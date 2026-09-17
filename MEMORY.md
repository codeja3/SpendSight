# MEMORY.md: SpendSight Decision Log & Architectural Context

This document serves as the persistent memory bank for the SpendSight project. It tracks the "why" behind architectural decisions, ensuring context is maintained across development sessions without bloating the core PRD or SPEC files.

## 1. Project Foundations
* **Project Name:** SpendSight
* **Core Objective:** A privacy-first, fully local CLI application for parsing bank statements, normalizing vendor names via local LLMs, and visualizing spending.

## 2. Architectural Decisions
* **The Language Split:** * *Decision:* Use Go for system orchestration (file watching, DB management, secure deletion) and Python for data processing.
  * *Reasoning:* Leverages Go's performance and standard library for system-level tasks while utilizing Python's dominance in data wrangling (`polars`) and LLM integration (`Instructor`/`DSPy`).
* **Package Management:**
  * *Decision:* `uv` for Python, `go mod` for Go. Explicitly rejected Conda and Docker.
  * *Reasoning:* Docker virtualization severs direct access to Apple Silicon's Metal API, crippling local LLM inference speed. Native tools preserve bare-metal performance.
* **Extraction Strategy:**
  * *Decision:* `pdfplumber` for structured table extraction from PDFs prior to `polars` ingestion.
  * *Reasoning:* `polars` cannot natively parse PDFs. `pdfplumber` provides reliable, offline bounding-box table extraction.
* **Vendor Normalization (The LLM Layer):**
  * *Decision:* Use structured local LLM inference (via `Instructor` or `DSPy`) instead of complex Regex rules.
  * *Reasoning:* Financial statement text is highly variable. LLMs excel at entity extraction when constrained by strict Pydantic JSON schemas.
* **Local Inference Engine & Model:**
  * *Decision:* Target a small parameter model (`gemma4:e2b`) running via Ollama natively on macOS.
  * *Reasoning:* An M2 Mac with 16GB of Unified Memory will bottleneck and swap to SSD if attempting to load models >8GB (like a 26B parameter model). A ~2B-9B parameter model at Q4/Q8 quantization ensures blazing-fast inference while leaving RAM for Go, macOS, and Polars.
* **Bank Profile Configuration (YAML over Go):**
  * *Decision:* Manage individual bank parsing logic (column names, sign multipliers) via a Python-loaded `configs.yaml` file rather than Go or SQLite.
  * *Reasoning:* Adheres to the "smart endpoints, dumb pipes" philosophy. It prevents Go from absorbing complex business logic, keeping it strictly as an orchestrator, while offering a highly readable, easily editable format for adding new bank accounts.
* **Unknown Statement Handling:**
    * *Decision:* Implemented a "Symmetric Resilience" heuristic. The orchestrator attempts a guess based on filename, then exhaustively retries ALL available profiles from `configs.yaml` before failing.
    * *Reasoning:* Prevents manual intervention for files that match existing profiles but have non-standard names.
* **Split Amount Columns Synthesis:**
    * *Decision:* Synthesize a canonical `amount` from `Debit` and `Credit` columns in the Python layer if a single `Amount` column is missing.
    * *Reasoning:* Common in some bank exports (e.g., Capital One). Keeps the database schema simple while supporting varied source formats.


## 3. Methodological Commitments
* **Test-Driven Development (TDD):** Tests are written and executed (and must fail) *before* implementation logic is drafted. 
* **Spec-Driven Development (SDD):** Schemas and API contracts must be defined in `SPEC.md` prior to coding.
* **CLI-First Development:** Code is executed strictly via the terminal. AI IDE auto-completion workflows are rejected to prevent undocumented technical debt.

## 4. Portfolio & Open Source Strategy
* **Synthetic Data:** The repository will include a script to generate fake PDFs/CSVs so reviewers can test the pipeline safely.
* **Mock Inference Flag:** The pipeline will support a `--mock` flag to bypass Ollama and return hardcoded JSON, allowing recruiters/reviewers without AI hardware to verify the Go orchestration and DB layers.

## 5. Security & Privacy
* **Ephemeral Data:** Source files are permanently deleted immediately after SQLite database commit.
* **Zero Network Calls:** No financial data leaves the local machine. 

## 6. Phase 4: Analytics Dashboard Decisions
* **UI Framework:** * *Decision:* Use `Textual` (Python) to build a Terminal UI (TUI).
  * *Reasoning:* Aligns perfectly with the CLI-Exclusive mandate in `PRD.md`. It avoids the bloat, security concerns, and context-switching of spinning up a local web server (like FastAPI + React or Streamlit), keeping the application entirely within the terminal.
