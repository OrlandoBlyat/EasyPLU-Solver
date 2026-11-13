<p align="center">
  <img src="../frontend/public/easyplu-solver-logo.svg" alt="EasyPLU solver" width="360" />
</p>

# EasyPLU solver

Automate EasyPLU training sessions with a mobile-friendly interface and live progress.

- **Two login options:** EasyPLU credentials or Lidl SSO with SMS verification.
- **Automatic sessions:** submit answers and repeat until 100% knowledge or the 50-attempt limit.
- **Two modes:** raise knowledge with **Improve knowledge**, or complete assigned **PLU checks** with overall progress. Scheduled runs complete assignments before a regular test.
- **Custom score:** optionally choose a target result.
- **Live results:** score, knowledge, points, store ranking, and execution time.

Built with Next.js, TypeScript, Tailwind CSS, FastAPI, Playwright, and AES decryption.

## Quick start

Linux installer supports Debian/Ubuntu and Fedora. It installs system prerequisites with your approval, including the venv package matching the selected Python version, creates `.venv`, installs Python/frontend packages and Playwright Chromium, verifies browser startup, and configures API access. Requires Python 3.10+ and Node.js 20+ (older distribution packages must be upgraded). Use `bash scripts/install.bash --no-sudo` when the package manager can install packages directly without sudo; it runs the same package commands without the sudo prefix. If Python reports that `ensurepip` is unavailable, install or repair the matching Debian/Ubuntu venv and wheel packages (for example, `sudo apt-get install --reinstall python3.13-venv python3-pip-whl python3-setuptools-whl` for Python 3.13), then rerun the installer.

```bash
git clone https://github.com/OrlandoBlyat/EasyPLU-Solver.git
cd EasyPLU-Solver

bash scripts/install.bash
source .venv/bin/activate
bash scripts/devstart.bash
```

Open **http://localhost:3000** on the host. Other devices on the same LAN can use **http://HOST_LAN_IP:3000**; `devstart.bash` prints available network URLs. The queued run shows elapsed wait time and can be cancelled before it starts. Interface and streamed progress messages follow the selected language. Both the script and `npm --prefix frontend run dev` bind to `0.0.0.0`. Development hot reload allows the host’s network addresses automatically; use `DEV_ALLOWED_ORIGINS` (comma-separated hostnames) for additional local DNS names. Allow inbound TCP port 3000 in the host firewall if needed. The backend remains private on localhost; browsers use the frontend proxy. Enter your EasyPLU/MyLidl credentials, choose **easyPLU** or **Lidl SSO**, and enter the SMS code when prompted.

The app is open; FastAPI requires a private key added by the frontend server. Keep `.api-key` and `frontend/.env.local` private and port 8000 bound to localhost. Missing key configuration blocks backend requests. The public proxy exposes only health, SMS submission, and session streaming; these remain publicly callable. Use HTTPS for network access.

Runs use server-generated IDs. SMS submission requires the matching signed HttpOnly browser cookie and is single-use; the app remains open without an app login.

**On your phone:** connect to the same network and open `http://<computer-LAN-IP>:3000`. Allow port 3000 through your firewall if needed. API requests pass through the frontend; port 8000 can stay local.


## Configuration

Both startup scripts check Python packages, Node/frontend dependencies, and Chromium before starting. Missing dependencies trigger an installer prompt; they automatically use the project virtual environment when present.

**Production:** run `bash scripts/prodstart.bash`. First startup asks for **Let's Encrypt**, **Cloudflare Tunnel HTTPS**, **local HTTPS**, or an explicit **no-certificate/HTTP** exception. It saves the choice in ignored `config/https.local.json`. Change it with `bash scripts/prodstart.bash --configure-https`.

