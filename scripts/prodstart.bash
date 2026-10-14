#!/usr/bin/env bash
set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
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

npm --prefix front run build

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

echo "Production frontend: http://${frontend_host}:${frontend_port} (use an HTTPS reverse proxy for network access)"

# Stop both services if either exits, retaining its exit status.
set +e
wait -n "${service_pids[@]}"
service_status=$?
set -e
exit "$service_status"
