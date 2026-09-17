# SpendSight TODO & Milestone Tracker

## Phase 1: Environment & Backend Orchestration (Golang/SQLite)
This phase focuses on building the "dumb pipe"—the Go orchestrator that watches the directory, executes the Python script, and saves the resulting JSON payload into the SQLite database.

### Task 1: Project Scaffolding
- [x] Initialize Git repository.
- [x] Initialize Go module (`go mod init spendsight`).
- [x] Initialize Python environment (`uv venv` and `uv pip install polars pydantic pdfplumber instructor`).
- [x] Create basic directory structure (`/ingest`, `/src/go`, `/src/python`, `/tests/go`, `/tests/python`).

### Task 2: Database Initialization (TDD)
- [x] **Test:** Write `db_test.go` to verify SQLite connection and schema creation.
- [x] **Implement:** Write `db.go` to execute the schema creation defined in `SPEC.md`.
- [x] **Refactor:** Ensure context managers/defensive programming are used for DB connections.

### Task 3: JSON Payload Ingestion (TDD)
- [x] **Test:** Write `ingest_test.go` using a mock JSON payload (matching `SPEC.md`) to verify successful parsing into Go structs.
- [x] **Implement:** Write `ingest.go` to unmarshal the Python JSON output.

### Task 4: Database Insertion (TDD)
- [x] **Test:** Write `insert_test.go` to verify the parsed Go structs are correctly inserted into the `transactions` table.
- [x] **Implement:** Write the `InsertTransactions` function.

### Task 5: The File Watcher & Orchestrator (TDD)
- [x] **Test:** Write `watcher_test.go` to simulate a file drop and verify it triggers the mock CLI command.
- [x] **Implement:** Write `watcher.go` to monitor the `/ingest` directory and execute the Python pipeline via standard CLI execution (`--mock` flag for now).
- [x] **Refactor:** Implement dynamic profile discovery and exhaustive retry logic ("Symmetric Resilience") to handle non-standard filenames.
- [x] **Implement:** Add the secure deletion routine to permanently remove the file upon successful DB commit.

---

## Phase 2: Extraction Pipeline (Python)
### Task 6: Profile Configuration Loader (TDD)
- [x] **Test:** Write `test_config.py` to verify YAML loading and strict Pydantic validation.
- [x] **Implement:** Write `config.py` to parse `configs.yaml` and Fail-Fast on missing profiles.

### Task 7: Data Ingestion & Canonical Normalization (TDD)
- [x] **Test:** Write `test_ingest.py` to verify CSV/PDF parsing into a Polars DataFrame.
- [x] **Implement:** Write `ingest.py` to map raw columns and enforce the Canonical Sign Standard via the profile's `sign_multiplier`.
- [x] **Refactor:** Implement split Debit/Credit column synthesis.
- [x] **Refactor:** Implement defensive filtering of null/empty rows to prevent ghost records.

### Task 8: Python CLI Entrypoint (TDD)
- [x] **Test:** Write `test_cli.py` to simulate the Go orchestrator's CLI invocation.
- [x] **Implement:** Write `pipeline.py` to wire the config and ingest modules together and print the final JSON to stdout.
- [x] **Implement:** Add `list-profiles` command for dynamic Go-to-Python configuration discovery.

--- 

## Phase 3: Transformation & Normalization (LLM)
### Task 9: LLM Client & Schema Definition (TDD)
- [x] **Test:** Write `test_llm.py` to mock Ollama and verify Pydantic schema enforcement.
- [x] **Implement:** Write `llm.py` configuring the `instructor` client to target local `gemma4:e2b` and define the `TransactionEntity` schema.

### Task 10: Batch Normalization (TDD)
- [x] **Test:** Write tests for processing a list of raw transaction strings into structured entities.
- [x] **Implement:** Add a `normalize_transactions` function to handle the LLM batching loop gracefully.

### Task 11: Pipeline Integration
- [x] **Test:** Update CLI tests to handle the live LLM execution path.
- [x] **Implement:** Wire the LLM normalization step into `pipeline.py` between ingestion and JSON output.

## Phase 4: Analytics Dashboard (Textual)
### Task 12: Dashboard Specification (SDD)
- [x] **Define:** Update `SPEC.md` to map out the exact SQLite aggregations required for the dashboard.
- [x] **Define:** Outline the visual layout of the `Textual` UI components (e.g., DataTables for ledgers, Plotext for terminal charts).

