#!/bin/bash

(cd front && npm run dev -- --hostname 0.0.0.0) &

(cd back && uvicorn api:app --reload --port 8000) &

trap 'kill $(jobs -p) 2>/dev/null' EXIT INT TERM

wait
