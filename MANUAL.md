# 📖 SpendSight User Manual: Installation & Quick Start
Welcome to SpendSight! Because this application relies on a multi-language architecture (Go + Python) and a local AI model, the initial setup requires a few specific steps. Once configured, the daily operation is entirely seamless and managed through a single command-line interface.

---

## 🛑 Phase 1: Prerequisites
Before installing SpendSight, ensure your machine has the following foundational tools installed:

1. Golang (v1.26+): The engine for our system orchestrator.

  - Download: go.dev/dl

2. Python (v3.12+): The data processing engine.

3. uv: The lightning-fast Python package manager.

  - Install via curl: curl -LsSf https://astral.sh/uv/install.sh | sh

4. Ollama: The local LLM runner optimized for Apple Silicon and modern GPUs.

  - Download: ollama.com

---

## ⚙️ Phase 2: System Installation
**Step 1: Clone and Prepare the Repository**
Open your terminal and navigate to your preferred projects folder. 

```bash
git clone <your-repository-url> spendsight
cd spendsight

# Create the required ingestion directory if it doesn't exist
mkdir -p ingest
```

⚠️ CRITICAL: Create the Ingestion Dropzone
Because Git does not track empty folders, you must manually create the ingest directory in the root of your project. This folder acts as the "dropzone" for your bank statements. The Go watcher will monitor this specific folder and crash if it does not exist.


**Step 2: Initialize the Local AI Model**
SpendSight requires a small, fast language model to normalize your transactions without sending your data to the cloud. We use gemma4:e2b (or your preferred equivalent SLM).  

```bash
# Make sure ollama is active in the background 
ollama serve

# Pull the model to your local machine (this may take a few minutes depending on your internet speed)
ollama pull gemma4:e2b 
```
*(Note: Ollama must be running in the background for SpendSight's Python pipeline to communicate with it).*

**Step 3: Build the Python Environment**
We use uv to create an isolated, extremely fast virtual environment.

```bash
# Create the virtual environment
uv venv

# Activate the environment (macOS/Linux)
source .venv/bin/activate

# Install the required data and UI libraries
uv pip install textual textual-plotext instructor polars pdfplumber pydantic pytest-asyncio pyyaml
```

**Step 4: Compile the Go Orchestrator**
We bundle the entire application into a single executable binary.

```bash
# Download Go dependencies (the SQLite driver)
go mod tidy

# Compile the final binary
go build -o spendsight main.go
```

--- 

## 🚀 Phase 3: First-Time Setup & Testing

**Step 1: Initialize the Database**
Before SpendSight can do anything, it needs to build the SQLite database and create the strict schema we defined.

```bash
./spendsight init
```
*Expected Output: Success! 'spendsight.db' is ready.*

**Step 2: Seed Dummy Data (Optional, for testing the UI)**
If you want to test the interactive dashboard before uploading your real bank statements, run these commands to populate the database with a few mock transactions:

```bash
sqlite3 spendsight.db "INSERT INTO transactions (transaction_date, amount, raw_description, vendor, category, source_format) VALUES ('2026-05-15', -150.00, 'CONEDISON AUTOPAY', 'ConEdison', 'Utilities', 'csv');"
sqlite3 spendsight.db "INSERT INTO transactions (transaction_date, amount, raw_description, vendor, category, source_format) VALUES ('2026-05-16', 3000.00, 'PAYROLL ACH', 'Employer', 'Income', 'csv');"
sqlite3 spendsight.db "INSERT INTO transactions (transaction_date, amount, raw_description, vendor, category, source_format) VALUES ('2026-05-17', -65.40, 'TRADER JOE''S #123', 'Trader Joe''s', 'Groceries', 'csv');"
```
--- 

## 📊 Phase 4: Daily Operation
Once the installation is complete, SpendSight operates via three simple commands.

**1. The Watcher (Ingesting Statements)**
To process new bank statements, you must start the watcher.

```bash
./spendsight watch
```

Leave this running in a terminal tab. Whenever you drop a `.pdf` or `.csv` bank statement into the `/ingest` directory, the Go orchestrator will automatically detect it, trigger the Python AI pipeline, save the clean data to SQLite, and permanently delete the original file to protect your privacy.

**2. The Dashboard (Analyzing Spend)**
To view your financial analytics, run the dashboard command:

```bash
./spendsight dashboard
```

This launches the native `Textual` UI.

- Left Pane: View your complete, normalized ledger.

- Right Pane (Categories): View bar charts of your spending and use the dropdown to drill down into specific vendors within a category.

- Right Pane (Vendors): View your highest and lowest spending targets.

- To exit the dashboard, simply press Ctrl + C.

--- 

**Configuration Note**: If you are adding a new bank account format, ensure you update the configs.yaml file with the correct skip_rows, column_mapping, and sign_multiplier to enforce the Canonical Sign Standard before dropping the statement into the /ingest folder.