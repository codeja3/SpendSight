# SpendSight TODO & Milestone Tracker

## Phase 1: Environment & Backend Orchestration (Golang/SQLite)
This phase focuses on building the "dumb pipe"—the Go orchestrator that watches the directory, executes the Python script, and saves the resulting JSON payload into the SQLite database.

### Task 1: Project Scaffolding
- [ ] Initialize Git repository.
- [ ] Initialize Go module (`go mod init spendsight`).
- [ ] Initialize Python environment (`uv venv` and `uv pip install polars pydantic pdfplumber instructor`).
- [ ] Create basic directory structure (`/ingest`, `/src/go`, `/src/python`, `/tests/go`, `/tests/python`).

### Task 2: Database Initialization (TDD)
- [ ] **Test:** Write `db_test.go` to verify SQLite connection and schema creation.
- [ ] **Implement:** Write `db.go` to execute the schema creation defined in `SPEC.md`.
- [ ] **Refactor:** Ensure context managers/defensive programming are used for DB connections.

### Task 3: JSON Payload Ingestion (TDD)
- [ ] **Test:** Write `ingest_test.go` using a mock JSON payload (matching `SPEC.md`) to verify successful parsing into Go structs.
- [ ] **Implement:** Write `ingest.go` to unmarshal the Python JSON output.

### Task 4: Database Insertion (TDD)
- [ ] **Test:** Write `insert_test.go` to verify the parsed Go structs are correctly inserted into the `transactions` table.
- [ ] **Implement:** Write the `InsertTransactions` function.

### Task 5: The File Watcher & Orchestrator (TDD)
- [ ] **Test:** Write `watcher_test.go` to simulate a file drop and verify it triggers the mock CLI command.
- [ ] **Implement:** Write `watcher.go` to monitor the `/ingest` directory and execute the Python pipeline via standard CLI execution (`--mock` flag for now).
- [ ] **Implement:** Add the secure deletion routine to permanently remove the file upon successful DB commit.

---

## Phase 2: Extraction Pipeline (Python)
*(Tasks to be defined upon completion of Phase 1)*

## Phase 3: Transformation & Normalization (LLM)
*(Tasks to be defined upon completion of Phase 2)*

## Phase 4: Visualization (Textual Dashboard)
*(Tasks to be defined upon completion of Phase 3)*
