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
bash devstart.bash
```

Open **http://localhost:3000**. Enter your credentials, choose **easyPLU** or **Lidl SSO**, and enter the SMS code when prompted. The login form hides while the session runs.

**On your phone:** connect to the same network and open `http://<computer-LAN-IP>:3000`. Allow port 3000 through your firewall if needed. API requests pass through the frontend; port 8000 can stay local.

## Configuration

| Setting | Default |
| --- | --- |
| Frontend | Port `3000` |
| Backend | Port `8000` |
| `API_BASE_URL` | `http://127.0.0.1:8000` — server-side frontend setting |

To use a different backend, set `API_BASE_URL` in `front/.env.local` and restart the frontend.

PLU data is cached in `back/plu_items.db`. SSO saves browser state in `back/mylidl_session.json`; debug artifacts go into `back/mylidl_debug/`. Keep session files and debug captures private.

**Debugging:** edit `debug-config.json`. `enabled` is the master switch; individual switches control solver/SSO logs, browser events, screenshots, tracebacks, and frontend console output. Restart both servers after changing it. Framework access logs are separate.

## Project layout

- `front/` — interface and API proxy.
- `back/api.py` — endpoints, progress streaming, and SMS handling.
- `back/solver.py` — authentication and session automation.
- `back/ssohandler.py` — MyLidl browser automation.

---

Independent educational project; not affiliated with Lidl or Knowledge Hero. Respect the platform's terms of service.