### Task 13: Database Query Layer (TDD)
- [x] **Test:** Write tests to verify SQLite aggregation queries (Total Spend by Category, Top Vendors).
- [x] **Implement:** Build the Python data access layer to fetch and format these metrics.

### Task 14: Terminal UI Construction (TDD)
- [x] **Test:** Write tests to verify the Textual app mounts the correct widgets and loads data states.
- [x] **Implement:** Build the `Textual` application and wire it to the query layer.

## Phase 5: System Integration & Launch
### Task 15: Final Orchestrator Entrypoint
- [x] **Implement:** Add the CLI execution block to `src/python/app.py`.
- [x] **Implement:** Write `main.go` to route CLI commands (`watch` and `dashboard`) and bind the Python UI to Go's standard streams.

---

## Phase 6: Documentation & Maintenance
- [x] **Update:** Synchronize `MANUAL.md` with automated setup and resilience features.
- [x] **Update:** Synchronize `SPEC.md` and `MEMORY.md` with dynamic discovery and split column logic.
- [x] **Cleanup:** Remove stale `spendsight.db` files and verify data integrity.

---

## Phase 7: Resilience, Optimization & Architectural Hardening

### Task 16: Environment & Package Reproducibility
- [x] **Implement:** Create `pyproject.toml` with `uv` pinning runtime and dev dependencies.
- [x] **Verify:** Execute `uv sync` to ensure fully locked, reproducible virtual environment.

### Task 17: Database Deduplication & Idempotent Ingestion (TDD)
- [x] **Test:** Write `insert_dedup_test.go` to verify re-inserting duplicate transactions does not produce duplicate rows.
- [x] **Implement:** Update SQLite schema with `CONSTRAINT uq_transaction UNIQUE (transaction_date, amount, raw_description)`.
- [x] **Implement:** Update `InsertTransactions` in `insert.go` to use `INSERT OR IGNORE`.

### Task 18: Ingestion Quarantine & Dead-Letter Handling (TDD)
- [x] **Test:** Write `watcher_quarantine_test.go` simulating an unparsable statement and verifying it moves to `/ingest/failed/`.
- [x] **Implement:** Update `watcher.go` to create `/ingest/failed/` and move failed files on terminal retry failure.

### Task 19: Vendor Normalization Cache & Micro-Batching (TDD)
- [x] **Test:** Write tests in `test_llm.py` verifying cache lookups and micro-batch payload processing.
- [x] **Implement:** Add `vendor_cache` schema in SQLite and lookup/save functions.
- [x] **Implement:** Update `llm.py` to batch un-cached transactions (10–20 per request) using `BatchTransactionEntities`.

### Task 20: Codebase Hygiene & Redundancy Removal
- [x] **Cleanup:** Remove redundant `GEMINI.md` in favor of canonical `CONSTITUTION.md`.
- [x] **Cleanup:** Remove untracked compiled binary `spendsight` from the repository root.

---

## Phase 8: Configurable Local Model Selection (YAML-Driven)

### Task 21: LLM Model Configuration Loader (TDD)
- [x] **Test:** Write `test_config.py` tests verifying `load_llm_config` loads custom models and defaults to `gemma4:e2b` if omitted.
- [x] **Implement:** Add `LLMConfig` model and `load_llm_config` function to `config.py`.
- [x] **Implement:** Add default `llm:` section to `configs.yaml`.

### Task 22: Dynamic Model Routing in Normalization Engine (TDD)
- [x] **Test:** Update `test_llm.py` to verify `normalize_vendor`, `normalize_batch`, and `normalize_transactions` use the passed `model` parameter.
- [x] **Implement:** Update `llm.py` functions to accept `model: str = "gemma4:e2b"` and forward it to `client.chat.completions.create`.
- [x] **Implement:** Update `pipeline.py` to load `LLMConfig` from the specified config file and pass `model` into `normalize_transactions`.

---

## Phase 9: Vendor Canonicalization & Data Hygiene (TDD)

