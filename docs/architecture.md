# Architecture

The two applications are `frontend/` (Next.js) and `backend/` (FastAPI). The frontend talks to the backend through the server-only API proxy; the internal key stays on the server. `backend/app.py` owns application setup and lifecycle. Feature routers in `backend/api/` preserve the existing endpoint URLs.

## Backend responsibilities

Authentication in `backend/auth/` supplies a job-local upstream session. The test runner and catalogue collector share that client without sharing credentials across concurrent jobs. Interactive execution lives in `backend/tests_runner/service.py`; the solver owns upstream test operations and decryption.

`backend/catalog/service.py` orchestrates refresh and export. The collector normalizes upstream products, the cache module validates and merges them, the images module enforces download restrictions and caches processed assets, and the PDF module renders the handbook. Neither the API nor the CLI owns a separate implementation.

`backend/scheduling/service.py` authorizes enrollment from a recent successful direct EasyPLU test and requires consent. The repository owns SQLite, credentials owns encryption and key migration, state owns short-lived grants and cancellation events, and the worker owns automatic runs. The application lifespan starts and stops the worker. No SSO credentials are enrolled.

Interactive requests enter a bounded FIFO queue before launching a worker. Waiting clients receive a `queued` progress event, and disconnects remove their reservations. Execution deadlines begin after admission. Scheduled jobs defer while interactive requests wait. Defaults are two active tests, twenty waiting requests, and a one-hour queue timeout; configure `MAX_ACTIVE_JOBS`, `MAX_QUEUED_JOBS`, and `MAX_QUEUE_SECONDS`. Each browser can have one active or queued request. Without a trusted edge client address, start-rate accounting uses the signed browser identity rather than the shared loopback proxy address. Queue state is in memory and is cleared on backend restart.

Cross-cutting limits, bounded requests, cancellation, error translation, logging, and single-worker enforcement live in `backend/infrastructure/`.

## Frontend responsibilities

The login feature coordinates login requests and streamed test state. Password input, run progress/OTP, and results have their own components. Footer tools own PDF download state and invoke the independent scheduling controller and modal. Helpers under `lib/server/` belong only in server routes; client-facing data types live under `lib/client/`.

## Commands and persistence

Use `python -m cli.export_catalog` for optional handbook export and `python -m cli.scheduled_tests` for the legacy batch scheduler. The corresponding old script paths remain thin wrappers. The CLI scheduler is retained for compatibility; its credentials and runs remain independent of web enrollment.

Python dependencies are defined once in `backend/requirements.txt`; frontend dependencies use npm and `frontend/package-lock.json`. Deployment helpers stay under `scripts/`.

`data/catalog-seed.json` is the versioned initial product snapshot. `var/plu-catalog/cache.json` is mutable and ignored; existing local overrides are preserved. If the default runtime cache is absent, reads use the seed until a refresh writes the runtime cache. Databases, generated PDFs, images, and debug artifacts stay under ignored `var/`. Credential encryption keys remain outside the checkout.

## Migration

Stop old development/production processes and restart with the same `scripts/devstart.bash` or `scripts/prodstart.bash` commands. Direct commands must now use `backend.app:app` and the `frontend/` directory. Local frontend environment/dependency files moved with the directory. Existing runtime cache and schedule databases were not relocated.

Tests are grouped by feature. Run `.venv/bin/python -m unittest discover -s tests -v`, `frontend/node_modules/.bin/tsc --noEmit -p frontend/tsconfig.json`, and `npm --prefix frontend run build`.
