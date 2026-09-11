# SPEC.md: SpendSight Technical Specifications

This document defines the strict data schemas, API contracts, and boundary definitions for the SpendSight application. Any changes to data structures must be updated here and approved before implementation code is altered.

## 1. Database Schema (SQLite)

The database acts as the single source of truth. Schema migrations will be handled manually via CLI scripts or standard SQL files for simplicity in Phase 1.

### Table: `transactions`
| Column Name | SQLite Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | `PRIMARY KEY AUTOINCREMENT` | Unique identifier. |
| `transaction_date` | `TEXT` | `NOT NULL` | ISO-8601 format (YYYY-MM-DD). |
| `amount` | `REAL` | `NOT NULL` | Transaction amount. Negative values represent expenditures; positive values represent deposits/payments. |
| `raw_description` | `TEXT` | `NOT NULL` | The exact string extracted from the bank statement. |
| `vendor` | `TEXT` | `NOT NULL` | The normalized vendor name provided by the LLM. |
| `category` | `TEXT` | `NOT NULL` | Categorization provided by the LLM. |
| `source_format` | `TEXT` | `NOT NULL` | Either 'pdf' or 'csv'. |
| `ingested_at` | `TEXT` | `NOT NULL DEFAULT CURRENT_TIMESTAMP` | UTC timestamp of when the record was written. |

* **Unique Deduplication Constraint:**
  `CONSTRAINT uq_transaction UNIQUE (transaction_date, amount, raw_description)`
* **Insert Policy:**
  Go orchestrator inserts using `INSERT OR IGNORE INTO transactions ...` ensuring that re-uploaded statements or overlapping date ranges never create duplicate records.

### Table: `vendor_cache`
Stores previously normalized descriptions to avoid redundant and slow local LLM calls.
| Column Name | SQLite Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `raw_description` | `TEXT` | `PRIMARY KEY` | Normalized uppercase/trimmed raw description. |
| `vendor` | `TEXT` | `NOT NULL` | Normalized vendor name. |
| `category` | `TEXT` | `NOT NULL` | Normalized budget category. |
| `created_at` | `TEXT` | `NOT NULL DEFAULT CURRENT_TIMESTAMP` | UTC timestamp. |

## 2. The Python-to-Go JSON Contract
When the Go orchestrator executes the Python extraction pipeline, the Python script must output a strict JSON payload to `stdout` upon success. The Go watcher parses this payload to execute the database inserts.

**Payload Schema:**
```json
{
  "metadata": {
    "source_file": "statement_april_2026.pdf",
    "format": "pdf",
    "processed_records": 142
  },
  "transactions": [
    {
      "date": "2026-04-12",
      "amount": -45.50,
      "raw_description": "SQ *LOCAL COFFEE SHOP NEW YORK NY",
      "vendor": "Local Coffee Shop",
      "category": "Dining"
    }
  ]
}
```

## 3. Local LLM Extraction Schema & Optimization (Pydantic)
To enforce deterministic output from `gemma4:e2b`, the Python layer will use `Instructor` and `Pydantic`.

### Single Entity Schema
```python
from pydantic import BaseModel, Field
from typing import Literal

class TransactionEntity(BaseModel):
    vendor: str = Field(
        description="The clean, normalized name of the business. Strip out store numbers, cities, or payment processor prefixes like 'SQ *' or 'TST*'."
    )
    category: Literal[
        "Groceries", "Dining", "Transportation", "Housing", 
        "Utilities", "Entertainment", "Shopping", "Income", "Transfer", "Other"
    ] = Field(
        description="The budget category that best fits the vendor."
    )
```

### Micro-Batching Schema
To avoid individual HTTP round-trips for every transaction, un-cached descriptions are batched into chunks of 10–20:
```python
class BatchTransactionEntities(BaseModel):
    items: list[TransactionEntity]
```

### Normalization Pipeline Flow
1. **Cache Lookup:** Check incoming `raw_description` against `vendor_cache`.
2. **Batching:** Collect cache misses into batches of 10–20 items.
3. **Inference:** Send each batch to Ollama with `response_model=BatchTransactionEntities`.
4. **Cache Populate:** Upsert newly normalized pairs into `vendor_cache`.

## 4. CLI Execution Interfaces
The system boundaries operate exclusively via standard input/output and CLI arguments.

**Python Extraction Invocation:**
The Go orchestrator will trigger the pipeline using the following signature:
`uv run python -m src.python.pipeline process --input /absolute/path/to/ingest/file.pdf --profile <profile_name> --output stdout`
* **Failure State:** If parsing, profile mapping, or LLM extraction fails, Python must exit with a non-zero status code and write the error trace to `stderr`. Go will catch this and halt the deletion of the source file.
* **Mock Mode:** `uv run python -m src.python.pipeline process --input /path/to/file.pdf --profile <profile_name> --mock --output stdout`
*(Bypasses the LLM and returns the predefined JSON contract for testing.)*

**Python Profile Discovery:**
To allow the Go orchestrator to dynamically discover available profiles without hardcoding:
`uv run python -m src.python.pipeline list-profiles`
* **Success State:** Returns a JSON list of strings representing the keys in `configs.yaml` (e.g., `["checking", "credit_account_with_split"]`).

## 5. Account Adapters & Sign Normalization
Financial institutions use conflicting sign conventions. 

**The Canonical Standard:**
Before data reaches the SQLite database or the LLM, the Python `polars` layer must enforce a strict canonical sign standard:
* **Expenditures / Debits:** Negative (`-`)
* **Payments / Deposits:** Positive (`+`)

