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
To enforce deterministic output from local small language models (default: `gemma4:e2b`), the Python layer uses `Instructor` and `Pydantic`.

### 3.0 Model Configuration Contract (`configs.yaml`)
Users configure the local inference model via an optional top-level `llm` block in `configs.yaml`:
```yaml
llm:
  model: "gemma4:e2b" # e.g., llama3.2:3b, phi4, mistral, gemma4:e2b
```
* **Schema Definition (`LLMConfig`):**
  ```python
  class LLMConfig(BaseModel):
      model: str = "gemma4:e2b"
  ```
* **Fallback Behavior:** If the `llm` block or `model` key is omitted in `configs.yaml`, the system defaults to `"gemma4:e2b"`.
* **Parameter Propagation:** `load_llm_config(config_path)` parses this block; `pipeline.py` passes the resolved `model` name to `normalize_transactions(..., model=model)` and `normalize_batch(..., model=model)`.

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

class VendorDirectoryRow(BaseModel):
    name: str
    transaction_count: int
    total_spend: float
    primary_category: str
    last_active_date: str
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

**Feature 2.5: All Vendors Directory**
Retrieves all distinct vendors with transaction counts, net spend, primary category, and last active date, sorted alphabetically (case-insensitive). Supports an optional substring filter.
* **Base Query:**
```sql
SELECT 
    t.vendor as name,
    COUNT(*) as transaction_count,
    SUM(t.amount) as total_spend,
    (
        SELECT t2.category 
        FROM transactions t2 
        WHERE t2.vendor = t.vendor 
        GROUP BY t2.category 
        ORDER BY COUNT(*) DESC, t2.category ASC 
        LIMIT 1
    ) as primary_category,
    MAX(t.transaction_date) as last_active_date
FROM transactions t
WHERE t.vendor IS NOT NULL AND t.vendor != ''
GROUP BY t.vendor
ORDER BY t.vendor COLLATE NOCASE ASC
```
* **Filter Query (when search term provided):**
Appends `AND LOWER(t.vendor) LIKE ?` with parameter `f"%{search.lower()}%"`.
* **DAL Signature:** `def get_vendor_directory(self, search: str | None = None) -> list[VendorDirectoryRow]`

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
  * **Tab: "All Vendors" (Feature 2.5)**
    * Includes an `Input` widget with placeholder `"Search vendors..."` (id: `vendor-search-input`).
    * Includes a `DataTable` widget (id: `vendor-directory-table`) displaying columns: `Vendor`, `Total Spend`, `Txns`, `Category`, `Last Date`. Primary financial metric (`Total Spend`) is placed adjacent to `Vendor` to guarantee immediate visibility in narrow analytics layouts, formatted as `-$X,XXX.XX` for expenditures and `$X,XXX.XX` for positive net balances.
    * Filtering updates dynamically when text is entered into `vendor-search-input`.

## 6.5 Vendor Canonicalization

After ingestion completes, the user must be able to invoke a vendor canonicalization routine that reconciles typographically distinct but semantically identical vendor names stored in the `transactions` table, so that amounts attributed to them are coherently aggregated per vendor.

### 6.5.1 Scope & Equivalence Rule
The feature scans **all rows** in `transactions` where `vendor IS NOT NULL` and applies a deterministic, pure function `canonical_key(vendor) -> str` that normalizes a vendor name by:
1. Converting to lowercase.
2. Stripping all non-alphanumeric characters (spaces, hyphens, periods, asterisks, underscores, etc.).

