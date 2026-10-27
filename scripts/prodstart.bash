#!/usr/bin/env bash
set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
run_mode=prompt
configure_https=false
for argument in "$@"; do
  case "$argument" in
    --foreground) run_mode=foreground ;;
    --background) run_mode=background ;;
    --startup) run_mode=startup ;;
    --service) run_mode=service ;;
    --configure-https) configure_https=true ;;
    --help|-h)
      echo "Usage: bash scripts/prodstart.bash [--foreground|--background|--startup] [--configure-https]"
      exit 0 ;;
    *) echo "Unknown option: $argument" >&2; exit 1 ;;
  esac
done
source ./scripts/lib/check-dependencies.bash

if [[ ! -s .api-key || ! -f front/.env.local ]]; then
  if [[ ! -t 0 ]]; then
    echo "Configure backend access first: python scripts/setup-access.py" >&2
    exit 1
  fi
  read -r -p "Backend access is not configured. Run scripts/setup-access.py now? [y/N] " setup_answer
  case "$setup_answer" in
    [yY]|[yY][eE][sS]) "$python_bin" scripts/setup-access.py ;;
    *) echo "Setup skipped. Startup cancelled."; exit 1 ;;
  esac
  if [[ ! -s .api-key || ! -f front/.env.local ]]; then
    echo "Backend access setup is incomplete." >&2
    exit 1
  fi
fi

export APP_ENV=production
export NODE_ENV=production

# Default to loopback; terminate HTTPS at a reverse proxy.
frontend_host="${FRONTEND_HOST:-127.0.0.1}"
frontend_port="${FRONTEND_PORT:-3000}"
backend_port="${BACKEND_PORT:-8000}"
export API_BASE_URL="${API_BASE_URL:-http://127.0.0.1:${backend_port}}"
source ./scripts/lib/https.bash

if [[ "$run_mode" == prompt ]]; then
  run_mode=foreground
  if [[ -t 0 && "$(uname -s)" == Linux ]]; then
    echo "Run production: 1) foreground  2) background  3) background + start at boot"
    read -r -p "Choose [1]: " run_answer
    case "$run_answer" in
      ""|1) run_mode=foreground ;;
      2) run_mode=background ;;
      3) run_mode=startup ;;
      *) echo "Invalid run mode." >&2; exit 1 ;;
    esac
  fi
fi

if [[ "$run_mode" != service ]]; then
  npm --prefix front run build
elif [[ ! -s front/.next/BUILD_ID ]]; then
  echo "Production build is missing. Run prodstart.bash interactively first." >&2
  exit 1
fi

if [[ "$run_mode" == background || "$run_mode" == startup ]]; then
  exec "$python_bin" scripts/manage-service.py "$run_mode"
fi

service_pids=()
cleanup() {
  trap - EXIT INT TERM
  for pid in "${service_pids[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
  for pid in "${service_pids[@]}"; do
    wait "$pid" 2>/dev/null || true
  done
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

(exec "$python_bin" -m uvicorn back.api:app --host 127.0.0.1 --port "$backend_port" --workers 1) &
service_pids+=("$!")

# Execute Next directly so signals reach its process without an npm wrapper.
(cd front && exec node node_modules/next/dist/bin/next start --hostname "$frontend_host" --port "$frontend_port") &
service_pids+=("$!")

if [[ "$https_mode" != none ]]; then
  (exec caddy run --config "$PWD/var/https/Caddyfile" --adapter caddyfile) &
  service_pids+=("$!")
else
  echo "Production frontend: http://${frontend_host}:${frontend_port}"
fi

# Stop both services if either exits, retaining its exit status.
set +e
wait -n "${service_pids[@]}"
service_status=$?
set -e
exit "$service_status"
