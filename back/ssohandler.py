
import getpass
import json
import os
import time
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
from debug import ARTIFACT_DIRECTORY, enabled, log as debug_log, log_exception
from jobs import check_cancelled, JobCancelled
from errors import SsoAuthenticationError

START_URL = (
    "https://mylidl.lidl.com/sap/bc/ui5_ui5/ui2/"
    "ushell/shells/abap/Fiorilaunchpad.html"
)

API_URL = (
    "https://easy-plu.knowledge-hero.com/"
    "api/plu/knowledge/user"
)

STATE_FILE = Path("mylidl_session.json")
DEBUG_DIR = ARTIFACT_DIRECTORY

LOGIN_TIMEOUT = 150
TILE_TIMEOUT = 60
API_TIMEOUT = 90



def log(message):
    debug_log("sso", message)


def safe_url(url):
    parsed = urlsplit(url)
    if not parsed.scheme:
        return url
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"


def save_debug(page, name):
    if not (enabled("sso") and enabled("screenshots")):
        return
    try:
        DEBUG_DIR.mkdir(parents=True, exist_ok=True)
        path = DEBUG_DIR / f"{name}.png"
        page.screenshot(
            path=str(path),
            full_page=True,
            timeout=5000
        )
        log(f"Screenshot saved: {path}")
    except JobCancelled:
        raise
    except Exception as e:
        log(f"Screenshot failed: {e}")

def fill_first(page, selectors, value, label):
    log(f"Looking for {label} field")

    for selector in selectors:
        try:
            field = page.locator(selector).first

            if field.count() and field.is_visible():
                log(f"Found {label}: {selector}")
                field.fill(value, timeout=10000)
                log(f"{label} filled")
                return True

        except JobCancelled:
            raise
        except Exception as e:
            log(
                f"Selector error ({selector}): "
                f"{type(e).__name__}: {e}"
            )

    return False


def submit(page):
    log("Searching for submit button")

    selectors = [
        'button[type="submit"]',
        'input[type="submit"]',
        'button:has-text("LOGIN")',
        'button:has-text("Continue")',
        'button:has-text("Next")'
    ]

    for selector in selectors:
        try:
            button = page.locator(selector).first

            if button.count() and button.is_visible():
                log(f"Clicking submit: {selector}")
                button.click(timeout=10000)
                return True

        except JobCancelled:
            raise
        except Exception as e:
            log(f"Submit error: {e}")

    try:
        page.locator("input:visible").last.press("Enter")
        return True
    except JobCancelled:
        raise
    except Exception as e:
        log(f"Enter fallback failed: {e}")
        return False

def inspect_page(page):
    return page.evaluate("""() => {
        const inputs = Array.from(
            document.querySelectorAll("input")
        );

        const visible = el =>
            !!(el.getClientRects().length);

        const body = document.body;

        const text = body ? body.innerText : "";

        const hasEasyPLU = Array.from(
            document.querySelectorAll(
                '[role="button"], .sapMGT'
            )
        ).some(el =>
            visible(el) &&
            (
                (el.getAttribute("aria-label") || "") +
                (el.innerText || "")
            ).includes("easyPLU")
        );

        return {
            url: location.origin + location.pathname,

            inputs: inputs.map(el => ({
                name: el.name,
                type: el.type,
                visible: visible(el)
            })),

            hasPassword: inputs.some(el =>
                el.type === "password" &&
                visible(el)
            ),

            hasSMS: inputs.some(el =>
                (
                    el.name === "SMSPassword" ||
                    el.autocomplete === "one-time-code"
                ) && visible(el)
            ),

            hasAuthChain: inputs.some(el =>
                el.name === "AuthChain"
            ),

            hasSMSOption: text.includes("SMS OTP"),

            hasEasyPLU: hasEasyPLU,

            hasLoginError: /invalid password|incorrect password|authentication failed|login failed/i.test(text)
        };
    }""")


