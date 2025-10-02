![Lidl EasyPLU Logo](https://easy-plu.knowledge-hero.com/plufiles/default/lidl-leon-logo-new-png_4046_100x100.webp)

## EasyPLU Solver

**Disclaimer:** Lidl is a trademark owned by the Schwarz Group. EasyPLU is a product of Knowledge Hero. This project is intended for educational purposes only. Use responsibly and respect all applicable terms of service.

***

### Overview

**EasyPLU Solver** is a Python script designed to **automate PLU (Price Look-Up) training sessions** on the **EasyPLU platform**.

**⚠️ Important:** You must use your **EasyPLU login credentials** directly. **Do not use the Lidl SSO login.**

The script will:
1.  Fetch all **PLU numbers** and store them locally in a **SQLite database**.
2.  Start a **PLU test session** on EasyPLU.
3.  Automatically **submit all correct answers** in the order they appear.
4.  Retrieve final **statistics** of the test session.

***

### Features

* **Automatic PLU retrieval** and local caching.
* **Test session initialization** and execution.
* **Answer submission** in the correct order.
* Fetch **final results** and display statistics.

***

### Usage

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/OrlandoBlyat/EasyPLU-Solver.git
    cd EasyPLU-Solver
    ```
2.  **Run the script:**
   
    ```bash
    python web.py
    ```
4.  Enter your EasyPLU login credentials when prompted.

***

### Dependencies

The script uses the following Python packages:

* `requests`
* `sqlite3`
* `tqdm` (for progress display)

The script will check if dependencies are installed and prompt you to install missing packages automatically.

***

### Database

The script creates a SQLite database named **`plu_items.db`** to store PLU numbers. If the database already exists, it skips fetching PLUs again.

***

### Test Results

After completing the test, the script will display statistics including:

* Total execution time
* Points earned
* Final score
* User knowledge percentage
* User ranking in store

***
