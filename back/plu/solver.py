import random
import requests
import time

from back.auth.ssohandler import extract_user_id, sso_authenticate
from back.core.debug import log
from back.core.errors import client_error, EasyPluAuthenticationError, PluDecryptionError
from back.plu.decryption import DecryptedProducts
from back.runtime.jobs import SessionProxy, check_cancelled, wait, JobCancelled

BASE_URL = "https://easy-plu.knowledge-hero.com/api/plu"
LOGIN_URL = f"{BASE_URL}/login"
CREATE_SESSION_URL = f"{BASE_URL}/plu-learn/create-new-session"
EXECUTION_ITEMS_URL_TEMPLATE = f"{BASE_URL}/plu-learn/{{session_id}}/execution-items"
START_EXECUTION_URL_TEMPLATE = f"{BASE_URL}/plu-learn/{{session_id}}/start-execution"
UPDATE_ANSWER_URL_TEMPLATE = f"{BASE_URL}/plu-learn/{{item_id}}/update"
RESULT_URL_TEMPLATE = f"{BASE_URL}/plu-learn/{{session_id}}/result"

session = SessionProxy()


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


def create_session(execution_type, user_id):
    debug_print(f"Creating session for user_id={user_id}, execution_type={execution_type}")
    payload = {
        "product_category_id": None,
        "count_selection": 154,
        "user_id": user_id,
        "language_id": 1,
        "execution_type": execution_type,
        "execution_subtype": 0,
        "is_gold_plu": False,
        "new_plu": None,
        "plu_current_count": 1,
        "top_article_active": False,
        "attribute_group_id": None,
        "ean_active": False
    }
    r = session.post(CREATE_SESSION_URL, json=payload)
    r.raise_for_status()
    session_id = r.json()["data"]["session_id"]
    debug_print(f"Created session_id={session_id}")
    return session_id


def fetch_execution_items(session_id, execution_type=1, products=None):
    debug_print(f"Fetching execution items for session_id={session_id}")
    url = EXECUTION_ITEMS_URL_TEMPLATE.format(session_id=session_id)
    payload = {"incrementCurrent": False, "activeLanguageLocale": "SI", "execution_type": execution_type}
    r = session.post(url, json=payload)
    r.raise_for_status()
    items = r.json()["data"]["items"]
    debug_print(f"Fetched {len(items)} items")
    if products is not None:
        products.update(session_id, items)
    return items


def start_execution(session_id):
    debug_print(f"Starting execution for session_id={session_id}")
    url = START_EXECUTION_URL_TEMPLATE.format(session_id=session_id)
    session.post(url, json={}).raise_for_status()


def submit_answers(items, wrong_count=0, progress_callback=None, products=None):
    debug_print(f"Submitting answers, wrong_count={wrong_count}")
    if products is None:
        products = DecryptedProducts()
        products.update(None, items)
    total = len(items)
    wrong_indices = set(random.sample(range(total), wrong_count))
    detailed_results = []

    for i, item in enumerate(items):
        check_cancelled()
        plu_number_id = item["pluNumberId"]
        correct_plu = products.get(plu_number_id)
        if correct_plu is None:
            raise PluDecryptionError()

        if i in wrong_indices:
            given_plu = "0000"
            correct_flag = False
        else:
            given_plu = correct_plu
            correct_flag = True

        payload = {
            "execution_type": 3,
            "given_plu_number": given_plu,
            "plu_number_id": plu_number_id,
            "answer": {"correct": correct_flag}
        }
        url = UPDATE_ANSWER_URL_TEMPLATE.format(item_id=item["id"])
        debug_print(
            f"Submitting item {i+1}/{total}: item_id={item['id']}, "
            f"plu_number_id={plu_number_id}, decrypted={correct_plu is not None}",
            "payload:", payload,
        )
        response = session.put(url, json=payload)
        if not response.ok:
            debug_print(
                f"Answer update failed: HTTP {response.status_code}",
                "response:", response.text[:4000],
            )
        response.raise_for_status()
        detailed_results.append({
            "item_id": item["id"],
            "plu_number_id": plu_number_id,
            "given_plu": given_plu,
            "correct": correct_flag
        })
        debug_print(f"Submitted item {i+1}/{total}: given_plu={given_plu}, correct={correct_flag}")
    
        if progress_callback:
            progress_callback(i + 1, total)

    return detailed_results


