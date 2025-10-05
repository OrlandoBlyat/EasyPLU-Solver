import random
import sqlite3
import requests
import os
import time

BASE_URL = "https://easy-plu.knowledge-hero.com/api/plu"
LOGIN_URL = f"{BASE_URL}/login"
CREATE_SESSION_URL = f"{BASE_URL}/plu-learn/create-new-session"
EXECUTION_ITEMS_URL_TEMPLATE = f"{BASE_URL}/plu-learn/{{session_id}}/execution-items"
START_EXECUTION_URL_TEMPLATE = f"{BASE_URL}/plu-learn/{{session_id}}/start-execution"
UPDATE_ANSWER_URL_TEMPLATE = f"{BASE_URL}/plu-learn/{{item_id}}/update"
RESULT_URL_TEMPLATE = f"{BASE_URL}/plu-learn/{{session_id}}/result"

DB_FILE = "plu_items.db"
DEBUG = True  # Set this to False to turn off debug prints
session = requests.Session()


def debug_print(*args):
    if DEBUG:
        print("[DEBUG]", *args)


def login(email: str, password: str):
    debug_print("Logging in...")
    payload = {"email": email, "password": password}
    r = session.post(LOGIN_URL, json=payload)
    r.raise_for_status()
    data = r.json()
    debug_print("Login response:", data)
    token = data.get("api_token")
    user_id = data.get("user", {}).get("id") or data.get("id")
    session.headers.update({"Authorization": f"Bearer {token}", "Accept": "application/json"})
    debug_print(f"Logged in as user_id={user_id}")
    return user_id


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


def fetch_execution_items(session_id, execution_type=1):
    debug_print(f"Fetching execution items for session_id={session_id}")
    url = EXECUTION_ITEMS_URL_TEMPLATE.format(session_id=session_id)
    payload = {"incrementCurrent": False, "activeLanguageLocale": "SI", "execution_type": execution_type}
    r = session.post(url, json=payload)
    r.raise_for_status()
    items = r.json()["data"]["items"]
    debug_print(f"Fetched {len(items)} items")
    return items


def init_db():
    debug_print("Initializing database...")
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS plu_items (
            id TEXT PRIMARY KEY,
            plu_number_id INTEGER,
            plu_number TEXT,
            title_si TEXT,
            image_src TEXT
        )
    """)
    conn.commit()
    return conn


def store_all_plus_if_needed(user_id):
    if os.path.exists(DB_FILE):
        debug_print("Database exists, skipping PLU storage")
        return
    debug_print("Storing all PLUs to database...")
    conn = init_db()
    c = conn.cursor()
    session_id = create_session(execution_type=1, user_id=user_id)
    items = fetch_execution_items(session_id)
    for item in items:
        plu = item.get("pluNumber", {})
        translations = plu.get("translations", {})
        sl_title = translations.get("SI", {}).get("name")
        c.execute("""
            INSERT OR REPLACE INTO plu_items (id, plu_number_id, plu_number, title_si, image_src)
            VALUES (?, ?, ?, ?, ?)
        """, (
            item.get("id"),
            plu.get("id"),
            plu.get("pluNumber"),
            sl_title,
            plu.get("imageSrc")
        ))
    conn.commit()
    conn.close()
    debug_print(f"Stored {len(items)} PLUs in the database")


def start_execution(session_id):
    debug_print(f"Starting execution for session_id={session_id}")
    url = START_EXECUTION_URL_TEMPLATE.format(session_id=session_id)
    session.post(url, json={}).raise_for_status()


def get_correct_plu_number(conn, plu_number_id):
    c = conn.cursor()
    c.execute("SELECT plu_number FROM plu_items WHERE plu_number_id = ?", (plu_number_id,))
    result = c.fetchone()
    return result[0] if result else None


def submit_answers(items, wrong_count=0):
    debug_print(f"Submitting answers, wrong_count={wrong_count}")
    conn = sqlite3.connect(DB_FILE)
    total = len(items)
    wrong_indices = set(random.sample(range(total), wrong_count))
    detailed_results = []

    for i, item in enumerate(items):
        plu_number_id = item["pluNumberId"]
        correct_plu = get_correct_plu_number(conn, plu_number_id)

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
        session.put(url, json=payload)

        detailed_results.append({
            "item_id": item["id"],
            "plu_number_id": plu_number_id,
            "given_plu": given_plu,
            "correct": correct_flag
        })
        debug_print(f"Submitted item {i+1}/{total}: given_plu={given_plu}, correct={correct_flag}")

    conn.close()
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


def run_session(email: str, password: str, target_score: int = None):
    debug_print("Running test session...")
    user_id = login(email, password)
    store_all_plus_if_needed(user_id)

    test_session_id = create_session(execution_type=3, user_id=user_id)
    start_execution(test_session_id)
    time.sleep(1)
    items = fetch_execution_items(test_session_id, execution_type=3)

    wrong_count = 0
    if target_score:
        total_items = len(items)
        correct_needed = int(total_items * (target_score / 100))
        wrong_count = total_items - correct_needed

    detailed_results = submit_answers(items, wrong_count=wrong_count)
    result_data = submit_result(test_session_id, user_id)

    total_items = len(detailed_results)
    correct_items = sum(1 for r in detailed_results if r["correct"])
    incorrect_items = total_items - correct_items
    average_score = (correct_items / total_items) * 100 if total_items else 0

    debug_print(f"Total items: {total_items}")
    debug_print(f"Correct items: {correct_items}")
    debug_print(f"Incorrect items: {incorrect_items}")
    debug_print(f"Average score: {average_score}")

    return {
        **result_data,
        "total_items": total_items,
        "correct_items": correct_items,
        "incorrect_items": incorrect_items,
        "average_score": average_score,
        "detailed_results": detailed_results
    }
