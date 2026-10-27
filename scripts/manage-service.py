"""Install a user systemd service after interactive production setup/build."""
import argparse
import getpass
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SERVICE = "easyplu-solver.service"


def quote(value):
    if "\n" in value or "\r" in value or "\x00" in value:
        raise ValueError("Service paths/settings cannot contain newlines or NUL")
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%") + '"'


def unit_text(root, environment):
    lines = ["[Unit]", "Description=EasyPLU Solver production", "StartLimitIntervalSec=300", "StartLimitBurst=3",
             "", "[Service]", "Type=simple", "WorkingDirectory=" + quote(str(root)),
             "ExecStart=/bin/bash " + quote(str(root / "scripts/prodstart.bash")).replace("$", "$$") + " --service",
             "Restart=on-failure", "RestartSec=10", "KillMode=control-group", "TimeoutStopSec=45",
             "UMask=0077", "StandardOutput=journal", "StandardError=journal"]
    for key in ("PATH", "FRONTEND_HOST", "FRONTEND_PORT", "BACKEND_PORT", "API_BASE_URL", "MAX_ACTIVE_JOBS",
                "MAX_JOB_SECONDS", "JOB_STARTS_PER_MINUTE", "SMS_SUBMISSIONS_PER_MINUTE"):
        if key in environment:
            lines.append("Environment=" + quote(f"{key}={environment[key]}"))
    return "\n".join(lines + ["", "[Install]", "WantedBy=default.target", ""])


def systemctl(*arguments):
    subprocess.run(["systemctl", "--user", *arguments], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("background", "startup"))
    args = parser.parse_args()
    if sys.platform != "linux" or not shutil.which("systemctl"):
        raise SystemExit("Background/startup mode requires Linux with a user systemd session. Use --foreground instead.")
    if os.geteuid() == 0:
        raise SystemExit("Run this as your normal user, not root.")
    subprocess.run(["systemctl", "--user", "show-environment"], check=True, stdout=subprocess.DEVNULL)
    # HTTPS setup overrides XDG_CONFIG_HOME for Caddy; use a fixed user-unit path.
    directory = Path.home() / ".config/systemd/user"
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / SERVICE
    target.write_text(unit_text(ROOT, os.environ))
    target.chmod(0o600)
    systemctl("daemon-reload")
    if args.mode == "startup":
        username = getpass.getuser()
        result = subprocess.run(["loginctl", "show-user", username, "--property=Linger", "--value"],
                                capture_output=True, text=True, check=True)
        if result.stdout.strip() != "yes":
            print("Starting before login requires user lingering (continues after logout).")
            if not sys.stdin.isatty():
                raise SystemExit("Enable lingering interactively, then rerun --startup.")
            answer = input("Enable lingering using sudo loginctl enable-linger? [y/N] ").strip().lower()
            if answer not in ("y", "yes"):
                raise SystemExit("Startup cancelled. Use --background to run only in the current user session.")
            subprocess.run(["sudo", "loginctl", "enable-linger", username], check=True)
        systemctl("enable", SERVICE)
    else:
        # Selecting background explicitly removes previously enabled autostart.
        systemctl("disable", SERVICE)
    systemctl("restart", SERVICE)
    print("Production launched in the background.")
    print("Status: systemctl --user status " + SERVICE)
    print("Logs:   journalctl --user -u " + SERVICE + " -f")
    print("Stop:   systemctl --user stop " + SERVICE)
    print("Disable autostart: systemctl --user disable " + SERVICE)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        raise SystemExit(f"Service setup failed: {error}")
