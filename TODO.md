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
- [x] **Implement:** Add the secure deletion routine to permanently remove the file upon successful DB commit.

---

## Phase 2: Extraction Pipeline (Python)
### Task 6: Profile Configuration Loader (TDD)
- [ ] **Test:** Write `test_config.py` to verify YAML loading and strict Pydantic validation.
- [ ] **Implement:** Write `config.py` to parse `configs.yaml` and Fail-Fast on missing profiles.

### Task 7: Data Ingestion & Canonical Normalization (TDD)
- [ ] **Test:** Write `test_ingest.py` to verify CSV/PDF parsing into a Polars DataFrame.
- [ ] **Implement:** Write `ingest.py` to map raw columns and enforce the Canonical Sign Standard via the profile's `sign_multiplier`.

### Task 8: Python CLI Entrypoint (TDD)
- [ ] **Test:** Write `test_cli.py` to simulate the Go orchestrator's CLI invocation.
- [ ] **Implement:** Write `pipeline.py` to wire the config and ingest modules together and print the final JSON to stdout.
