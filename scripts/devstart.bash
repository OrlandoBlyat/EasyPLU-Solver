#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
use_https=false
configure_https=false
run_mode=foreground
for argument in "$@"; do
  case "$argument" in
    --https) use_https=true ;;
    --configure-https) use_https=true; configure_https=true ;;
    --background) run_mode=background ;;
    --startup) run_mode=startup ;;
    --service) run_mode=service ;;
    --help|-h)
      echo "Usage: bash scripts/devstart.bash [--https|--configure-https] [--background|--startup]"
      exit 0 ;;
    *) echo "Unknown option: $argument" >&2; exit 1 ;;
  esac
done
source ./scripts/lib/check-dependencies.bash

frontend_host="0.0.0.0"
frontend_port="${FRONTEND_PORT:-3000}"
backend_port="${BACKEND_PORT:-8000}"
if "$use_https"; then
  export HTTPS_SETTINGS_FILE="config/dev-https.local.json"
  export HTTPS_CADDYFILE="var/https/dev.Caddyfile"
  export HTTPS_LABEL="Development"
  source ./scripts/lib/https.bash
fi

if [[ "$run_mode" == background || "$run_mode" == startup ]]; then
  service_args=("$run_mode" --development)
  if "$use_https"; then service_args+=(--https); fi
  exec "$python_bin" scripts/manage-service.py "${service_args[@]}"
fi

service_pids=()
cleanup() {
  trap - EXIT INT TERM
  for pid in "${service_pids[@]}"; do kill "$pid" 2>/dev/null || true; done
  for pid in "${service_pids[@]}"; do wait "$pid" 2>/dev/null || true; done
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

(APP_ENV=development exec "$python_bin" -m uvicorn backend.app:app --reload --host 127.0.0.1 --port "$backend_port") &
service_pids+=("$!")
(cd frontend && exec node node_modules/next/dist/bin/next dev --hostname "$frontend_host" --port "$frontend_port") &
service_pids+=("$!")

if "$use_https" && [[ "$https_mode" != none ]]; then
  (exec caddy run --config "$https_caddyfile" --adapter caddyfile) &
  service_pids+=("$!")
  echo "Development frontend: https://${https_host}:${https_port}"
else
  echo "Development frontend: http://localhost:${frontend_port}"
  FRONTEND_PORT="$frontend_port" node --input-type=module - <<'JS'
import { networkInterfaces } from "node:os"
let interfaces = {}
try { interfaces = networkInterfaces() } catch {
  console.log(`Network access: http://<this computer’s LAN IP>:${process.env.FRONTEND_PORT}`)
}
for (const addresses of Object.values(interfaces)) {
  for (const address of addresses || []) {
    if (address.family === "IPv4" && !address.internal) {
      console.log(`Network access: http://${address.address}:${process.env.FRONTEND_PORT}`)
    }
  }
}
JS
fi
set +e
wait -n "${service_pids[@]}"
service_status=$?
set -e
exit "$service_status"
