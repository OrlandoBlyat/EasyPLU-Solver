"""Choose an HTTPS transport and generate a private Caddy configuration."""
import argparse
import ipaddress
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SETTINGS = ROOT / "config/https.local.json"
DEFAULT_CADDYFILE = ROOT / "var/https/Caddyfile"


def ask(prompt, default):
    print(f"{prompt} [{default}]: ", end="", file=sys.stderr, flush=True)
    return input().strip() or default


def validate_path(value, name):
    if not isinstance(value, str) or not re.fullmatch(r"/[A-Za-z0-9._/-]+", value):
        raise ValueError(f"{name} must be an absolute path containing only letters, numbers, '.', '_', '/', or '-'")
    path = Path(value)
    if not path.is_file():
        raise ValueError(f"{name} does not exist or is not a file")
    return path


def validate(settings):
    mode = settings.get("mode")
    if mode not in ("letsencrypt", "local", "cloudflare", "none"):
        raise ValueError("Unknown HTTPS mode")
    host = settings.get("host", "localhost")
    if not isinstance(host, str) or len(host) > 253:
        raise ValueError("Invalid hostname")
    try:
        ipaddress.ip_address(host)
        is_ip = True
    except ValueError:
        is_ip = False
        if not all(re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", part) for part in host.split(".")):
            raise ValueError("Enter a hostname or IP, without https://, a path, or port")
    if mode == "letsencrypt" and (is_ip or "." not in host or host.endswith((".local", ".localhost", ".internal"))):
        raise ValueError("Let's Encrypt mode requires a public domain you control")
    port = settings.get("port", 443)
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("Invalid HTTPS port")
    if mode == "letsencrypt" and port != 443:
        raise ValueError("Let's Encrypt setup uses public ports 80 and 443")
    if mode == "cloudflare":
        if is_ip or "." not in host or host.endswith((".local", ".localhost", ".internal")):
            raise ValueError("Cloudflare Tunnel mode requires the public hostname covered by its Origin Certificate")
        certificate = validate_path(settings.get("certificate"), "certificate")
        key = validate_path(settings.get("key"), "key")
        if certificate == key:
            raise ValueError("certificate and key must be different files")
    return mode, host, port


def generate(settings, frontend_port, caddyfile):
    mode, host, port = validate(settings)
    if not 1 <= frontend_port <= 65535:
        raise ValueError("Invalid frontend port")
    if mode == "none":
        return
    if frontend_port == port or (mode == "letsencrypt" and frontend_port == 80):
        raise ValueError("Frontend port conflicts with the HTTPS proxy")
    address = f"[{host}]" if ":" in host else host
    tls = "tls internal" if mode == "local" else "tls {\n        issuer acme {\n            dir https://acme-v02.api.letsencrypt.org/directory\n        }\n    }"
    bind = ""
    client_ip_header = "header_up X-Real-IP {remote_host}"
    if mode == "cloudflare":
        tls = f"tls {settings['certificate']} {settings['key']}"
        bind = "bind 127.0.0.1"
        # The listener is loopback-only, so this header can only arrive through
        # cloudflared on the same host rather than directly from the network.
        client_ip_header = "header_up X-Real-IP {http.request.header.CF-Connecting-IP}"
    # Leave streaming responses unbuffered by Caddy's SSE handling; retain disconnect cancellation.
    content = f"""{{
    admin off
    skip_install_trust
    {"auto_https disable_redirects" if mode == "local" else ""}
}}
https://{address}:{port} {{
    {tls}
    {bind}
    reverse_proxy 127.0.0.1:{frontend_port} {{
        {client_ip_header}
    }}
}}
"""
    caddyfile.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    caddyfile.write_text(content)
    caddyfile.chmod(0o600)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--configure", action="store_true")
    parser.add_argument("--print", action="store_true", dest="print_settings")
    parser.add_argument("--frontend-port", type=int, default=3000)
    parser.add_argument("--settings", type=Path, default=DEFAULT_SETTINGS)
    parser.add_argument("--caddyfile", type=Path, default=DEFAULT_CADDYFILE)
    parser.add_argument("--label", default="Production")
    args = parser.parse_args()
    os.umask(0o077)
    settings_path = args.settings.resolve()
    caddyfile = args.caddyfile.resolve()
    if args.configure or not settings_path.exists():
        if not sys.stdin.isatty():
            raise ValueError("Configure transport interactively: python scripts/setup-https.py --configure")
        print(f"{args.label} connection:\n  1. Let's Encrypt — public domain, automatic trusted certificate\n  2. Cloudflare Tunnel — loopback HTTPS with a Cloudflare Origin Certificate\n  3. Local HTTPS — trust the local Caddy CA on each device\n  4. No certificate — unencrypted HTTP (explicit opt-out)", file=sys.stderr)
        choice = ask("Choose 1, 2, 3, or 4", "2")
        if choice == "1":
            print("Point your domain's A/AAAA records to this server. Forward/open TCP 80 and 443. Caddy will request and renew the certificate when started.", file=sys.stderr)
            settings = {"mode": "letsencrypt", "host": ask("Your domain", "plu.example.com"), "port": 443}
        elif choice == "2":
            print("Create a Cloudflare Origin Certificate for this hostname. cloudflared must use HTTPS to this loopback listener with TLS verification enabled.", file=sys.stderr)
            settings = {
                "mode": "cloudflare",
                "host": ask("Public hostname", "plu.example.com"),
                "port": int(ask("Loopback HTTPS port", "8443")),
                "certificate": ask("Absolute certificate path", "/etc/cloudflare/origin.pem"),
                "key": ask("Absolute private-key path", "/etc/cloudflare/origin-key.pem"),
            }
        elif choice == "3":
            settings = {"mode": "local", "host": ask("Hostname or LAN IP you will open", "localhost"), "port": int(ask("HTTPS port", "8443"))}
        elif choice == "4":
            print("WARNING: HTTP does not encrypt passwords or SMS codes. Use only on a trusted local connection or behind your own HTTPS proxy.", file=sys.stderr)
            settings = {"mode": "none", "host": "localhost", "port": 443}
        else:
            raise ValueError("Choose 1, 2, 3, or 4")
        validate(settings)
        settings_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        settings_path.write_text(json.dumps(settings, indent=2) + "\n")
        settings_path.chmod(0o600)
    settings = json.loads(settings_path.read_text())
    mode, host, port = validate(settings)
    generate(settings, args.frontend_port, caddyfile)
    if args.print_settings:
        print(f"{mode}\t{host}\t{port}")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, EOFError) as error:
        raise SystemExit(str(error))