def submit_result(session_id, user_id):
    debug_print(f"Submitting final result for session_id={session_id}")
    url = RESULT_URL_TEMPLATE.format(session_id=session_id)
    payload = {"user_id": user_id}
    r = session.post(url, json=payload)
    r.raise_for_status()
    data = r.json().get("data", {})
    debug_print("Raw result data:", data)

    # Extract only logical useful fields
    logical_result = {
        "final_result": data.get("final_result"),
        "total_user_points": data.get("result", {}).get("total_user_points"),
        "max_points": data.get("result", {}).get("max_points"),
        "required_points": data.get("result", {}).get("required_points"),
        "user_knowledge": data.get("user_knowledge"),
        "user_ranking_in_store": data.get("user_ranking_in_store"),
        "earned_gold_plus": data.get("earned_gold_plus"),
        "total_gold_plus": data.get("total_gold_plus"),
        "plu_execution_session_item_count": data.get("executionSession", {}).get("plu_execution_session_item_count"),
        "total_execution_time": data.get("result", {}).get("total_execution_time")
    }
    debug_print("Logical result extracted:", logical_result)
    return logical_result


def run_session(
    email: str,
    password: str,
    target_score: int = None,
    progress_callback=None,
    login_method: str = "easyplu",
    otp_callback=None,
    user_id=None,
):
    def emit_progress(stage: str, progress: float, message: str = "", extra_data: dict = None):
        check_cancelled()
        if progress_callback:
            data = {
                "stage": stage,
                "progress": progress,
                "message": message,
                **(extra_data or {})
            }
            progress_callback(data)
    
    try:
        emit_progress("initializing", 0, "Začenjanje seje...")
        debug_print("[PLU] Source: decrypt")
        products = DecryptedProducts()
        debug_print("Running test session...")
        
        if user_id is None:
            method_label = "Lidl SSO" if (login_method or "").lower() == "sso" else "EasyPLU"
            emit_progress("logging_in", 10, f"Prijavljanje ({method_label})...")
            user_id = login(email, password, login_method=login_method, otp_callback=otp_callback)
            debug_print(f"Logged in, user_id={user_id}")
        else:
            debug_print(f"Reusing authenticated user_id={user_id}")
        
        emit_progress("creating_session", 30, "Ustvarjanje seje...")
        test_session_id = create_session(execution_type=3, user_id=user_id)
        
        emit_progress("starting_execution", 40, "Zaganjanje izvajanja...")
        start_execution(test_session_id)
        wait(1)
        
        emit_progress("fetching_items", 50, "Pridobivanje elementov...")
        items = fetch_execution_items(test_session_id, execution_type=3, products=products)
        
        wrong_count = 0
        if target_score is not None:
            total_items = len(items)
            correct_needed = int(total_items * (target_score / 100))
            wrong_count = total_items - correct_needed
        
        emit_progress("submitting_answers", 60, "Oddajanje odgovorov...", {"total_items": len(items), "submitted": 0})
        detailed_results = submit_answers(items, wrong_count=wrong_count, products=products, progress_callback=lambda current, total: emit_progress(
            "submitting_answers",
            60 + (current / total) * 30,
            f"Oddajanje odgovorov: {current}/{total}",
            {"total_items": total, "submitted": current}
        ))
        
        emit_progress("submitting_result", 90, "Oddajanje rezultata...")
        result_data = submit_result(test_session_id, user_id)
        
        total_items = len(detailed_results)
        correct_items = sum(1 for r in detailed_results if r["correct"])
        incorrect_items = total_items - correct_items
        average_score = (correct_items / total_items) * 100 if total_items else 0
        
        debug_print(f"Total items: {total_items}")
        debug_print(f"Correct items: {correct_items}")
        debug_print(f"Incorrect items: {incorrect_items}")
        debug_print(f"Average score: {average_score}")
        
        emit_progress("completed", 100, "Končano!", {
            "total_items": total_items,
            "correct_items": correct_items,
            "incorrect_items": incorrect_items,
            "average_score": average_score
        })
        
        return {
            **result_data,
            "user_id": user_id,
            "total_items": total_items,
            "correct_items": correct_items,
            "incorrect_items": incorrect_items,
            "average_score": average_score,
            "detailed_results": detailed_results
        }
    except JobCancelled:
        raise
    except Exception as e:
        debug_print("Session failed:", e)
        emit_progress("error", 0, client_error(e))
        raise