Two vendors are **semantically equivalent** if and only if `canonical_key` returns the same string for both.
- Examples: `TMOBILE`, `T-Mobile`, `T-MOBILE.`, and `* T-MOBILE *` (a raw description's vendor) all collapse to key `tmobile`; `Quickpark`, `Quick_Park`, and `Quick Park.` all collapse to `quickpark`.

Run-collapsing (treating `aa` and `a` as equal) was deliberately **omitted**: it provides no benefit for the stated examples and risks merging genuinely distinct vendors that merely differ by a doubled character. A 2-step key (lowercase + strip) is the sound, minimally-invasive invariant.

For each equivalence class (one or more distinct vendor spellings sharing a key), the **canonical representative** is:
- the spelling with the **highest row frequency**;
- breaking ties by the **lexicographically smallest** original spelling.

A class of size 1 (a spelling that is already its own representative) maps to itself and is excluded from the rename set.

### 6.5.2 Consolidation: Rename, Not Row-Merge
Consolidation is performed **by renaming `transactions.vendor` only**. No row is inserted or deleted, and no per-row `amount`, `transaction_date`, or `raw_description` is mutated.
- Because each row retains its canonical signed amount (negative = expenditure, positive = deposit), consolidated spending per vendor is the algebraic sum of its rows: `SUM(amount) GROUP BY vendor`.
- This makes the sign-dependent aggregation the user expects automatic and lossless: merged negative rows **sum into a larger net expenditure**, while merged positive rows **net against** it (a deposit "subtracts" from spend). No sign flip is performed at merge time; signs are only reconciled at aggregation time in the analytics layer (Features 2.1–2.4).
- **Rationale (single source of truth):** row-merging would destroy auditability, break idempotency, and require re-deriving dates/categories. A lossless rename keeps the ledger append-only, reversible-in-principle, and idempotent.

### 6.5.3 Module & Function Contract
A new module `src/python/vendor_canonicalize.py` provides:

```python
def canonical_key(vendor: str) -> str
```
Pure, deterministic. Returns the normalized key per §6.5.1. No I/O, no side effects.

```python
def compute_canonical_mappings(db_path: str) -> dict[str, str]
```
Scans `transactions`, groups distinct `vendor` values by `canonical_key`, selects the canonical representative per group, and returns `{old_vendor: canonical_name}` for every spelling that is **not** already its own representative. Vendors that map to themselves are omitted. This function is a pure read; it does **not** mutate the database.

```python
def apply_canonicalization(db_path: str) -> dict[str, str]
```
Computes the mappings, then applies them in a single transaction: updates `transactions.vendor` for all affected rows and invalidates/reconciles `vendor_cache` (see §6.5.6). Returns the same `{old: canonical}` mapping as `compute_canonical_mappings` (empty when there is nothing to merge). Fail-fast: database/connection errors propagate as exceptions (the CLI translates these to a non-zero exit code).

### 6.5.4 CLI Interface
```bash
uv run python -m src.python.vendor_canonicalize canonicalize --input spendsight.db
```
The command calls `apply_canonicalization`, prints a human-readable summary (vendor count before/after and the list of `old -> canonical` renames), and returns exit code `0` on success and non-zero on database errors.

### 6.5.5 Idempotency
Running canonicalization multiple times is safe: once all spellings equal their class's representative, `compute_canonical_mappings`/`apply_canonicalization` returns an empty dict and writes nothing to the database.

### 6.5.6 Vendor Cache Invalidation
After renaming, any `vendor_cache` row whose `vendor` is a non-canonical spelling must be updated so `vendor_cache.vendor` becomes the canonical representative. This keeps the LLM cache consistent with the transactions table, so future normalizations resolve to the canonical name. `vendor_cache.category` is left unchanged (a spelling's category is independent of its spelling).

### 6.5.7 External Override Configuration (`SYNONYMS` / `REVIEW_FLAGS`)
The mechanics of §6.5.1 cover typographic differences only. Two classes of duplicates that the mechanical key cannot infer are handled via a user-maintained YAML file `vendor_overrides.yaml` loaded through `load_override_config` / `apply_override_config`, optional via the CLI `--config` flag (default `vendor_overrides.yaml`; an absent file is a no-op, a present-but-malformed file fails fast).

**Schema:**
```yaml
synonyms:
       # Each key is a current vendor spelling; its value is the
       # target name to fold this spelling into. The target's
       # equivalence class then selects the canonical representative
       # by the usual most-frequent rule (§6.5.1).
       "Landsend Inc.": "Lands' End"

review_flags:
       # Vendors that *look* like a duplicate but must NOT be auto-merged.
       # Surfaced in the CLI summary for manual triage; never merged.
       "Thank You-Mobile": "Possible T-Mobile ACH processor -- verify."
```

**Behavior:**
* `SYNONYMS[spelling] = target`: `class_key(spelling)` returns `canonical_key(target)`, so the spelling joins the target's equivalence class and both spellings participate in the same most-frequent/lex representative selection. This preserves idempotency: once a spelling is renamed to the class representative, it no longer carries its original key.
* `REVIEW_FLAGS[vendor] = note`: the vendor is explicitly excluded from any automatic merge. `get_review_flags(conn)` returns `{vendor: note}` for every flagged vendor still present in `transactions` (i.e., not already renamed), enabling the CLI to print a "manual review" section without merging them.

**Rationale:** `Landsend Inc.` and `Lands' End` differ by an alphanumeric token (`inc`); no mechanical rule can distinguish "inc as decoration" from "inc as part of the name" without a human decision. `Thank You-Mobile` shares no key with `T-Mobile` by construction (it is T-Mobile's ACH/payment processor, not a typo), and even if it did, merging it would silently combine income and expense. Explicit user judgment is the only sound handling.

### 6.5.8 Orchestrator Auto-Wiring (Post-Ingestion, Non-Fatal)
Canonicalization is invoked **automatically after every successful ingestion** by the Go orchestrator, in addition to remaining available as the standalone CLI of §6.5.4. The wiring contract:

- **Trigger:** at the end of `ProcessFile`, *after* the ledger insert commits and *after* the source file is deleted (Ephemeral Data Rule). By construction, canonicalization always sees a committed ledger and an already-deleted source, so it can never re-lex ephemeral data.
- **Interface:** a `Canonicalizer func(dbPath string) error` is threaded through `ProcessFile → processWithLog → {initialScan, watchLoop} → StartWatcher`. The orchestrator calls `canonicalizer(dbPath)` on the success path.
- **Default (real):** `PythonCanonicalizer`, which invokes the §6.5.4 CLI (`uv run python -m src.python.vendor_canonicalize canonicalize --input <db>`) with `vendor_overrides.yaml` resolved from the working directory.
- **Default (tests / opt-out):** `NoopCanonicalizer`, a hermetic no-op that invokes no external process. Pre-existing orchestrator tests use it; `main.go` wires the real `PythonCanonicalizer`.
- **Non-fatal semantics:** a non-zero `Canonicalizer` return is logged (`WARNING: vendor canonicalization skipped: …`) but **never fails `ProcessFile` or the watcher**. Rationale: the source file is already deleted and the commit already landed, so the Ephemeral Data guarantee holds regardless; and §6.5.5 idempotency means any skipped canonicalization self-heals on the next successful ingestion or a manual `canonicalize` run.
- **Failure path is unaffected:** canonicalization is skipped entirely when the payload fails to insert (extraction or `InsertTransactions` error), so a quarantined file is never subjected to a partial merge.
- **Contract tests:** `tests/go/orchestrator/canonicalize_wiring_test.go` asserts exactly-once invocation with the database path on success, hermetic behavior of `NoopCanonicalizer`, and that the failure path invokes no canonicalization.

---

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
    * **If Success:** Parse JSON, commit to DB, delete source file, then run the non-fatal post-ingestion canonicalization (§6.5.8) on the resulting ledger.
    * **If Failure:** The orchestrator iterates through *all* other discovered profiles and retries.
    * **Final Failure:** If all profiles fail, the error is logged to the terminal and the source file is moved to `/ingest/failed/` to prevent infinite re-processing loops while preserving the file for inspection.
5. **Outcome Handling:**
     * **Success (Exit Code 0):** Parse the JSON from `stdout`, insert into SQLite (`INSERT OR IGNORE`), **permanently delete** the source file, then run **vendor canonicalization on the database** (see §6.5.8) as a non-fatal post-ingestion step.
     * **Failure (Exit Code != 0):** Log the error from `stderr` to the terminal and **move** the unparsable source file into `/ingest/failed/<filename>`. Canonicalization is **not** run on the failure path.

### 7.3 Concurrency & Safety
* **Sequential Processing:** To maintain database integrity and simple logging, files must be processed one at a time. If multiple files are dropped, they should be queued.
* **Initialization Scan:** Upon starting the `watch` command, the orchestrator must perform an initial scan of the `/ingest` directory and process any existing files before entering the event-listening loop.
