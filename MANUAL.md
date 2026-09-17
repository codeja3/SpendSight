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
```

*Note: The system will automatically create an `/ingest` directory in the root of your project on first run if it doesn't already exist. This folder acts as the "dropzone" for your bank statements.*


**Step 2: Initialize the Local AI Model**
SpendSight normalizes your transactions without sending your data to the cloud. By default, it uses `gemma4:e2b`, but you can configure any model installed in Ollama via `configs.yaml`.

```bash
# Start the ollama server (keep this running in a separate terminal window)
ollama serve

# In a new terminal tab, pull your preferred model (default: gemma4:e2b)
ollama pull gemma4:e2b 
```
*(Note: Ollama must be running for SpendSight's Python pipeline to communicate with it).*

**Step 3: Build the Python Environment**
We use `uv` with `pyproject.toml` to create a reproducible, locked virtual environment.

```bash
# Sync runtime and dev dependencies
uv sync --extra dev
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

Leave this running in a terminal tab. Whenever you drop a `.pdf` or `.csv` bank statement into the `/ingest` directory, the Go orchestrator will:
1. **Detect** the file and automatically guess the profile (e.g., checking vs. credit) based on the filename.
2. **Trigger** the Python AI pipeline to normalize and categorize transactions (using local SQLite cache and micro-batching).
3. **Retry** with an alternate profile automatically if the first guess fails (Symmetric Resilience).
4. **Save** the clean data to SQLite with deduplication (`INSERT OR IGNORE`) and **permanently delete** the original file on success.
5. **Reconcile vendors** — after each successful delete, the ledger is automatically canonicalized: typographically distinct but identical vendors (e.g. `TMOBILE` / `T-Mobile`) are folded into one name by lossless rename, so aggregated spend stays coherent. This step is non-blocking: if canonicalization ever fails, the already-saved and already-deleted ingestion still stands, and the next ingestion self-heals it. You can also run it manually any time:
```bash
uv run python -m src.python.vendor_canonicalize canonicalize --input spendsight.db
```
6. **Quarantine** unparsable files that fail all profiles by safely moving them to `/ingest/failed/`.

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

**Configuration Notes (`configs.yaml`)**:
- **Local LLM Model:** Set the model under the top-level `llm:` block (e.g., `model: "llama3.2:3b"` or `model: "gemma4:e2b"`).
- **Bank Profiles:** When adding new accounts, configure `skip_rows`, `column_mapping`, `date_format`, and `sign_multiplier` to enforce the Canonical Sign Standard before dropping statements into `/ingest`.