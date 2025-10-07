import playwright.sync_api
from getpass import getpass
import json
import warnings
import requests

warnings.filterwarnings('ignore', category=playwright.sync_api.Error)

FEDERATION_URL = "https://federation.auth.lidl.com/nidp/app/login?sid=0&sid=0"
MYLIDL_PORTAL_URL = "https://mylidl.lidl.com/sap/bc/ui5_ui5/ui2/ushell/shells/abap/Fiorilaunchpad.html?sov-ui-flp=true#Shell-home"
RANKING_API_URL = "https://easy-plu.knowledge-hero.com/api/plu/knowledge/user/ranking-by-store"

def dynamic_login_and_fetch_token(gps_number, password, otp):
    print("\n--- Starting Headless Browser Flow ---")
    with playwright.sync_api.sync_playwright() as p:
        browser = p.chromium.launch(headless=True, ignore_https_errors=True)
        context = browser.new_context()
        page = context.new_page()
        bearer_token = None

        def capture_token(route, request):
            nonlocal bearer_token
            if RANKING_API_URL in request.url:
                auth_header = request.headers.get("authorization")
                if auth_header and auth_header.startswith("Bearer "):
                    bearer_token = auth_header.split(" ")[1]
                    route.abort()
                else:
                    route.continue_()
            else:
                route.continue_()

        context.route("**/*", capture_token)
        print("1-2. Submitting GPS credentials...")
        page.goto(FEDERATION_URL, wait_until="networkidle")
        page.click('input[value="Credential"]')
        page.fill('input[name="Ecom_User_ID"]', gps_number)
        page.fill('input[name="Ecom_Password"]', password)
        page.click('input[type="submit"]')
        page.wait_for_selector('input[value="SMS_OTP:1"]')
        print("3. Triggering SMS OTP...")
        page.click('input[value="SMS_OTP:1"]')
        print(f"4. Submitting OTP: {otp}")
        page.fill('input[name="SMSPassword"]', otp)
        page.click('input[type="submit"]')
        print("5-6. Performing SSO and acquiring JWT token...")
        page.goto(MYLIDL_PORTAL_URL)
        page.wait_for_selector('a:has-text("easyPLU")')
        page.goto(RANKING_API_URL.replace("/api/plu/knowledge/user/ranking-by-store", "/user-ranking"))
        page.wait_for_timeout(3000)
        if not bearer_token:
            print("verify=TrueToken acquisition failed. Final page URL:", page.url)
            return None, "Failed to capture Bearer Token."
        print("verify=TrueJWT Token acquired successfully.")
        ranking_payload = {"first": 0, "rows": 20}
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {bearer_token}",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
            "Referer": RANKING_API_URL.replace("/api/plu/knowledge/user/ranking-by-store", "/user-ranking")
        }
        print("7. Verifying login with the acquired token...")
        r = requests.post(RANKING_API_URL, headers=headers, json=ranking_payload, verify=False)
        r.raise_for_status()
        return r.json(), None

if __name__ == "__main__":
    print("=" * 65)
    print("=== Playwright: Dynamic JWT Acquisition and Verification ===")
    print("=" * 65)
    gps_number = input("Enter GPS number (Ecom_User_ID): ")
    password = getpass("Enter password: ")
    otp_code = input("Enter OTP from SMS: ")
    try:
        data, error_message = dynamic_login_and_fetch_token(gps_number, password, otp_code)
        if error_message:
            print(f"\nverify=TrueFAILED: {error_message}")
        else:
            print("\n" + "=" * 65)
            print("FINAL RESULT: End-to-end flow completed and Bearer Token verified.")
            print("\n--- RANKING DATA RESPONSE ---")
            print(json.dumps(data, indent=4))
            print("=" * 65)
    except requests.exceptions.HTTPError as e:
        print(f"\nverify=TrueLogin Failed: HTTP Error occurred. Status Code: {e.response.status_code}")
        print(f"Response URL: {e.response.url}")
        print("\nEnsure the submitted GPS/password/OTP were correct.")
    except playwright.sync_api.Error as e:
        print(f"\nverify=TruePlaywright Error: {e}")
        print("Please ensure Playwright is installed correctly (`pip install playwright` and `playwright install`).")
    except Exception as e:
        print(f"\nverify=TrueAn unexpected error occurred during the process: {e}")