- **Let's Encrypt:** enter a domain you control, point its A/AAAA records at the server, and open/forward TCP 80 and 443. Caddy obtains and renews the certificate while running. The script offers to install Caddy and grant low-port binding permission. Stop any conflicting web server first; do not run the whole app as root.
- **Cloudflare Tunnel:** create a Cloudflare Origin Certificate for the exact public hostname. Install both Cloudflare Origin CA roots on the server with `sudo bash scripts/install-cloudflare-origin-ca.bash`; it creates `/etc/cloudflare/origin-ca.pem`. Make the Origin Certificate and private key readable by the app account (the setup defaults are `/etc/easyplu/origin.pem` and `/etc/easyplu/origin-key.pem`). The wizard checks that the key matches the certificate and the CA bundle is valid. Caddy listens only on `127.0.0.1` (default port `8443`), disables the unused port-80 redirect, and presents the Origin Certificate. For the Tunnel's published application, use service URL `https://127.0.0.1:8443`; under **TLS**, set **Origin Server Name** to the public hostname and **CA Pool** to `/etc/cloudflare/origin-ca.pem`. Keep **No TLS Verify** disabled. If the site should be public, do not enable **Validate Access JWT** or attach an Access policy. The wizard prints these values after setup. Cloudflare handles visitor HTTPS at the edge; the Tunnel connection is separately encrypted.
- **Local HTTPS:** enter the hostname or LAN IP you will use (default port 8443). Caddy creates a local CA; trust `var/caddy-data/caddy/pki/authorities/local/root.crt` on each device to remove browser warnings. Only distribute that public certificate, never CA/private keys. Local mode does not require public DNS or internet port forwarding.
- **No certificate:** HTTP only; credentials are unencrypted unless you supply your own HTTPS proxy. Defaults to loopback. This is an explicit exception to HTTPS, not a secure public deployment.

Caddy forwards HTTPS to Next.js over loopback; FastAPI also stays on loopback. All HTTPS modes preserve streaming progress and use secure owner cookies. Caddy state and certificates live in ignored `var/`; retain them across restarts for renewals. Optional settings: `FRONTEND_HOST` (HTTP mode only), `FRONTEND_PORT`, `BACKEND_PORT`, and `API_BASE_URL`.

For a locally managed Tunnel, adapt [`config/cloudflared.example.yml`](../config/cloudflared.example.yml), keep the credentials outside the checkout, and use the installed CA bundle path; then validate it with `cloudflared tunnel ingress validate`. For a remotely managed Tunnel, add a published application for the hostname and use the printed origin TLS settings. Confirm the Cloudflare zone is Active and the hostname is assigned to this Tunnel so Cloudflare creates the DNS record. DNS resolution can be checked with `dig A your-hostname @1.1.1.1 +short`; an empty result means fix the zone, nameservers, or Tunnel hostname route before debugging the origin.

**Development HTTPS:** run `bash scripts/devstart.bash --https`. Its first run offers the same certificate choices and saves them separately in ignored `config/dev-https.local.json`; use `--configure-https` to change the choice. The Cloudflare Tunnel option has the same loopback-only HTTPS origin and certificate-validation requirements as production. Run plain `bash scripts/devstart.bash` only for local HTTP development.

**Linux background/startup:** production startup can prompt for a run mode or accept `--background` / `--startup`; development accepts the same flags (and optionally `--https`), for example `bash scripts/devstart.bash --background`. Both use separate user systemd services; startup mode asks to enable lingering so it runs at boot before login. Production setup/build happens interactively first. Stop production with `systemctl --user stop easyplu-solver`; stop development with `systemctl --user stop easyplu-solver-dev`; view logs with `journalctl --user -u easyplu-solver -f` or `journalctl --user -u easyplu-solver-dev -f`. Disable autostart with `systemctl --user disable easyplu-solver` or `systemctl --user disable easyplu-solver-dev`, respectively. Requires systemd and an available user session bus. Keep the checkout and Python environment in place.

| Setting | Default |
| --- | --- |
| Frontend | Port `3000` |
| Backend | Port `8000` |
| `API_BASE_URL` | `http://127.0.0.1:8000` — server-side frontend setting |

To use a different backend, set `API_BASE_URL` in `frontend/.env.local` and restart the frontend.

