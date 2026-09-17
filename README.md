# SpendSight 👁️💰

**A Privacy-First, Local LLM-Powered Personal Finance CLI**

SpendSight is a fully local, command-line application that ingests bank and credit card statements, intelligently normalizes vendor names using local Small Language Models (SLMs), and visualizes your spending habits through a rich interactive terminal dashboard. 

Built with an absolute commitment to data privacy, SpendSight operates completely offline. Your financial data never leaves your machine, and source statement files are securely and permanently deleted the moment they are successfully committed to the local database.

---

## 🏗️ System Architecture & Data Flow

SpendSight utilizes a strict separation of concerns, employing a "dumb pipe, smart endpoints" philosophy. Go acts as the secure, high-speed system orchestrator, while Python handles the heavy data wrangling and LLM inference.

```mermaid
sequenceDiagram
    participant U as User
    participant Dir as /ingest Directory
    participant Go as Go Orchestrator
    participant Py as Python Pipeline
    participant LLM as Ollama (Local SLM)
    participant DB as SQLite

    U->>Dir: Drops Statement (PDF/CSV)
    Go->>Dir: Watches for new files
    Dir-->>Go: File Detected
    Go->>Py: Trigger Extraction (CLI Exec)
    
    rect rgb(40, 44, 52)
        Note over Py,LLM: Python Processing Layer
        Py->>Py: Extract Tables (pdfplumber/csv)
        Py->>Py: Wrangle & Type Cast (polars)
        Py->>LLM: Raw Vendor String via Instructor/DSPy
        LLM-->>Py: Normalized Pydantic JSON
    end
    
    Py-->>Go: Return Structured Payload
    Go->>DB: Insert & Verify Records
    Go->>Dir: Securely Delete Original File
    Go->>Py: Post-Ingest Canonicalize (CLI Exec)
    Py->>DB: Reconcile Duplicate Vendors & Sync Cache
    
    U->>DB: Query via Terminal UI (Textual)
```

## 🗺️ The Development Journey (Methodology)
This project was built with unwavering adherence to rigorous software engineering principles:

Spec-Driven Development (SDD): No code was written until schemas, API boundaries, and database layouts were explicitly locked into a SPEC.md document.

Test-Driven Development (TDD): Every single module across both Go and Python was implemented by first writing failing unit/integration tests (pytest and go test), followed by defensive implementation code to turn them green.

CLI-First Context: Graphical IDEs were entirely eschewed. The entire pipeline, testing suite, and application interface natively live in the terminal.



## Phase Completion Log
✅ Phase 1: Environment Setup & Go Backend Orchestration (TDD)

✅ Phase 2: Python Extraction Pipeline & Config Management (TDD)

✅ Phase 3: LLM Transformation & Entity Normalization (SDD/TDD)

✅ Phase 4: Analytics Dashboard Data Contracts & Textual UI Construction (SDD/TDD)

✅ Phase 5: Final Integration & Go CLI Router Routing

✅ Phase 6: Documentation & Maintenance

✅ Phase 7: Resilience, Optimization & Architectural Hardening (Deduplication, Quarantine, Micro-Batching & Caching)

✅ Phase 8: Configurable Local Model Selection (YAML-Driven)

✅ Phase 9: Post-Ingestion Vendor Canonicalization & Data Hygiene (TDD)
- Automated post-delete vendor deduplication by lossless rename.
- Semantic synonym folds and review flags via `vendor_overrides.yaml`.
- Non-fatal auto-wiring in Go orchestrator success path.

✅ Phase 10: Comprehensive Vendor Directory & Search (TDD)
- Full vendor directory query with count, primary category resolution, net spend, and last active date.
- Dedicated "All Vendors" tab in Textual TUI with live keyboard search filter.

✅ Phase 11: Generalized Vendor Canonicalization & Ingestion Hardening (TDD)
- Algorithmic canonical key stripping web domains, leading articles, corporate suffixes, and retail qualifiers.
- Ingestion prompt and schema guidance enforcing the Parent Brand Rule.

✅ Phase 12: Positive Transaction (Income) Toggle (TDD)
- `expenses_only` query filter in DAL and interactive toggle button above main ledger.

✅ Phase 13: All Vendors Directory Expense Filter Toggle (TDD)
- `expenses_only` support in `get_vendor_directory` and toggle button in All Vendors tab.

✅ Phase 14: Vendor Directory Ranking by Dollars Spent (TDD)
- Ranked directory entries by total spend (`total_spend ASC`) from highest expenditure to lowest.

✅ Phase 15: Unbounded / Full Historical Ledger Listing (TDD)
- Lifted 50-item cap to list all transactions across all statements with full vertical scrolling.

--- 

Built with precision, paranoia, and Polars.