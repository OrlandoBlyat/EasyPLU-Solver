![Lidl EasyPLU Logo](https://easy-plu.knowledge-hero.com/plufiles/default/lidl-leon-logo-new-png_4046_100x100.webp)

## EasyPLU Solver

**Disclaimer:** Lidl is a trademark owned by the Schwarz Group. EasyPLU is a product of Knowledge Hero. This project is intended for educational purposes only. Use responsibly and respect all applicable terms of service.

***

### Overview

**EasyPLU Solver** is a web application designed to **automate PLU (Price Look-Up) training sessions** on the **EasyPLU platform**. It consists of a **FastAPI backend** and a **Next.js frontend** with real-time progress tracking.

**⚠️ Important:** You must use your **EasyPLU login credentials** directly. **Do not use the Lidl SSO login.**

The application will:
1.  Fetch all **PLU numbers** and store them locally in a **SQLite database**.
2.  Start a **PLU test session** on EasyPLU.
3.  Automatically **submit all correct answers** in the order they appear.
4.  **Automatically loop** until **100% user knowledge** is achieved.
5.  Provide **real-time progress updates** with live status tracking.
6.  Retrieve final **statistics** of the test session.

***

### Features

* **Automatic PLU retrieval** and local caching in SQLite database.
* **Test session initialization** and execution.
* **Answer submission** in the correct order.
* **Automatic looping** until 100% user knowledge is achieved.
* **Real-time progress tracking** with Server-Sent Events (SSE).
* **Live status updates** showing current stage, attempt number, and knowledge level.
* **Progress bar** with detailed submission tracking.
* **Modern web UI** built with Next.js and Tailwind CSS.
* Fetch **final results** and display comprehensive statistics.

***

### Installation & Setup

#### Prerequisites

* **Python 3.8+**
* **Node.js 18+** and **npm** (or **pnpm**)

#### Step 1: Clone the Repository

```bash
git clone https://github.com/OrlandoBlyat/EasyPLU-Solver.git
cd EasyPLU-Solver
```

#### Step 2: Setup Backend

1.  **Navigate to the backend directory:**
    ```bash
    cd back
    ```

2.  **Install Python dependencies:**
    ```bash
    pip install fastapi uvicorn requests pydantic
    ```
    
    Or create a virtual environment (recommended):
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    pip install fastapi uvicorn requests pydantic
    ```

3.  **Start the FastAPI backend server:**
    ```bash
    uvicorn api:app --reload --port 8000
    ```
    
    The backend will be available at `http://localhost:8000`

#### Step 3: Setup Frontend

1.  **Open a new terminal and navigate to the frontend directory:**
    ```bash
    cd front
    ```

2.  **Install dependencies:**
    ```bash
    npm install
    ```
    
    Or if you prefer pnpm:
    ```bash
    pnpm install
    ```

3.  **Start the Next.js development server:**
    ```bash
    npm run dev
    ```
    
    Or with pnpm:
    ```bash
    pnpm dev
    ```

4.  **Open your browser:**
    Navigate to `http://localhost:3000`

### Usage

1.  **Enter your credentials:**
    - **Uporabniško ime (e-naslov)**: Your EasyPLU email
    - **Geslo**: Your EasyPLU password
    - **Optional**: Check "Rezultat po meri" to set a custom target score percentage

2.  **Click "easyPLU"** to start the automated test session.

3.  **Monitor progress:**
    - Watch real-time updates showing the current stage
    - View attempt number and current knowledge level
    - See progress bar with detailed submission tracking
    - The solver will automatically loop until 100% knowledge is achieved

4.  **View results:**
    - After completion, view comprehensive statistics
    - Results include final score, knowledge percentage, points, ranking, and more

***

### Dependencies

#### Backend (Python)

The backend requires the following Python packages:

* `fastapi` - Web framework for building the API
* `uvicorn` - ASGI server for running FastAPI
* `requests` - HTTP library for API calls
* `pydantic` - Data validation using Python type annotations
* `sqlite3` - Built-in Python library for database operations

Install all dependencies:
```bash
pip install fastapi uvicorn requests pydantic
```

#### Frontend (Node.js)

The frontend is built with:

* **Next.js 15** - React framework
* **React 18** - UI library
* **TypeScript** - Type safety
* **Tailwind CSS** - Styling
* **Radix UI** - Accessible component primitives
* **Lucide React** - Icons

All dependencies are managed via `package.json` and installed with `npm install` or `pnpm install`.

***

### Database

The script creates a SQLite database named **`plu_items.db`** to store PLU numbers. If the database already exists, it skips fetching PLUs again.

***

### Test Results

After completing the test, the application will display comprehensive statistics including:

* **Final result** - Overall test score percentage
* **User knowledge** - Knowledge percentage (automatically reaches 100%)
* **Points earned** - Total points vs maximum points
* **Store ranking** - Your ranking position in the store
* **Gold Plus** - Earned vs total Gold Plus points
* **Items completed** - Number of PLU items processed
* **Execution time** - Total time taken to complete all attempts

### Architecture

The application consists of two main components:

* **Backend (`/back`)**: FastAPI server that handles:
  - User authentication
  - PLU database management
  - Test session execution
  - Real-time progress streaming via Server-Sent Events (SSE)
  - Automatic looping until 100% knowledge

* **Frontend (`/front`)**: Next.js application that provides:
  - User-friendly login interface
  - Real-time progress visualization
  - Live status updates
  - Results display

### Notes

* The solver **automatically loops** until 100% user knowledge is achieved (no manual intervention needed).
* PLU data is cached locally in `plu_items.db` to avoid repeated API calls.
* The backend runs on port **8000** and the frontend on port **3000** by default.
* Make sure both servers are running simultaneously for the application to work properly.

***