* **Aggregation Strategy:**
  * *Decision:* Push all data aggregation (Top-N, groupings, sums) down to the SQLite database via parameterized queries.
  * *Reasoning:* While `polars` is already in our environment and excellent at aggregations, loading the entire SQLite database into memory just to calculate "Top 5 Vendors" is highly inefficient. Leveraging SQLite's native `GROUP BY` and `ORDER BY` keeps the Python UI layer thin, fast, and memory-safe.

## 7. Go Orchestrator Implementation (Phase 1)
* **File Watching Technology:**
  * *Decision:* Used `github.com/fsnotify/fsnotify` for the Go watcher.
  * *Reasoning:* It is the industry standard for cross-platform file system notifications in Go.
* **Resiliency & Data Integrity:**
  * *Decision:* Implemented a 500ms debounce and a sequential processing queue.
  * *Reasoning:* Debouncing prevents triggering the pipeline on partial file writes (common with large PDFs). A sequential queue ensures that database transactions are processed one at a time, preventing "database is locked" errors in SQLite during bulk file drops.
* **Dynamic Profile Discovery:**
  * *Decision:* Go queries the Python pipeline (`list-profiles`) to fetch available adapters.
  * *Reasoning:* Keeps Go "dumb" (not reading YAML) while allowing it to be aware of the configuration state for retry loops.
* **Exhaustive Retry Heuristic:**
  * *Decision:* The watcher cycles through all available profiles if the first attempt fails.
  * *Reasoning:* Maximizes ingestion success rates and minimizes user frustration when filenames are ambiguous.
* **Initialization Behavior:**
  * *Decision:* The watcher performs an "Initial Scan" of `/ingest` before entering the event loop.
  * *Reasoning:* Ensures that files already present when the app starts are not ignored, maintaining the "ephemeral data" rule for all files.
* **Error Handling & Ephemerality:**
  * *Decision:* The source file is deleted ONLY on a successful (Exit Code 0) pipeline run.
  * *Reasoning:* Prevents data loss if the LLM inference fails or if a file is malformed.

## 8. Extraction Pipeline Improvements
* **Defensive Data Cleaning:**
    * *Decision:* Filter out completely null or empty rows in the `polars` layer.
    * *Reasoning:* Prevents "ghost" records with `None` values caused by trailing newlines or empty data blocks in bank CSV exports.

## 9. Phase 9: Vendor Canonicalization & Data Hygiene (TDD)

### Task 23: Post-Ingestion Vendor Canonicalization (TDD) — DONE
* *Status:* Implemented in `src/python/vendor_canonicalize.py` with a `canonicalize` CLI; tests in `tests/python/test_vendor_canonicalize.py` all green.
* *Canonical key:* `lowercase` + strip non-alphanumerics (`[^a-z0-9]`). **Run-collapsing was dropped** — it added no value for the stated examples (`TMOBILE`/`T-Mobile`, `Quickpark`/`Quick Park`) and risked false merges.
* *Consolidation: rename, not row-merge.* Rows are never deleted/inserted and no `amount`/`date`/`raw_description` is mutated. Consolidated net spend is `SUM(amount) GROUP BY vendor`: expenditures sum into a larger net; deposits net (subtract) against it. Idempotent and lossless.
* *Representative:* per equivalence class, most-frequent spelling wins; ties break lexicographically.
* *Cache reconciliation:* `vendor_cache.vendor` rewritten to the canonical name for any non-canonical spelling; cache-existence checked once in `apply_canonicalization`.
* *Real-DB run:* 148->141 distinct vendors via 7 correct merges (all case variants of the same vendor); no false-positive merges observed.
* *Lint debt (pre-existing, untouched):* `ruff check src/ tests/` reports several items in `ingest.py`, `llm.py`, `pipeline.py`, `app.py`, `config.py`, `dal.py`, and `test_cli.py`, `test_dal.py`, `test_llm.py`. Flagged rather than fixed.

### Task 24: External Vendor Override Config (TDD) — DONE
* *Status:* `SYNONYMS` and `REVIEW_FLAGS` as module-level dicts, populated from `vendor_overrides.yaml` via `load_override_config` (fail-fast on malformed YAML, no-op on absent file) and `apply_override_config`. Tests in `tests/python/test_vendor_synonyms.py` all green.
* *Design decision:* `Landsend Inc.` vs `Lands' End` differ by an alphanumeric token ("inc") — no mechanical rule distinguishes "inc as decoration" from "inc as part of the name." A user-supplied `SYNONYMS` entry is the only sound way to fold this pair without risking false merges. `REVIEW_FLAGS` ("Thank You-Mobile": "possible T-Mobile ACH processor") prevents auto-merging a vendor that superficially resembles a duplicate but is income in a different category.
* *CLI:* `canonicalize --input <db> --config vendor_overrides.yaml`; absent config prints a note and skips.
* *Count bug fixed:* `before`/`after` in `main()` now query a separate connection before calling `apply_canonicalization`, so the reported counts reflect pre/post-merge state even when zero renames occur.