def select_sms_method(page):
    log("Selecting SMS OTP authentication method")

    selectors = [
        'a:has-text("SMS OTP")',
        'button:has-text("SMS OTP")',
        'label:has-text("SMS OTP")',
        '[role="button"]:has-text("SMS OTP")',
        'input[type="radio"] + label:has-text("SMS OTP")'
    ]

    for selector in selectors:
        try:
            target = page.locator(selector).first

            if target.count() and target.is_visible():
                log(f"Found SMS OTP selector: {selector}")
                target.click(timeout=10000)
                log("SMS OTP clicked")
                return True

        except JobCancelled:
            raise
        except Exception as e:
            log(f"SMS selector error: {type(e).__name__}: {e}")

    try:
        target = page.get_by_text(
            "SMS OTP",
            exact=True
        ).first

        if target.count() and target.is_visible():
            log("Clicking exact SMS OTP text")
            target.click(timeout=10000)
            return True

    except JobCancelled:
        raise
    except Exception as e:
        log(f"SMS text click error: {e}")

    # Debug the clickable element structure.
    try:
        elements = page.get_by_text(
            "SMS OTP",
            exact=True
        ).evaluate_all("""elements => elements.map(el => ({
            tag: el.tagName,
            id: el.id,
            className: String(el.className).slice(0, 120),
            parentTag: el.parentElement?.tagName,
            parentClass: String(
                el.parentElement?.className || ""
            ).slice(0, 120)
        }))""")

        log("SMS OTP element structure:")
        log(json.dumps(elements, indent=2))

    except JobCancelled:
        raise
    except Exception as e:
        log(f"SMS inspection error: {e}")

    return False


def extract_user_id(body):
    if not isinstance(body, dict):
        return None

    user = body.get("user")
    data = body.get("data")

    if body.get("id"):
        return body.get("id")
    if isinstance(user, dict) and user.get("id"):
        return user.get("id")
    if isinstance(data, dict):
        nested_user = data.get("user")
        if data.get("id"):
            return data.get("id")
        if isinstance(nested_user, dict) and nested_user.get("id"):
            return nested_user.get("id")
    return None


def extract_token(headers, body):
    auth = headers.get("authorization") or headers.get("Authorization") or ""
    if auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()
    if auth:
        return auth.strip()
    if isinstance(body, dict):
        return (
            body.get("api_token")
            or body.get("token")
            or (body.get("data") or {}).get("api_token")
            or (body.get("data") or {}).get("token")
        )
    return None


def login(page, username, password, otp_callback=None):
    log("Navigating to MyLidl")

    page.goto(
        START_URL,
        wait_until="domcontentloaded",
        timeout=60000
    )

    log(f"Initial URL: {safe_url(page.url)}")

    start = time.monotonic()

    credentials_submitted = False
    sms_method_selected = False
    sms_submitted = False

    last_state = None
    last_report = -1

    while time.monotonic() - start < LOGIN_TIMEOUT:
        check_cancelled()
        elapsed = int(time.monotonic() - start)

        try:
            info = inspect_page(page)

            if info["hasEasyPLU"]:
                log("SUCCESS: easyPLU tile visible")
                return

            if info["hasLoginError"]:
                raise SsoAuthenticationError(
                    "Login page reports an authentication error"
                )

            if info["hasSMS"]:
                state = "SMS_CHALLENGE"

            elif (
                info["hasAuthChain"]
                and info["hasSMSOption"]
            ):
                state = "AUTH_CHAIN"

            elif info["hasPassword"]:
                state = "LOGIN_FORM"

            elif "mylidl.lidl.com" in info["url"]:
                state = "MYLIDL_LOADING"

            else:
                state = "UNKNOWN_AUTH_STEP"

            if state != last_state:
                log(f"STATE CHANGED: {state}")
                log(f"URL: {info['url']}")
                log(
                    "Input fields: " +
                    json.dumps(info["inputs"])
                )
                last_state = state

            if elapsed // 5 != last_report:
                last_report = elapsed // 5
                log(
                    f"Waiting: {elapsed}/{LOGIN_TIMEOUT}s "
                    f"| state={state}"
                )

            if (
                state == "LOGIN_FORM"
                and not credentials_submitted
            ):
                log("Filling login credentials")

                if not fill_first(
                    page,
                    ['input[name="Ecom_User_ID"]'],
                    username,
                    "username"
                ):
                    raise RuntimeError(
                        "Username field not found"
                    )

                if not fill_first(
                    page,
                    ['input[name="Ecom_Password"]'],
                    password,
                    "password"
                ):
                    raise RuntimeError(
                        "Password field not found"
                    )

                credentials_submitted = True

                if not submit(page):
                    raise RuntimeError(
                        "Could not submit login form"
                    )

                log("Credentials submitted")


            elif (
                state == "AUTH_CHAIN"
                and not sms_method_selected
            ):
                log("SMS OTP method selection detected")

                if not select_sms_method(page):
                    save_debug(
                        page,
                        "sms_method_selection_failed"
                    )
                    raise RuntimeError(
                        "Could not select SMS OTP method"
                    )

                sms_method_selected = True
                log("SMS OTP method selected")


            elif (
                state == "SMS_CHALLENGE"
                and not sms_submitted
            ):
                log("SMS verification field detected")

                ask_otp = otp_callback or (
                    lambda: input("SMS verification code: ").strip()
                )
                otp = (ask_otp() or "").strip()
                if not otp:
                    raise RuntimeError("SMS verification code is required")

                if not fill_first(
                    page,
                    [
                        'input[name="SMSPassword"]',
                        'input[autocomplete="one-time-code"]'
                    ],
                    otp,
                    "SMS code"
                ):
                    raise RuntimeError(
                        "SMS verification field missing"
                    )

                sms_submitted = True

                if not submit(page):
                    raise RuntimeError(
                        "Could not submit SMS code"
                    )

                log("SMS submitted")

            page.wait_for_timeout(500)

        except (RuntimeError, SsoAuthenticationError, TimeoutError):
            raise

        except JobCancelled:
            raise
        except Exception as e:
            log(
                f"LOGIN LOOP ERROR: "
                f"{type(e).__name__}: {e}"
            )
            page.wait_for_timeout(1000)

    save_debug(page, "login_timeout")

    raise RuntimeError(
        f"Login timed out after {LOGIN_TIMEOUT}s. "
        f"Last state: {last_state}"
    )


