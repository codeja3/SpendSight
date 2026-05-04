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
    * *Decision:* Gracefully fail and require manual YAML profile creation for Phase 1. Zero-shot LLM profile inference is deferred to Phase 3.
    * *Reasoning:* Prevents silent data corruption and keeps the initial TDD loop focused on core orchestration rather than edge cases.


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
