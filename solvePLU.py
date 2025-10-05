import sys
import subprocess
import random
import sqlite3
import requests
import os
import time
import getpass
from tqdm import tqdm

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

BASE_URL = "https://easy-plu.knowledge-hero.com/api/plu"
LOGIN_URL = f"{BASE_URL}/login"
CREATE_SESSION_URL = f"{BASE_URL}/plu-learn/create-new-session"
EXECUTION_ITEMS_URL_TEMPLATE = f"{BASE_URL}/plu-learn/{{session_id}}/execution-items"
START_EXECUTION_URL_TEMPLATE = f"{BASE_URL}/plu-learn/{{session_id}}/start-execution"
UPDATE_ANSWER_URL_TEMPLATE = f"{BASE_URL}/plu-learn/{{item_id}}/update"
RESULT_URL_TEMPLATE = f"{BASE_URL}/plu-learn/{{session_id}}/result"

DB_FILE = "plu_items.db"
session = requests.Session()

USE_HARD_VAL = False
if USE_HARD_VAL:
    EMAIL = "nuuh@maybe.com"
    PASSWORD = "youthoughpahahhahaha"
else: 
    EMAIL = input("Enter your email: ")
    PASSWORD = getpass.getpass("Enter your password: ")

def login():
    payload = {"email": EMAIL, "password": PASSWORD}
    r = session.post(LOGIN_URL, json=payload)
    r.raise_for_status()
    data = r.json()
    token = data.get("api_token")
    user_id = data.get("user", {}).get("id") or data.get("id")
    session.headers.update({"Authorization": f"Bearer {token}", "Accept": "application/json"})
    return user_id

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
    return r.json()["data"]["session_id"]

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
        return
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

def start_execution(session_id):
    url = START_EXECUTION_URL_TEMPLATE.format(session_id=session_id)
    session.post(url, json={}).raise_for_status()

def get_correct_plu_number(conn, plu_number_id):
    c = conn.cursor()
    c.execute("SELECT plu_number FROM plu_items WHERE plu_number_id = ?", (plu_number_id,))
    result = c.fetchone()
    return result[0] if result else None


def submit_answers(items, wrong_count=0):
    conn = sqlite3.connect(DB_FILE)
    total = len(items)

    wrong_indices = set(random.sample(range(total), wrong_count))

    for i, item in enumerate(tqdm(items, desc="Submitting answers", unit="item")):
        plu_number_id = item["pluNumberId"]
        correct_plu = get_correct_plu_number(conn, plu_number_id)

        if i in wrong_indices:
            # Submit a wrong answer (e.g., "0000")
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
    conn.close()

def submit_result(session_id, user_id):
    url = RESULT_URL_TEMPLATE.format(session_id=session_id)
    payload = {"user_id": user_id}
    r = session.post(url, json=payload)
    r.raise_for_status()
    data = r.json().get("data", {})
    final_result = data.get("final_result", 0)
    print(f"\nFinal Result: {final_result}%")
    return final_result


def main():
    user_id = login()
    store_all_plus_if_needed(user_id)

    choice = input("Do you want 100% score? [y/n]: ").strip().lower()
    set_score = None
    if choice != "y":
        set_score_input = input("Enter a target score (e.g., 97) or press Enter to skip: ").strip()
        if set_score_input.isdigit():
            set_score = int(set_score_input)

    final_result = 0
    attempt = 1
    while True:
        print(f"\nStarting attempt #{attempt}...")
        test_session_id = create_session(execution_type=3, user_id=user_id)
        start_execution(test_session_id)
        time.sleep(1)
        items = fetch_execution_items(test_session_id, execution_type=3)

        wrong_count = 0
        if set_score:
            total_items = len(items)
            correct_needed = int(total_items * (set_score / 100))
            wrong_count = total_items - correct_needed
            print(f"Answering {wrong_count} questions incorrectly for approximately {set_score}%.")

        submit_answers(items, wrong_count=wrong_count)
        final_result = submit_result(test_session_id, user_id)

        if choice == "y":
            if final_result == 100:
                print("Achieved 100%. Done.")
                break
            else:
                print(f"Result was {final_result}%. Retrying test until 100% is achieved...\n")
                attempt += 1
                time.sleep(2)
        else:
            break

if __name__ == "__main__":
    main()