### Task 23: Post-Ingestion Vendor Canonicalization (TDD)
Consolidate typographically mismatched but semantically duplicate vendors (e.g. `TMOBILE`/`T-Mobile`, `Quickpark`/`Quick Park`) by lossless rename so `SUM(amount) GROUP BY vendor` nets the merged rows (see PRD *Vendor Canonicalization*, SPEC §6.5).
- [x] **T1 - Test (Red):** Author `tests/python/test_vendor_canonicalize.py` covering `canonical_key` equivalence, frequency-wins + lexicographic tie-breaking, single-vendor left untouched, **amount netting after rename** (mixed sign rows sum to the expected net), `vendor_cache` invalidation, idempotency (2nd run empty), and CLI exit codes. Verify the suite fails because the module is absent.
- [x] **T2 - Test+Impl `canonical_key` (Red->Green):** Add a failing test for `canonical_key` (lowercase + strip non-alphanumerics), then implement the pure function. *Decision: run-collapsing was dropped as it offered no benefit for the stated examples and risked false merges (KISS/YAGNI).*
- [x] **T3 - Test+Impl `compute_canonical_mappings` / `apply_canonicalization` (Red->Green):** Add failing tests for grouping by key and rename selection + that amounts are consolidated by aggregation (not row-merge), then implement the read function and the transactional apply.
- [x] **T4 - Test+Impl `vendor_cache` invalidation (Red->Green):** Add a failing test asserting non-canonical cache vendors are rewritten, then reconcile cache rows in `apply_canonicalization`.
- [x] **T5 - Test+Impl `canonicalize` CLI (Red->Green):** Add failing CLI tests (exit 0 on valid/empty DB, non-zero on bad DB path), then add the module entrypoint.
- [x] **T6 - Refactor & Quality Gate:** Eliminate duplication, enforce type hints, and run `pytest`, `ruff check .`, `mypy src` green before committing.

### Task 24: External Vendor Override Config (TDD)
Add a user-maintained `vendor_overrides.yaml` so semantic merges the mechanical key cannot infer can be declared without editing source.
- [x] **T1 - Test (Red):** Author `tests/python/test_vendor_synonyms.py` covering: default no-fold of `Landsend Inc.` vs `Lands' End`; fold applied when configured (class nets correctly, idempotent); `REVIEW_FLAGS` vendors never merged and surfaceable via `get_review_flags`.
- [x] **T2 - Test+Impl `load_override_config` / `apply_override_config` (Red->Green):** YAML loader with `synonyms` / `review_flags` sections, fail-fast on malformed config, no-op on absent file; module-level dict population.
- [x] **T3 - Test+Impl `--config` CLI flag (Red->Green):** `canonicalize --config <path>`; absent file prints a note and skips, present file is applied.
- [x] **T4 - Fix before/after count reporting:** Count distinct vendors separately so the reported counts reflect pre/post-merge state (not a post-mutation read).
- [x] **T5 - Refactor & commit:** Run full suite / ruff / mypy green; commit.

### Task 25: Auto-Canonicalization in the Go Success Path (TDD)
Wire a `Canonicalizer` into `ProcessFile` so canonicalization runs automatically after every successful ingestion — post-delete, non-fatal, threaded through `StartWatcher`→`{initialScan, watchLoop, processWithLog}`→`ProcessFile`. Wire `main.go` to `PythonCanonicalizer` (auto-run after every ingest); leave `NoopCanonicalizer` as the hermetic test default.
- [x] **T1 - Design (decision log):** Decide post-delete vs post-insert and non-fatal vs fatal semantics. *Decision:* post-delete, non-fatal — preserves the Ephemeral Data guarantee; idempotency self-heals any skipped run.
- [x] **T2 - Test (Red):** Add `tests/go/orchestrator/canonicalize_wiring_test.go` asserting exactly-once invocation with the database path on success, `NoopCanonicalizer` lets an ingest proceed without external processes, and the failure path invokes no canonicalization. Verify `go vet`/`go test` fails because `Canonicalizer` is absent.
- [x] **T3 - Impl `Canonicalizer`, `NoopCanonicalizer`, `PythonCanonicalizer` (Red->Green):** Add `src/go/orchestrator/canonicalize.go`; thread `canon Canonicalizer, dbPath string` through the orchestrator chain; wire `main.go` to `PythonCanonicalizer()`.
- [x] **T4 - Update pre-existing orchestrator tests:** Pass `NoopCanonicalizer` + `dbFile.Name()` so existing `ProcessFile` / `StartWatcher` call sites stay hermetic.
- [x] **T5 - Quality gate:** `go test -count=1 ./tests/go/...` green; `gofmt` clean on new files; end-to-end smoke on a scratch DB folds three typo-variant vendors (`T-Mobile` / `TMOBILE` / `T-MOBILE.`) into one via the real `PythonCanonicalizer`.