def attach_debug_listeners(context):
    if not (enabled("sso") and enabled("browser_events")):
        return

    def on_page(page):
        log(f"NEW PAGE: {safe_url(page.url)}")

        page.on(
            "domcontentloaded",
            lambda: log(
                f"DOM LOADED: {safe_url(page.url)}"
            )
        )

        page.on(
            "framenavigated",
            lambda frame: log(
                f"FRAME NAVIGATED: "
                f"{safe_url(frame.url)}"
            )
            if frame == page.main_frame
            else None
        )

        page.on(
            "pageerror",
            lambda error: log(
                f"PAGE JS ERROR: {str(error)[:200]}"
            )
        )

        page.on(
            "crash",
            lambda: log("PAGE CRASHED")
        )

        page.on(
            "requestfailed",
            lambda request: log(
                f"FAILED REQUEST: "
                f"{safe_url(request.url)} | "
                f"{request.failure}"
            )
            if "federation.auth.lidl.com" in request.url
            else None
        )

        page.on(
            "response",
            lambda response: log(
                f"AUTH HTTP {response.status}: "
                f"{safe_url(response.url)}"
            )
            if (
                "federation.auth.lidl.com" in response.url
                and response.request.is_navigation_request()
            )
            else None
        )

    context.on("page", on_page)

    for page in context.pages:
        on_page(page)

def click_easyplu(page):
    log("Searching for easyPLU tile")

    selectors = [
        '[role="button"][aria-label*="easyPLU"]',
        '.sapMGT:has-text("easyPLU")',
        '[id$="-title-inner"]:has-text("easyPLU")'
    ]

    start = time.monotonic()
    last_report = -1

    while time.monotonic() - start < TILE_TIMEOUT:
        check_cancelled()
        for selector in selectors:
            try:
                tile = page.locator(selector).first

                if tile.count() and tile.is_visible():
                    log(f"Found tile: {selector}")
                    log("Clicking easyPLU")

                    tile.click(timeout=15000)

                    log("Tile clicked")
                    return

            except JobCancelled:
                raise
            except Exception as e:
                log(f"Tile click error: {e}")

        elapsed = int(time.monotonic() - start)

        if elapsed // 5 != last_report:
            last_report = elapsed // 5
            log(
                f"Waiting for tile: "
                f"{elapsed}/{TILE_TIMEOUT}s"
            )

        page.wait_for_timeout(1000)

    save_debug(page, "tile_not_found")
    raise RuntimeError("easyPLU tile not found")


