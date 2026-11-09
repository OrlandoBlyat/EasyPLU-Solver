"""EasyPLU direct login and interactive SSO exchange."""
from backend.auth.lidl_sso import extract_user_id, sso_authenticate
from backend.infrastructure.logging import log
from backend.infrastructure.errors import EasyPluAuthenticationError
from backend.infrastructure.jobs import JobCancelled
from backend.auth.client import BASE_URL, session

LOGIN_URL = f"{BASE_URL}/login"


def debug_print(*args):
    log("solver", *args)


def apply_auth(token: str, user_id, cookies=None):
    session.headers.update({"Authorization": f"Bearer {token}", "Accept": "application/json"})
    if cookies:
        for cookie in cookies:
            name = cookie.get("name")
            value = cookie.get("value")
            if not name:
                continue
            kwargs = {"path": cookie.get("path") or "/"}
            domain = (cookie.get("domain") or "").lstrip(".")
            if domain:
                kwargs["domain"] = domain
            session.cookies.set(name, value, **kwargs)
    debug_print(f"Authenticated as user_id={user_id}")
    return user_id


def login_easyplu(email: str, password: str):
    debug_print("Logging in via EasyPLU...")
    payload = {"email": email, "password": password}
    r = session.post(LOGIN_URL, json=payload)
    if r.status_code in (401, 403):
        raise EasyPluAuthenticationError("EasyPLU credentials rejected")
    r.raise_for_status()
    data = r.json()
    debug_print("Login response keys:", list(data))
    token = data.get("api_token")
    if not token:
        raise RuntimeError("EasyPLU login succeeded but no api_token was returned")
    user_id = data.get("user", {}).get("id") or data.get("id")
    return apply_auth(token, user_id)


def login_sso(username: str, password: str, otp_callback=None):
    debug_print("Logging in via Lidl SSO...")
    result = sso_authenticate(username, password, otp_callback=otp_callback)
    token = result.get("token")
    user_id = result.get("user_id")
    if not token:
        raise RuntimeError("SSO login succeeded but no api_token was captured")
    user_id = apply_auth(token, user_id, cookies=result.get("cookies"))
    if not user_id:
        user_id = extract_user_id(result.get("body"))
    if not user_id:
        for method in ("get", "post"):
            try:
                r = getattr(session, method)(f"{BASE_URL}/knowledge/user", json={}, timeout=30)
                debug_print(
                    f"knowledge/user {method.upper()}: status={r.status_code}, "
                    f"content_type={r.headers.get('content-type')}"
                )
                if r.ok:
                    body = r.json()
                    debug_print(
                        "knowledge/user response keys:",
                        list(body) if isinstance(body, dict) else type(body).__name__,
                    )
                    user_id = extract_user_id(body)
                    debug_print(f"knowledge/user user ID present: {bool(user_id)}")
                    if user_id:
                        break
            except JobCancelled:
                raise
            except Exception as e:
                debug_print(f"knowledge/user {method} failed: {e}")
    if not user_id:
        raise RuntimeError("SSO login succeeded but user_id was not found")
    debug_print(f"SSO login complete, user_id={user_id}")
    return user_id


def login(email: str, password: str, login_method: str = "easyplu", otp_callback=None):
    method = (login_method or "easyplu").lower()
    if method == "sso":
        return login_sso(email, password, otp_callback=otp_callback)
    if method in ("easyplu", "easy-plu"):
        return login_easyplu(email, password)
    raise ValueError(f"Unknown login_method: {login_method}")

