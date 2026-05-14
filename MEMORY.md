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