def sso_authenticate(username, password, otp_callback=None):
    """Log in via MyLidl SSO and return EasyPLU api_token + user_id."""
    log("Starting headless MyLidl automation")

    with sync_playwright() as p:
        log("Launching Chromium")

        browser = p.chromium.launch(
            headless=True,
            args=["--disable-dev-shm-usage"]
        )

        context = browser.new_context(
            accept_downloads=False
        )

        context.set_default_timeout(15000)

        page = context.new_page()

        attach_debug_listeners(context)

        api_responses = []
        api_requests = []
        api_failures = []
        captured_headers = {}

        def is_easyplu_api(url):
            return url.split("?")[0].startswith(
                "https://easy-plu.knowledge-hero.com/api/plu"
            )

        def on_request(request):
            if request.url.split("?")[0] == API_URL:
                log(
                    f"API REQUEST: "
                    f"{request.method} "
                    f"{safe_url(request.url)}"
                )
                api_requests.append(request)
            if is_easyplu_api(request.url) and request.headers.get("authorization"):
                captured_headers.update(request.headers)

        def on_response(response):
            if response.url.split("?")[0] == API_URL:
                log(
                    f"API RESPONSE: HTTP {response.status}"
                )
                api_responses.append(response)

        def on_request_failed(request):
            if request.url.split("?")[0] == API_URL:
                log(
                    f"API REQUEST FAILED: "
                    f"{request.failure}"
                )
                api_failures.append(
                    str(request.failure)
                )

        context.on("request", on_request)
        context.on("response", on_response)
        context.on("requestfailed", on_request_failed)

        try:
            login(page, username, password, otp_callback=otp_callback)

            log("Login completed")
            log(f"Current page: {safe_url(page.url)}")

            click_easyplu(page)

            log("Waiting for easyPLU API response")

            start = time.monotonic()
            last_report = -1

            while time.monotonic() - start < API_TIMEOUT:
                check_cancelled()
                elapsed = int(time.monotonic() - start)

                if api_responses:
                    log("API response captured")
                    break

                if elapsed // 5 != last_report:
                    last_report = elapsed // 5

                    log(
                        f"API wait: "
                        f"{elapsed}/{API_TIMEOUT}s | "
                        f"requests={len(api_requests)} | "
                        f"failures={len(api_failures)} | "
                        f"pages={len(context.pages)}"
                    )

                    for i, tab in enumerate(context.pages):
                        log(
                            f"Page {i}: "
                            f"{safe_url(tab.url)}"
                        )

                page.wait_for_timeout(500)

            if not api_responses:
                for i, tab in enumerate(context.pages):
                    save_debug(
                        tab,
                        f"api_timeout_page_{i}"
                    )

                raise RuntimeError(
                    "easyPLU API response not captured. "
                    f"Requests={len(api_requests)}, "
                    f"Failures={api_failures}"
                )

            response = api_responses[-1]

            log(
                f"Parsing API response "
                f"(HTTP {response.status})"
            )

            try:
                body = response.json()
                log("JSON parsed successfully")
            except JobCancelled:
                raise
            except Exception as e:
                log(f"JSON parsing failed: {e}")
                body = response.text()

            if not captured_headers and api_requests:
                captured_headers.update(api_requests[-1].headers)

            token = extract_token(captured_headers, body)
            user_id = extract_user_id(body)
            log(
                f"API response structure: "
                f"{list(body) if isinstance(body, dict) else type(body).__name__}"
            )
            log(f"API user ID present: {bool(user_id)}")

            if not user_id:
                for tab in context.pages:
                    if urlsplit(tab.url).hostname != "easy-plu.knowledge-hero.com":
                        continue
                    try:
                        stored_user_id = tab.evaluate("""() => {
                            const user = JSON.parse(localStorage.getItem('user') || 'null');
                            return user && typeof user === 'object' ? user.id : null;
                        }""")
                        log(f"localStorage user ID present: {bool(stored_user_id)}")
                        if stored_user_id:
                            user_id = stored_user_id
                            break
                    except JobCancelled:
                        raise
                    except Exception as e:
                        log(f"localStorage user lookup failed: {type(e).__name__}")

            cookies = context.cookies()

            if not token:
                raise RuntimeError(
                    "SSO login succeeded but no EasyPLU API token was captured"
                )

            if enabled("session_state"):
                log("Saving browser session")
                # Restrict access before writing cookies and tokens.
                fd = os.open(STATE_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
                try:
                    os.fchmod(fd, 0o600)
                    with os.fdopen(fd, "w") as state_file:
                        fd = None
                        json.dump(context.storage_state(), state_file)
                finally:
                    if fd is not None:
                        os.close(fd)

            log("SUCCESS: easyPLU API captured")

            return {
                "status": response.status,
                "url": response.url,
                "body": body,
                "token": token,
                "user_id": user_id,
                "cookies": cookies,
            }

        except JobCancelled:
            raise
        except Exception as e:
            log(
                f"FATAL ERROR: "
                f"{type(e).__name__}: {e}"
            )

            log_exception("sso")

            for i, tab in enumerate(context.pages):
                log(
                    f"Page {i}: "
                    f"{safe_url(tab.url)}"
                )

                save_debug(
                    tab,
                    f"error_page_{i}"
                )

            raise

        finally:
            log("Closing browser")
            browser.close()


def run():
    username = (
        os.getenv("MYLIDL_USERNAME")
        or input("MyLidl username: ").strip()
    )

    password = (
        os.getenv("MYLIDL_PASSWORD")
        or getpass.getpass("MyLidl password: ")
    )

    result = sso_authenticate(username, password)

    return result


if __name__ == "__main__":
    run()
