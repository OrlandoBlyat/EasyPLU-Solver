<p align="center">
  <img src="../front/public/easyplu-solver-logo.png" alt="EasyPLU solver" width="360" />
</p>

# EasyPLU solver

Automate EasyPLU training sessions with a mobile-friendly interface and live progress.

- **Two login options:** EasyPLU credentials or Lidl SSO with SMS verification.
- **Automatic sessions:** submit answers and repeat until 100% knowledge or the 50-attempt limit.
- **Two modes:** raise knowledge with **Dvig znanja**, or complete assigned **PLU Preverjanje** tasks with overall progress. Scheduled runs complete assignments before a regular test.
- **Custom score:** optionally choose a target result.
- **Live results:** score, knowledge, points, store ranking, and execution time.

Built with Next.js, TypeScript, Tailwind CSS, FastAPI, Playwright, and AES decryption.

## Quick start

Linux installer supports Debian/Ubuntu and Fedora. It installs system prerequisites with your approval, creates `.venv`, installs Python/frontend packages and Playwright Chromium, verifies browser startup, and configures API access. Requires Python 3.10+ and Node.js 20+ (older distribution packages must be upgraded). Use `bash scripts/install.bash --skip-system` if system dependencies are already installed.

```bash
git clone https://github.com/OrlandoBlyat/EasyPLU-Solver.git
cd EasyPLU-Solver

bash scripts/install.bash
source .venv/bin/activate
bash scripts/devstart.bash
```

Open **http://localhost:3000**. Enter your EasyPLU/MyLidl credentials, choose **easyPLU** or **Lidl SSO**, and enter the SMS code when prompted.

The app is open; FastAPI requires a private key added by the frontend server. Keep `.api-key` and `front/.env.local` private and port 8000 bound to localhost. Missing key configuration blocks backend requests. The public proxy exposes only health, SMS submission, and session streaming; these remain publicly callable. Use HTTPS for network access.

Runs use server-generated IDs. SMS submission requires the matching signed HttpOnly browser cookie and is single-use; the app remains open without an app login.

**On your phone:** connect to the same network and open `http://<computer-LAN-IP>:3000`. Allow port 3000 through your firewall if needed. API requests pass through the frontend; port 8000 can stay local.


## Configuration

Both startup scripts check Python packages, Node/frontend dependencies, and Chromium before starting. Missing dependencies trigger an installer prompt; they automatically use the project virtual environment when present.

**Production:** run `bash scripts/prodstart.bash`. It builds Next.js, disables debugging, and runs one backend worker. Both services bind to loopback by default; serve them through an HTTPS reverse proxy. Optional settings: `FRONTEND_HOST`, `FRONTEND_PORT`, `BACKEND_PORT`, and `API_BASE_URL`.

| Setting | Default |
| --- | --- |
| Frontend | Port `3000` |
| Backend | Port `8000` |
| `API_BASE_URL` | `http://127.0.0.1:8000` — server-side frontend setting |

To use a different backend, set `API_BASE_URL` in `front/.env.local` and restart the frontend.

Limits: **2 active jobs**, **3 starts/minute/IP**, **10 SMS submissions/minute/IP**, and **10 minutes/job**. Backend settings: `MAX_ACTIVE_JOBS`, `JOB_STARTS_PER_MINUTE`, `SMS_SUBMISSIONS_PER_MINUTE`, and `MAX_JOB_SECONDS`. Deadline cancellation takes effect after in-flight operations return; slots remain occupied until cleanup.

Run **one backend worker**. A local process lock rejects a second worker against the same checkout (Linux/macOS); multiple replicas require shared storage. Local proxied clients share one IP bucket. Separate device buckets require a trusted proxy that overwrites a client-IP header: set frontend `EDGE_CLIENT_IP_HEADER` and backend `TRUST_EDGE_CLIENT_IP=1`. Keep trust disabled without that proxy.

PLU numbers are decrypted from execution items and kept in memory for each test. SSO saves browser state in `var/auth/mylidl_session.json` only when development debugging and `session_state` are enabled (owner-only permissions); debug artifacts go into `var/debug/`. Keep session files and debug captures private.

**Debugging:** edit `config/debug-config.json`. `enabled` is the master switch; individual switches control solver/SSO logs, browser events, screenshots, session state, tracebacks, and frontend console output. Restart both servers after changing it. Backend debugging requires `APP_ENV=development` (set by `scripts/devstart.bash`); it is off by default and always off with `NODE_ENV=production`. Frontend debugging runs only in Next.js development mode. Development logs are unredacted; client errors stay generic. Framework access logs are separate.

## Scheduled tests

The scheduler checks API health and starts a local backend if needed, without starting the frontend. It stops only the backend it started when you exit. Copy `config/test-credentials.example.json` to `config/test-credentials.json`, enter easyPLU credentials (add objects for more accounts), and restrict access:

```bash
cp config/test-credentials.example.json config/test-credentials.json
chmod 600 config/test-credentials.json
source .venv/bin/activate
python scripts/scheduled-tests.py --check
python scripts/scheduled-tests.py
```

Set `interval_seconds` in `config/scheduled-tests.json` (default: one hour after each batch). Accounts run sequentially; files reload before each batch. Use `--once` for a single batch. Each account runs one test; unattended SSO/SMS is unsupported. Credentials are gitignored. Keep the scheduler running, or supervise it with systemd for unattended operation.



## Project layout

- `front/` — Next.js interface and API proxy.
- `back/api.py` — API entry point.
- `back/auth/`, `back/plu/` — SSO and PLU automation.
- `back/core/`, `back/runtime/`, `back/security/` — logging, jobs, and protection.
- `scripts/` — installation, startup, access setup, and scheduler.
- `config/` — debug/scheduler settings and credentials template.
- `docs/` — development notes.
- `var/` — ignored runtime artifacts.

---

Independent educational project; not affiliated with Lidl or Knowledge Hero. Respect the platform's terms of service.
