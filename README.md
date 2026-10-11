<p align="center">
  <img src="front/public/easyplu-solver-logo.png" alt="EasyPLU solver" width="360" />
</p>

# EasyPLU solver

Automate EasyPLU training sessions with a mobile-friendly interface and live progress.

- **Two login options:** EasyPLU credentials or Lidl SSO with SMS verification.
- **Automatic sessions:** submit answers and repeat until 100% knowledge or the 50-attempt limit.
- **Custom score:** optionally choose a target result.
- **Live results:** score, knowledge, points, store ranking, and execution time.

Built with Next.js, TypeScript, Tailwind CSS, FastAPI, Playwright, and SQLite.

## Quick start

Requires **Python 3.10+**, **Node.js 20+**, and npm. Commands below use Bash.

```bash
git clone https://github.com/OrlandoBlyat/EasyPLU-Solver.git
cd EasyPLU-Solver

python -m venv .venv
source .venv/bin/activate
pip install fastapi uvicorn requests pydantic playwright
python -m playwright install chromium

npm --prefix front install
python setup-access.py
bash devstart.bash
```

Open **http://localhost:3000**. Enter your EasyPLU/MyLidl credentials, choose **easyPLU** or **Lidl SSO**, and enter the SMS code when prompted.

The app is open; FastAPI requires a private key added by the frontend server. Keep `.api-key` and `front/.env.local` private and port 8000 bound to localhost. Missing key configuration blocks backend requests. The public proxy exposes only health, SMS submission, and session streaming; these remain publicly callable. Use HTTPS for network access.

Runs use server-generated IDs. SMS submission requires the matching signed HttpOnly browser cookie and is single-use; the app remains open without an app login.

**On your phone:** connect to the same network and open `http://<computer-LAN-IP>:3000`. Allow port 3000 through your firewall if needed. API requests pass through the frontend; port 8000 can stay local.


## Configuration

**Production:** activate the Python environment and run `bash prodstart.bash`. It builds Next.js, disables debugging, and runs one backend worker. Both services bind to loopback by default; serve them through an HTTPS reverse proxy. Optional settings: `FRONTEND_HOST`, `FRONTEND_PORT`, `BACKEND_PORT`, and `API_BASE_URL`.

| Setting | Default |
| --- | --- |
| Frontend | Port `3000` |
| Backend | Port `8000` |
| `API_BASE_URL` | `http://127.0.0.1:8000` — server-side frontend setting |

To use a different backend, set `API_BASE_URL` in `front/.env.local` and restart the frontend.

Limits: **2 active jobs**, **3 starts/minute/IP**, **10 SMS submissions/minute/IP**, and **10 minutes/job**. Backend settings: `MAX_ACTIVE_JOBS`, `JOB_STARTS_PER_MINUTE`, `SMS_SUBMISSIONS_PER_MINUTE`, and `MAX_JOB_SECONDS`. Deadline cancellation takes effect after in-flight operations return; slots remain occupied until cleanup.

Run **one backend worker**. A local process lock rejects a second worker against the same checkout (Linux/macOS); multiple replicas require shared storage. Local proxied clients share one IP bucket. Separate device buckets require a trusted proxy that overwrites a client-IP header: set frontend `EDGE_CLIENT_IP_HEADER` and backend `TRUST_EDGE_CLIENT_IP=1`. Keep trust disabled without that proxy.

PLU data is cached in `back/plu_items.db`. SSO saves browser state in `back/mylidl_session.json` only when development debugging and `session_state` are enabled (owner-only permissions); debug artifacts go into `back/mylidl_debug/`. Keep session files and debug captures private.

**Debugging:** edit `debug-config.json`. `enabled` is the master switch; individual switches control solver/SSO logs, browser events, screenshots, session state, tracebacks, and frontend console output. Restart both servers after changing it. Backend debugging requires `APP_ENV=development` (set by `devstart.bash`); it is off by default and always off with `NODE_ENV=production`. Frontend debugging runs only in Next.js development mode. Development logs are unredacted; client errors stay generic. Framework access logs are separate.

## Project layout

- `front/` — interface and API proxy.
- `back/api.py` — endpoints, progress streaming, and SMS handling.
- `back/solver.py` — authentication and session automation.
- `back/ssohandler.py` — MyLidl browser automation.

---

Independent educational project; not affiliated with Lidl or Knowledge Hero. Respect the platform's terms of service.
