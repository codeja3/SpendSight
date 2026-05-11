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

## 3. Local LLM Extraction Schema (Pydantic)
To enforce deterministic output from `gemma4:e2b`, the Python layer will use `Instructor` and `Pydantic`. Raw strings are passed to the model, and it must return this exact structure.

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

## 4. CLI Execution Interfaces
The system boundaries operate exclusively via standard input/output and CLI arguments.

**Python Extraction Invocation:**
The Go orchestrator will trigger the pipeline using the following signature:
`uv run python -m src.pipeline process --input /absolute/path/to/ingest/file.pdf --profile <profile_name> --output stdout`
* **Failure State:** If parsing, profile mapping, or LLM extraction fails, Python must exit with a non-zero status code and write the error trace to `stderr`. Go will catch this and halt the deletion of the source file.
* **Mock Mode:** `uv run python -m src.pipeline process --input /path/to/file.pdf --profile <profile_name> --mock --output stdout`
*(Bypasses the LLM and returns the predefined JSON contract for testing.)*

## 5. Account Adapters & Sign Normalization
Financial institutions use conflicting sign conventions. 

**The Canonical Standard:**
Before data reaches the SQLite database or the LLM, the Python `polars` layer must enforce a strict canonical sign standard:
* **Expenditures / Debits:** Negative (`-`)
* **Payments / Deposits:** Positive (`+`)

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