### Task 25: Auto-Canonicalization in the Go Success Path (TDD) — DONE
* *Status:* Added `src/go/orchestrator/canonicalize.go` (`Canonicalizer func(dbPath string) error`, `NoopCanonicalizer` default, `PythonCanonicalizer` that shells out to the §6.5.4 CLI). Threaded `canon Canonicalizer, dbPath string` through `ProcessFile → processWithLog → {initialScan, watchLoop} → StartWatcher`. `main.go` wires the real `PythonCanonicalizer()`; pre-existing orchestrator tests pass `NoopCanonicalizer`. Tests in `tests/go/orchestrator/canonicalize_wiring_test.go` all green; `go vet ./...` clean.
* *Design decision (post-delete, non-fatal):* Canonicalization runs at the **end** of `ProcessFile` — after `InsertTransactions` commits and after `os.Remove` of the source (Ephemeral Data Rule). Rationale: canonicalization must never re-lex ephemeral data, and it must never block the (already-committed, already-deleted) ingestion. A `Canonicalizer` error is logged (`WARNING: vendor canonicalization skipped: …`) but never returned. Idempotency (§6.5.5) means a skipped run self-heals on the next successful ingestion or a manual `canonicalize`. `canon == nil` safely defaults to `NoopCanonicalizer`.
* *Failure path:* canonicalization is skipped entirely when the payload fails to parse or `InsertTransactions` errors, so a quarantined file is never subjected to a partial merge.
* *Verification:* `tests/go/orchestrator/canonicalize_wiring_test.go` verifies invocation on success, safe skip on payload error, non-fatal handling on canonicalizer error, nil-safe handling, and includes `TestPythonCanonicalizer_EndToEnd` folding typo-variant vendors via `PythonCanonicalizer()`.

## 10. Phase 10: Comprehensive Vendor Directory & Search (TDD)

### Task 26: Vendor Directory Data Model & DAL Query (TDD) — DONE
* *Status:* Implemented `VendorDirectoryRow` and `get_vendor_directory(search: str | None = None)` in `src/python/dal.py`; unit tests in `tests/python/test_dal.py` all green.
* *Query design:* Correlated subquery resolves primary category by maximum frequency with alphabetical tie-breaking; aggregates total transaction count, algebraic net spend, and latest transaction date. Sorted alphabetically (`COLLATE NOCASE ASC`). Case-insensitive substring filter enabled via `AND LOWER(t.vendor) LIKE ?`.

### Task 27: "All Vendors" Tab & Real-Time Search in Textual TUI (TDD) — DONE
* *Status:* Added "All Vendors" `TabPane` to `SpendSightApp` in `src/python/app.py` with `Input(id="vendor-search-input")` and `DataTable(id="vendor-directory-table")`. Tests in `tests/python/test_app.py` verifying mount, table columns/rows, and dynamic live search filtering are green.
* *Interaction:* Real-time filtering handled via `on_input_changed`, querying `dal.get_vendor_directory(search=query)` and rebuilding table rows cleanly without layout remounting.

### Task 28: Documentation & Manual Verification — DONE
* *Status:* Updated `MANUAL.md` and `README.md` to document the All Vendors directory tab, its 5 columns (Vendor, Txns, Category, Net Spend, Last Date), and live search input.
* *Verification:* Full test suite (`pytest`, `go test ./...`) and linters green.

### Task 29: Vendor Directory Column Ordering & Sign Formatting (TDD) — DONE
* *Status:* Reordered columns in `_load_vendor_directory` in `src/python/app.py` to `("Vendor", "Total Spend", "Txns", "Category", "Last Date")`. Formatted currency balances as `-$X,XXX.XX` for negative expenditures and `$X,XXX.XX` for positive net amounts. Tests in `tests/python/test_app.py` all green.
* *Design decision:* The analytics pane has `width: 1fr` (1/3 of the screen width). Placing `Total Spend` immediately after `Vendor` guarantees total dollars spent are in plain sight without horizontal cutoff.

### Task 30: Canonicalize Amazon Brand Variants (TDD) — DONE
* *Status:* Configured `Amazon.com`, `Amazon Prime`, and `Amazon Marketplace` under `synonyms:` in `vendor_overrides.yaml`. Added unit test in `tests/python/test_vendor_synonyms.py` verifying that all variants fold into `Amazon` and net algebraic spend correctly.
* *Database Reconciliation:* Reconciled local `spendsight.db` via `uv run python -m src.python.vendor_canonicalize canonicalize --input spendsight.db --config vendor_overrides.yaml`. Consolidated 4 Amazon variants (72 total transactions, net -$3,428.82) into a single canonical `Amazon` entity. Total distinct vendors reduced from 141 to 138.