Limits: **2 active jobs**, **3 admissions/minute/IP and 3 starts/minute/IP**, **2 pending requests/IP**, **10 SMS submissions/minute/IP**, and **10 minutes/job**. Backend settings: `MAX_ACTIVE_JOBS`, `JOB_STARTS_PER_MINUTE`, `SMS_SUBMISSIONS_PER_MINUTE`, and `MAX_JOB_SECONDS`. Deadline cancellation takes effect after in-flight operations return; slots remain occupied until cleanup.

Run **one backend worker**. A local process lock rejects a second worker against the same checkout (Linux/macOS); multiple replicas require shared storage. Local proxied clients share one IP bucket. Separate device buckets require a trusted proxy that overwrites a client-IP header: set frontend `EDGE_CLIENT_IP_HEADER` and backend `TRUST_EDGE_CLIENT_IP=1`. Keep trust disabled without that proxy.

PLU numbers are decrypted from execution items and kept in memory for each test. SSO saves browser state in `var/auth/mylidl_session.json` only when development debugging and `session_state` are explicitly enabled (off by default, owner-only permissions); debug artifacts go into `var/debug/`. Keep session files and debug captures private. Disabling session saving does not delete previously saved files.

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

## Self-service automatic tests

After a successful **direct EasyPLU email/password test**, open **Tools → Automatic tests** within one minute of finishing the test. Read the warning and check the agreement box, then choose **Save credentials and enable tests** to save encrypted EasyPLU credentials, or **Disable automatic tests** to delete the enrollment. Lidl SSO enrollment is disabled; no SSO credentials, tokens, or cookies are retained by this scheduler. Existing token-based enrollments are removed when the backend starts; enroll again using direct EasyPLU login.

The backend runs opted-in knowledge tests while it is running, using the interval and account delay from `config/scheduled-tests.json` (one hour and 25 seconds by default). Each run performs a fresh EasyPLU login and checks that its account ID matches the enrolled account before starting the test. Errors pause scheduling until another successful interactive test and re-enrollment. No separate scheduler command is needed. After a restart or one minute, complete another direct EasyPLU test to manage your account's schedule in that browser.

Email/password credentials are Fernet encrypted in the private, ignored `var/schedules/accounts.sqlite3`. Pending enrollment credentials are also encrypted in server memory. The separate encryption key defaults to `~/.config/easyplu-solver/schedule.key`, outside the checkout, created automatically with mode 600. On backend startup an existing checkout `.schedule-key` is moved there without changing its value, preserving enrollments; conflicting keys stop startup rather than discarding credentials. **Keep this key separate from database backups.** For stronger separation, set `SCHEDULE_KEY_FILE` to an absolute, private key file outside the checkout (paths inside the checkout are rejected), provisioned through an OS credential or secrets service; its contents must be a Fernet key. The backend needs access to that key for unattended login, so compromise of the running server account can still expose credentials. Losing or replacing the key requires re-enrollment. API key rotation does not change the credential encryption key.

Removal deletes the encrypted database entry and requests cancellation of any running automatic test; already submitted answers cannot be undone. Copies in backups or manually exported database fields are outside application deletion. The legacy CLI scheduler remains independent and uses its existing credentials file; remove its entries separately to avoid duplicate runs.

## PLU training handbook

The web interface’s **Download PLU catalog (PDF)** button downloads the categorized handbook from the current cache, without a CLI login. Every top-level test refreshes the catalog using its authenticated session before running, including PLU checking mode. A failed refresh leaves the previous cache available and allows the test to continue. Backend dependencies include the PDF libraries. Repeat downloads reuse the latest PDF in server memory until product data changes or the backend restarts. PDF-ready images are cached on disk, avoiding repeated resizing and compression. PDF rendering uses a separate lock so catalogue updates can continue during exports.

The catalogue tool fetches PLU numbers, product names and images, groups them by category, and creates an A4 PDF. Names prefer the Slovenian translation and fall back to the German (`DE`) entry when Slovenian is unavailable. Every page shows its category in the top-left. Its generator in `backend/catalog/` is shared by the web interface and optional CLI.

Category names use the platform translation when available, with Slovenian fallbacks for the known vegetable, bakery, fruit, and nut category IDs.
Each category has its own color and vector icon in the page heading and product cards for faster visual recognition.

