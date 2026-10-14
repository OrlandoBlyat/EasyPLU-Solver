#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."

install_system=true
case "${1:-}" in
  --skip-system) install_system=false ;;
  --help|-h)
    echo "Usage: bash scripts/install.bash [--skip-system]"
    echo "Install Python/Node prerequisites, .venv dependencies, Chromium, frontend packages and API access."
    echo "System packages require sudo. --skip-system uses existing system dependencies."
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

if "$install_system"; then
  if [[ ! -t 0 ]]; then
    echo "Run interactively to approve system packages, or use --skip-system." >&2
    exit 1
  fi
  read -r -p "Install Python, Node.js/npm and browser system dependencies using sudo? [y/N] " answer
  case "$answer" in
    [yY]|[yY][eE][sS]) ;;
    *) echo "System installation skipped. Checking existing prerequisites."; install_system=false ;;
  esac
fi

if "$install_system"; then
  if command -v apt-get >/dev/null; then
    sudo apt-get update
    sudo apt-get install -y python3 python3-venv python3-pip nodejs npm
  elif command -v dnf >/dev/null; then
    # Fedora is not an officially supported Playwright distribution. Chromium
    # pulls in native browser libraries; the browser smoke check below verifies compatibility.
    sudo dnf install -y python3 python3-pip nodejs npm chromium
  else
    echo "Unsupported package manager. Install Python 3.10+, Node.js 20+, npm and browser libraries, then use --skip-system." >&2
    exit 1
  fi
fi

for executable in python3 node npm; do
  command -v "$executable" >/dev/null || { echo "Missing prerequisite: $executable" >&2; exit 1; }
done
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else "Python 3.10+ is required")'
node -e 'if (Number(process.versions.node.split(".")[0]) < 20) { console.error("Node.js 20+ is required; upgrade Node.js and rerun."); process.exit(1) }'

python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r back/requirements.txt

if "$install_system" && command -v apt-get >/dev/null; then
  .venv/bin/python -m playwright install-deps chromium
fi
.venv/bin/python -m playwright install chromium
npm --prefix front ci --include=dev

# Check actual browser startup, not just successful downloads.
.venv/bin/python - <<'PY'
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=["--disable-dev-shm-usage"])
    page = browser.new_page()
    page.set_content("<title>EasyPLU installation check</title>")
    assert page.title() == "EasyPLU installation check"
    browser.close()
print("Chromium startup verified")
PY

.venv/bin/python scripts/setup-access.py
echo "Installation complete."
echo "Activate Python: source .venv/bin/activate"
echo "Development: bash scripts/devstart.bash"
echo "Production:  bash scripts/prodstart.bash"
