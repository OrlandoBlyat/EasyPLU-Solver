import argparse
import json
import re
import secrets
import signal
import stat
import subprocess
import sys
import os
import time
from pathlib import Path
from threading import Event
from urllib.parse import urlsplit
import requests

ROOT = Path(__file__).resolve().parents[1]


def ensure_api(config, key):
    """Reuse a healthy API, or start a local backend with this Python environment."""
    print("Checking API health...", flush=True)
    def healthy():
        try:
            response = requests.get(config["api_url"].rstrip("/") + "/health",
                                    headers={"X-Internal-Key": key}, timeout=(2, 2))
            return response.ok and response.json().get("service") == "api"
        except (requests.RequestException, ValueError):
            return False
    if healthy():
        print("Using the running API", flush=True)
        return None
    url = urlsplit(config["api_url"])
    if url.hostname not in ("localhost", "127.0.0.1", "::1") or url.scheme != "http":
        raise ValueError("Remote API is unavailable; automatic startup supports local HTTP only")
    port = url.port or 80
    environment = {**os.environ, "APP_ENV": "production"}
    print("Starting the backend API (no frontend)", flush=True)
    process = subprocess.Popen([sys.executable, "-m", "uvicorn", "back.api:app",
                                "--host", url.hostname, "--port", str(port), "--workers", "1"],
                               cwd=ROOT, env=environment)
    try:
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError("Backend startup failed; check its terminal output")
            if healthy():
                print("Backend API ready", flush=True)
                return process
            time.sleep(0.25)
        raise RuntimeError("Backend did not become healthy within 30 seconds")
    except BaseException:
        stop_api(process)
        raise


def stop_api(process):
    if process is not None and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def load_settings(path):
    config = json.loads(path.read_text())
    for key, minimum in (("interval_seconds", 60), ("account_delay_seconds", 20), ("request_timeout_seconds", 1)):
        value = config.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value < minimum:
            raise ValueError(f"{key} must be at least {minimum}")
    score = config.get("target_score")
    if score is not None and (type(score) is not int or not 0 <= score <= 99):
        raise ValueError("target_score must be null or an integer from 0 to 99")
    url = urlsplit(config.get("api_url", ""))
    if url.scheme not in ("http", "https") or not url.hostname or url.username or url.password:
        raise ValueError("api_url must be an HTTP(S) server URL")
    if url.scheme == "http" and url.hostname not in ("localhost", "127.0.0.1", "::1"):
        raise ValueError("Remote backend connections require HTTPS")
    credentials_path = path.parent / config["credentials_file"]
    if credentials_path.stat().st_mode & (stat.S_IRWXG | stat.S_IRWXO):
        raise ValueError("Credentials file must be private: chmod 600 " + str(credentials_path))
    accounts = json.loads(credentials_path.read_text())
    if not isinstance(accounts, list) or not accounts:
        raise ValueError("Credentials file must contain a non-empty account array")
    for index, account in enumerate(accounts, 1):
        if not isinstance(account, dict):
            raise ValueError(f"Account {index} must be an object")
        email = account.get("email", "")
        password = account.get("password", "")
        if not isinstance(email, str) or len(email) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email.strip()):
            raise ValueError(f"Account {index} needs an easyPLU email address; unattended SSO is unsupported")
        if not isinstance(password, str) or not 8 <= len(password) <= 1024:
            raise ValueError(f"Account {index} password must contain 8–1024 characters")
    key = (ROOT / ".api-key").read_text().strip()
    if not key:
        raise ValueError("Configure backend access with scripts/setup-access.py")
    return config, accounts, key


def run_batch(config, accounts, key, stop):
    failed = False
    with requests.Session() as session:
        session.headers.update({"X-Internal-Key": key, "X-Run-Owner": secrets.token_hex(32)})
        for index, account in enumerate(accounts, 1):
            if stop.is_set():
                break
            print(f"Running account {index}/{len(accounts)}", flush=True)
            try:
                response = session.post(config["api_url"].rstrip("/") + "/run-session",
                    json={"email": account["email"].strip(), "password": account["password"],
                          "login_method": "easyplu", "target_score": config.get("target_score")},
                    timeout=(5, config["request_timeout_seconds"]))
                if not response.ok:
                    failed = True
                    print(f"Account {index}: failed (HTTP {response.status_code})", flush=True)
                else:
                    result = response.json().get("data", {})
                    print(f"Account {index}: completed; knowledge={result.get('user_knowledge')}%", flush=True)
            except (requests.RequestException, ValueError):
                failed = True
                print(f"Account {index}: backend request failed", flush=True)
            if index < len(accounts):
                stop.wait(config["account_delay_seconds"])
    return not failed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "config" / "scheduled-tests.json")
    parser.add_argument("--once", action="store_true", help="Run one batch and exit")
    parser.add_argument("--check", action="store_true", help="Validate files without making requests")
    args = parser.parse_args()
    print("Scheduled tests starting...", flush=True)
    print(f"Configuration: {args.config.resolve()}", flush=True)
    stop = Event()
    owned_api = None
    def shutdown(signum, frame):
        stop.set()
        raise KeyboardInterrupt
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    try:
        while not stop.is_set():
            config, accounts, key = load_settings(args.config.resolve())
            print(f"Loaded {len(accounts)} account(s); interval: {config['interval_seconds']} seconds", flush=True)
            if args.check:
                print(f"Configuration valid: {len(accounts)} account(s), interval {config['interval_seconds']} seconds", flush=True)
                return 0
            if owned_api is not None and owned_api.poll() is not None:
                owned_api = None
            if owned_api is None:
                owned_api = ensure_api(config, key)
            success = run_batch(config, accounts, key, stop)
            if args.once:
                return 0 if success else 1
            print(f"Next batch in {config['interval_seconds']} seconds", flush=True)
            stop.wait(config["interval_seconds"])
    except KeyboardInterrupt:
        print("Scheduler stopped", flush=True)
        return 0
    except FileNotFoundError as error:
        print(f"Missing file: {error.filename}. Follow docs/README.md scheduler setup.", flush=True)
        return 1
    except (ValueError, KeyError, OSError) as error:
        print(f"Invalid scheduler configuration: {error}", flush=True)
        return 1
    except RuntimeError as error:
        print(str(error), flush=True)
        return 1
    finally:
        stop_api(owned_api)


if __name__ == "__main__":
    raise SystemExit(main())