```bash
.venv/bin/python -m pip install -r backend/requirements.txt
.venv/bin/python scripts/export-plu-catalog.py --login-method easyplu
```

Run the exporter as your normal user, without `sudo`. Use `--login-method sso` for Lidl SSO; the terminal asks for the SMS code. Passwords are prompted securely and are not stored. The default output is `var/plu-catalog/plu-catalog.pdf`; use `--output FILE.pdf` to change it.

Each run compares live products with the ignored runtime cache `var/plu-catalog/cache.json`. On a fresh checkout, the tracked `data/catalog-seed.json` supplies the initial snapshot without overwriting existing local cache data. Live PLU, name, category and image changes update the cache and its UTC `updated_at` timestamp automatically. Set a product's `"ignore"` field to `true` to preserve its cached values when EasyPLU contains outdated data. Products temporarily missing from the live response remain cached. Use `--cache FILE.json` to select another cache file.

> [!CAUTION]
> The included seed contains Slovenian PLUs and is only a dated snapshot. Check its top-level `updated_at` value before using it for training. Run a test in the web interface to refresh it for your own store and market.

Items without an extractable Slovenian name are saved in full to the ignored `var/plu-catalog/missing-names.json` for debugging, even if the export fails. Use `--missing-names FILE.json` to change its location.



## Project layout

- `frontend/` — Next.js interface and API proxy. Feature components live in `components/login/`, `components/scheduling/`, and `components/layout/`; `components/ui/` holds shared UI primitives. Server helpers live in `lib/server/`.
- `backend/app.py` — FastAPI setup, middleware, and router registration; launch with `uvicorn backend.app:app`.
- `backend/api/` — feature routers and request schemas.
- `backend/auth/` — direct EasyPLU login, interactive Lidl SSO, and the job-local upstream client.
- `backend/tests_runner/` — test execution, decryption, OTP, and progress streaming.
- `backend/catalog/` — collection, cache persistence, safe image downloads, PDF rendering, and export orchestration.
- `backend/scheduling/` — enrollment service, SQLite repository, encryption/key migration, settings, and worker.
- `backend/infrastructure/` — request limits, cancellation, lifecycle, logging, and errors.
- `backend/requirements.txt` — the single Python dependency definition, including PDF libraries.
- `cli/` — optional catalogue exporter and legacy batch scheduler. Existing `scripts/export-plu-catalog.py` and `scripts/scheduled-tests.py` commands remain compatibility wrappers.
- `scripts/` — installation, startup, access setup, and deployment helpers. Startup commands remain unchanged.
- `config/` — non-secret settings; `data/` — tracked catalogue seed; `var/` — ignored runtime data.
- `tests/` — tests grouped by feature; run `.venv/bin/python -m unittest discover -s tests -v`.

Use npm and the sole `frontend/package-lock.json` for frontend dependencies. To build: `npm --prefix frontend run build`. The local `.env.local` moved with the frontend directory. Existing databases, runtime catalog overrides, and the external encryption key retain their locations.

See [architecture.md](architecture.md) for responsibilities and migration notes.

---

Independent educational project; not affiliated with Lidl or Knowledge Hero. Respect the platform's terms of service.

## Download security and proxy client addresses

PDF downloads use separate admission limits (one active download, ten starts per minute per client address) so they do not consume test slots or test rate limits. Without a configured trusted edge, requests conservatively share the proxy address. The supplied Caddy startup config overwrites `X-Real-IP`, sets `EDGE_CLIENT_IP_HEADER=x-real-ip` for Next.js and `TRUST_EDGE_CLIENT_IP=1` for the backend, and keeps Next.js bound to loopback. For an external proxy, use that same arrangement and prevent direct public access to Next.js; never trust a client-supplied forwarding header. The backend accepts the forwarded address only from a loopback peer.

Product image downloads allow only HTTPS on `easy-plu.knowledge-hero.com` port 443, reject non-public DNS addresses, and revalidate each redirect (maximum three followed redirects). They use a separate session without login credentials or environment proxy settings. The 10 MiB limit is enforced during streaming, including responses without Content-Length.
