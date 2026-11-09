#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
source ./scripts/lib/check-dependencies.bash

service_pids=()
cleanup() {
  trap - EXIT INT TERM
  for pid in "${service_pids[@]}"; do kill "$pid" 2>/dev/null || true; done
  for pid in "${service_pids[@]}"; do wait "$pid" 2>/dev/null || true; done
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

(APP_ENV=development exec "$python_bin" -m uvicorn backend.app:app --reload --host 127.0.0.1 --port 8000) &
service_pids+=("$!")
(cd frontend && exec node node_modules/next/dist/bin/next dev --hostname 0.0.0.0) &
service_pids+=("$!")

echo "Development frontend: http://localhost:3000"
node --input-type=module - <<'JS'
import { networkInterfaces } from "node:os"
let interfaces = {}
try { interfaces = networkInterfaces() } catch {
  console.log("Network access: http://<this computer’s LAN IP>:3000")
}
for (const addresses of Object.values(interfaces)) {
  for (const address of addresses || []) {
    if (address.family === "IPv4" && !address.internal) {
      console.log(`Network access: http://${address.address}:3000`)
    }
  }
}
JS
set +e
wait -n "${service_pids[@]}"
service_status=$?
set -e
exit "$service_status"
