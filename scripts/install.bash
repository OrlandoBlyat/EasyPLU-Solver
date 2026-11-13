#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."

install_system=true
allow_sudo=true
case "${1:-}" in
  --skip-system) install_system=false ;;
  --no-sudo) allow_sudo=false ;;
  --help|-h)
    echo "Usage: bash scripts/install.bash [--skip-system|--no-sudo]"
    echo "Install Python/Node prerequisites, .venv dependencies, Chromium, frontend packages and API access."
    echo "--no-sudo runs system package commands directly. --skip-system uses existing system dependencies."
    exit 0 ;;
  "") ;;
  *) echo "Unknown option: $1" >&2; exit 1 ;;
esac

if [[ "$(uname -s)" != Linux ]]; then
  echo "This installer supports Linux (Debian/Ubuntu and Fedora)." >&2
  exit 1
fi
if [[ "$EUID" -eq 0 ]]; then
  echo "Run this script as your normal user; it uses sudo only for system packages." >&2
  exit 1
fi

use_sudo=false
if "$allow_sudo" && command -v sudo >/dev/null; then
  use_sudo=true
fi

run_system() {
  if "$use_sudo"; then
    sudo "$@"
  else
    "$@"
  fi
}

if "$install_system"; then
  if [[ ! -t 0 ]]; then
    echo "Run interactively to approve system packages, or use --skip-system." >&2
    exit 1
  fi
  read -r -p "Install Python, Node.js/npm and browser system dependencies? [y/N] " answer
  case "$answer" in
    [yY]|[yY][eE][sS])
      if "$use_sudo" && ! sudo -v; then
        echo "sudo authentication failed. Retrying package commands directly." >&2
        use_sudo=false
      fi
      ;;
    *) echo "System installation skipped. Checking existing prerequisites."; install_system=false ;;
  esac
fi

if "$install_system"; then
  if command -v apt-get >/dev/null; then
    run_system apt-get update
    run_system apt-get install -y ca-certificates curl openssl python3 python3-venv python3-pip python3-pip-whl python3-setuptools-whl nodejs npm
    python_venv_package="$(python3 -c 'import sys; print(f"python{sys.version_info.major}.{sys.version_info.minor}-venv")')"
    run_system apt-get install -y "$python_venv_package"
  elif command -v dnf >/dev/null; then
    # Fedora is not an officially supported Playwright distribution. Chromium
    # pulls in native browser libraries; the browser smoke check below verifies compatibility.
    run_system dnf install -y ca-certificates curl openssl python3 python3-pip nodejs npm chromium
  else
    echo "Unsupported package manager. Install Python 3.10+, Node.js 20+, npm and browser libraries, then use --skip-system." >&2
    exit 1
  fi
fi

for executable in python3 node npm; do
  command -v "$executable" >/dev/null || {
    echo "Missing prerequisite: $executable" >&2
    echo "Ask an administrator to install it, or install a suitable version in your user account and rerun with --no-sudo." >&2
    exit 1
  }
done
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else "Python 3.10+ is required")'
node -e 'if (Number(process.versions.node.split(".")[0]) < 20) { console.error("Node.js 20+ is required; upgrade Node.js and rerun."); process.exit(1) }'

if ! python3 -m venv .venv; then
  python_executable="$(command -v python3)"
  python_version="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
  echo "Could not create a pip-enabled virtual environment with $python_executable (Python $python_version)." >&2
  if command -v apt-get >/dev/null; then
    echo "Install or repair the matching Debian/Ubuntu venv packages, then rerun this installer:" >&2
    echo "  sudo apt-get update && sudo apt-get install --reinstall python${python_version}-venv python3-pip-whl python3-setuptools-whl" >&2
  elif command -v dnf >/dev/null; then
    echo "Repair the Python venv packages with your administrator, then rerun this installer." >&2
  fi
  exit 1
fi
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r backend/requirements.txt

if "$install_system" && command -v apt-get >/dev/null; then
  run_system .venv/bin/python -m playwright install-deps chromium
fi
if ! .venv/bin/python -m playwright install chromium; then
  echo "Playwright could not install Chromium. Install its browser dependencies, then rerun the installer." >&2
  exit 1
fi
npm --prefix frontend ci --include=dev

# Check actual browser startup, not just successful downloads.
if ! .venv/bin/python - <<'PY'
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=["--disable-dev-shm-usage"])
    page = browser.new_page()
    page.set_content("<title>EasyPLU installation check</title>")
    assert page.title() == "EasyPLU installation check"
    browser.close()
print("Chromium startup verified")
PY
then
  echo "Chromium could not start. Install its system libraries, then rerun the installer." >&2
  exit 1
fi

.venv/bin/python scripts/setup-access.py
echo "Installation complete."
echo "Activate Python: source .venv/bin/activate"
echo "Development: bash scripts/devstart.bash"
echo "Production:  bash scripts/prodstart.bash"