**Split Column Synthesis:**
Some institutions provide separate `Debit` and `Credit` columns instead of a single `Amount` column. If a profile maps both `debit` and `credit` standard names, the pipeline synthesizes the canonical amount using: `amount = Credit - Debit`.

**Defensive Filtering:**
To handle trailing newlines or "junk" rows common in bank CSV exports, the pipeline automatically filters out rows that are entirely null or empty before processing.

**The Adapter Pattern:**
To handle varied structures, the system will use an external `configs.yaml` file mapping each account profile to its parsing rules (`skip_rows`, `column_mapping`, `sign_multiplier`).

## 6. Analytics & Dashboard Data Contracts

### 6.1 Schema Definitions
The Python Data Access Layer (DAL) will return these structures to the Textual UI layer to ensure strict type safety between the database and the frontend.

```python
from pydantic import BaseModel

class LedgerRow(BaseModel):
    date: str
    vendor: str
    category: str
    amount: float

class AggregateRow(BaseModel):
    name: str 
    total_spend: float
```

### 6.2 Feature Queries

**Feature 1: Ledger View**
Retrieves chronological transactions for the main data table, supporting pagination.
* **Query:** `SELECT transaction_date AS date, vendor, category, amount FROM transactions ORDER BY transaction_date DESC LIMIT ? OFFSET ?`
* **Parameters:** `limit` (int), `offset` (int)

**Feature 2.1: Top-N Vendors (Highest Spend)**
Retrieves the vendors with the most negative sum (highest expenses).
* **Query:** `SELECT vendor as name, SUM(amount) as total_spend FROM transactions WHERE amount < 0 GROUP BY vendor ORDER BY total_spend ASC LIMIT ?`
* **Parameters:** `limit_n` (int)

**Feature 2.2: Bottom-N Vendors (Lowest Spend)**
Retrieves the vendors with the sum closest to zero (lowest expenses).
* **Query:** `SELECT vendor as name, SUM(amount) as total_spend FROM transactions WHERE amount < 0 GROUP BY vendor ORDER BY total_spend DESC LIMIT ?`
* **Parameters:** `limit_n` (int)

**Feature 2.3: Top-N Categories**
Aggregates total expenses by category to populate high-level charts.
* **Query:** `SELECT category as name, SUM(amount) as total_spend FROM transactions WHERE amount < 0 GROUP BY category ORDER BY total_spend ASC LIMIT ?`
* **Parameters:** `limit_n` (int)

**Feature 2.4: Top-N Vendors Within a Category**
Drill-down metric for specific budget areas.
* **Query:** `SELECT vendor as name, SUM(amount) as total_spend FROM transactions WHERE category = ? AND amount < 0 GROUP BY vendor ORDER BY total_spend ASC LIMIT ?`
* **Parameters:** `target_category` (str), `limit_n` (int)

### 6.3 Visual Layout & UI Components (Textual)

The terminal dashboard will utilize a horizontal split layout to balance detailed transactional data with aggregated analytics.

* **Main Layout Engine:** Textual `Horizontal` grid.
* **Left Pane (Ledger):** * Consumes 2/3 of terminal width.
  * Uses Textual's `DataTable` widget for Feature 1.
* **Right Pane (Analytics):** * Consumes 1/3 of terminal width.
  * Uses Textual's `TabbedContent` widget to prevent vertical overflow.
  * **Tab: "Categories"**
    * Integrates `textual-plotext` for a terminal-based bar chart mapping Feature 2.3.
    * Includes a `Select` widget triggering Feature 2.4 (Drill-down).
  * **Tab: "Vendors"**
    * Vertically stacks UI blocks for Feature 2.1 (Highest Spend) and Feature 2.2 (Lowest Spend).

## 7. Orchestrator File Watcher

The Go orchestrator must provide a resilient file watching mechanism to automate the ingestion pipeline.

### 7.1 Monitor Behavior
* **Target Directory:** `/ingest` (Relative to project root).
* **Event Triggers:** `Create` or `Rename` (Move-in) events.
* **Supported Extensions:** `.pdf`, `.csv` (Case-insensitive).
* **Debounce:** The orchestrator should wait for a short period (e.g., 500ms) after an event to ensure the file is fully written/transferred before triggering the pipeline.

### 7.2 Execution Loop
1. **Detect:** A new supported file appears in `/ingest`.
2. **Discovery:** The orchestrator queries the Python pipeline (`list-profiles`) to get the latest list of available account adapters.
3. **Heuristic Guess:** The orchestrator determines an `initial_profile` based on filename keywords (e.g., "credit", "visa", "checking").
4. **Exhaustive Retry (Symmetric Resilience):** 
    * The orchestrator invokes the pipeline with the `initial_profile`.
    * **If Success:** Parse JSON, commit to DB, and delete source file.
    * **If Failure:** The orchestrator iterates through *all* other discovered profiles and retries.
    * **Final Failure:** If all profiles fail, the error is logged to the terminal and the source file is moved to `/ingest/failed/` to prevent infinite re-processing loops while preserving the file for inspection.
5. **Outcome Handling:**
    * **Success (Exit Code 0):** Parse the JSON from `stdout`, insert into SQLite (`INSERT OR IGNORE`), and **permanently delete** the source file.
    * **Failure (Exit Code != 0):** Log the error from `stderr` to the terminal and **move** the unparsable source file into `/ingest/failed/<filename>`.

### 7.3 Concurrency & Safety
* **Sequential Processing:** To maintain database integrity and simple logging, files must be processed one at a time. If multiple files are dropped, they should be queued.
* **Initialization Scan:** Upon starting the `watch` command, the orchestrator must perform an initial scan of the `/ingest` directory and process any existing files before entering the event-listening loop.
