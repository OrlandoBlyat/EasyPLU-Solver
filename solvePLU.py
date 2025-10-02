import sys
import subprocess

required_packages = ["requests", "tqdm"]

for pkg in required_packages:
    try:
        __import__(pkg)
    except ImportError:
        choice = input(f"Required package '{pkg}' is not installed. Install it now? [y/n]: ").strip().lower()
        if choice == "y":
            subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])
        else:
            print(f"Cannot continue without '{pkg}'. Exiting.")
            sys.exit(1)

import os
import sqlite3
import requests
from tqdm import tqdm
import time
import getpass

EMAIL = input("Enter your email: ")
PASSWORD = getpass.getpass("Enter your password: ")

BASE_URL = "https://easy-plu.knowledge-hero.com/api/plu"

LOGIN_URL = f"{BASE_URL}/login"
PRODUCT_CATEGORIES_URL = f"{BASE_URL}/plu-learn/product-categories"
CREATE_SESSION_URL = f"{BASE_URL}/plu-learn/create-new-session"
EXECUTION_ITEMS_URL_TEMPLATE = f"{BASE_URL}/plu-learn/{{session_id}}/execution-items"
START_EXECUTION_URL_TEMPLATE = f"{BASE_URL}/plu-learn/{{session_id}}/start-execution"
UPDATE_ANSWER_URL_TEMPLATE = f"{BASE_URL}/plu-learn/{{item_id}}/update"
RESULT_URL_TEMPLATE = f"{BASE_URL}/plu-learn/{{session_id}}/result"

DB_FILE = "plu_items.db"
session = requests.Session()

def login():
    payload = {"email": EMAIL, "password": PASSWORD}
    r = session.post(LOGIN_URL, json=payload)
    print("Login status:", r.status_code)
    r.raise_for_status()

    try:
        data = r.json()
    except Exception as e:
        raise Exception(f"Failed to parse login response as JSON: {r.text}") from e

    token = data.get("api_token")
    user_id = None

    if "user" in data and "id" in data["user"]:
        user_id = data["user"]["id"]
    elif "id" in data:
        user_id = data["id"]

    if not token:
        raise Exception(f"Login failed: no api_token found.\nFull response: {data}")
    if not user_id:
        raise Exception(f"Login succeeded but user_id not found.\nFull response: {data}")

    session.headers.update({
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    })
    print("Login successful. User ID:", user_id)
    return user_id

def preload_categories(user_id):
    payload = {"user_id": user_id, "baseline_test": False}
    r = session.post(PRODUCT_CATEGORIES_URL, json=payload)
    r.raise_for_status()
    print("Product categories preloaded.")

def create_session(execution_type, user_id):
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
    resp_json = r.json()
    session_id = resp_json.get("data", {}).get("session_id")
    start_time = resp_json.get("data", {}).get("session", {}).get("created_at")
    if not session_id:
        raise Exception("Could not find session_id in response.")
    print(f"\nNew session created.")
    print(f"  Session ID   : {session_id}")
    print(f"  Start time   : {start_time}\n")
    return session_id

def fetch_execution_items(session_id, execution_type=1):
    url = EXECUTION_ITEMS_URL_TEMPLATE.format(session_id=session_id)
    payload = {"incrementCurrent": False, "activeLanguageLocale": "SI", "execution_type": execution_type}
    r = session.post(url, json=payload)
    r.raise_for_status()
    return r.json()["data"]["items"]

def init_db():
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
        print("Database exists, skipping PLU fetch.")
        return
    print("No database found. Fetching all PLUs...")
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
    print(f"Stored {len(items)} PLUs into {DB_FILE}")

def start_execution(session_id):
    url = START_EXECUTION_URL_TEMPLATE.format(session_id=session_id)
    r = session.post(url, json={})
    r.raise_for_status()
    print("Execution started.\n")

def get_correct_plu_number(conn, plu_number_id):
    c = conn.cursor()
    c.execute("SELECT plu_number FROM plu_items WHERE plu_number_id = ?", (plu_number_id,))
    result = c.fetchone()
    return result[0] if result else None

def submit_answers(items):
    conn = sqlite3.connect(DB_FILE)
    for item in tqdm(items, desc="Submitting answers", unit="item"):
        plu_number_id = item["pluNumberId"]
        correct_plu = get_correct_plu_number(conn, plu_number_id)
        if not correct_plu:
            continue
        payload = {
            "execution_type": 3,
            "given_plu_number": correct_plu,
            "plu_number_id": plu_number_id,
            "answer": {"correct": True}
        }
        url = UPDATE_ANSWER_URL_TEMPLATE.format(item_id=item["id"])
        session.put(url, json=payload)
    conn.close()

def submit_result(session_id, user_id):
    url = RESULT_URL_TEMPLATE.format(session_id=session_id)
    payload = {"user_id": user_id}
    r = session.post(url, json=payload)
    r.raise_for_status()
    data = r.json().get("data", {})

    result = data.get("result", {})
    session_info = data.get("executionSession", {})

    print("\n=== Final Test Statistics ===")
    print(f"Session ID           : {result.get('plu_execution_session_id')}")
    print(f"Total Execution Time : {result.get('total_execution_time')} s")
    print(f"User Points          : {result.get('total_user_points')}/{result.get('max_points')} (Required: {result.get('required_points')})")
    print(f"Total Items Tested   : {session_info.get('plu_execution_session_item_count')}")
    print(f"Product Category ID  : {session_info.get('product_category_id')}")
    print(f"Final Result (%)     : {data.get('final_result')}")
    print(f"User Knowledge (%)   : {data.get('user_knowledge')}")
    print(f"Store Ranking        : #{data.get('user_ranking_in_store')}")
    print(f"Gold Plus Earned     : {data.get('earned_gold_plus')}/{data.get('total_gold_plus')}")
    print("=============================\n")

def main():
    user_id = login()
    store_all_plus_if_needed(user_id)
    preload_categories(user_id)

    test_session_id = create_session(execution_type=3, user_id=user_id)
    start_execution(test_session_id)
    time.sleep(1)

    items = fetch_execution_items(test_session_id, execution_type=3)
    print(f"Fetched {len(items)} test items.\n")

    submit_answers(items)
    submit_result(test_session_id, user_id)

if __name__ == "__main__":
    main()
