from pathlib import Path
import secrets

root = Path(__file__).resolve().parents[1]
key_path = root / ".api-key"
if not key_path.exists():
    key_path.write_text(secrets.token_urlsafe(48) + "\n")
key_path.chmod(0o600)
key = key_path.read_text().strip()
if not key:
    raise SystemExit(".api-key is empty; supply a key before continuing")

env_path = root / "front" / ".env.local"
content = env_path.read_text() if env_path.exists() else ""
lines = content.splitlines()
lines = [line for line in lines if not line.startswith(("API_INTERNAL_KEY=", "API_ACCESS_USER=", "API_ACCESS_PASSWORD="))]
lines.append("API_INTERNAL_KEY=" + key)
env_path.write_text("\n".join(lines) + "\n")
env_path.chmod(0o600)
print("Private backend key configured. Restart both servers. The app remains open.")