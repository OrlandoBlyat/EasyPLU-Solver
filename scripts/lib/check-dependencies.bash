#!/usr/bin/env bash
# Source from a startup script after changing to the repository root.

select_python() {
  python_bin=""
  for candidate in .venv/bin/python back/venv/bin/python venv/bin/python; do
    if [[ -x "$candidate" ]]; then
      python_bin="$PWD/$candidate"
      break
    fi
  done
  if [[ -z "$python_bin" ]]; then
    python_bin="$(command -v python3 || true)"
  fi
}

check_dependencies() {
  local missing=0
  select_python
  if [[ -z "$python_bin" ]]; then
    echo "Missing Python 3.10+." >&2
    missing=1
  elif ! "$python_bin" - <<'PY'
import importlib
import sys
if sys.version_info < (3, 10):
    raise SystemExit("Python 3.10+ is required.")
missing = []
modules = ["fastapi", "uvicorn", "requests", "pydantic", "playwright.sync_api"]
modules.append("cryptography")
for module in modules:
    try:
        importlib.import_module(module)
    except ImportError:
        missing.append(module)
if missing:
    raise SystemExit("Missing Python dependencies: " + ", ".join(missing))
import pydantic
if int(pydantic.__version__.split(".")[0]) != 2:
    raise SystemExit("Pydantic 2 is required.")
from playwright.sync_api import sync_playwright
try:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, timeout=10000, args=["--disable-dev-shm-usage"])
        browser.close()
except Exception as error:
    raise SystemExit("Chromium or its system dependencies are unavailable: " + str(error))
PY
  then
    missing=1
  fi
  if ! command -v node >/dev/null || ! command -v npm >/dev/null; then
    echo "Missing Node.js/npm." >&2
    missing=1
  elif ! node -e 'if (Number(process.versions.node.split(".")[0]) < 20) process.exit(1)'; then
    echo "Node.js 20+ is required." >&2
    missing=1
  elif ! npm --prefix front ls --depth=0 --include=dev >/dev/null 2>&1; then
    echo "Frontend dependencies are missing or do not match package.json." >&2
    missing=1
  fi
  return "$missing"
}

if ! check_dependencies; then
  if [[ ! -t 0 ]]; then
    echo "Dependencies are missing. Run: bash scripts/install.bash" >&2
    exit 1
  fi
  read -r -p "Install missing dependencies now using scripts/install.bash? [y/N] " install_answer
  case "$install_answer" in
    [yY]|[yY][eE][sS]) bash scripts/install.bash ;;
    *) echo "Installation skipped. Startup cancelled."; exit 1 ;;
  esac
  if ! check_dependencies; then
    echo "Dependency checks still fail. Startup cancelled." >&2
    exit 1
  fi
fi
