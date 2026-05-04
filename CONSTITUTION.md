# CONSTITUTION.md: SpendSight Engineering & AI Standards

This document defines the immutable rules of engagement for developing SpendSight. It governs both the architectural design of the software and the collaborative workflow between the developer and the AI assistant. 

## 1. Development Workflow & AI Collaboration
* **CLI-Exclusive Execution:** All development, testing, and execution must occur directly via the Command Line Interface (CLI). Workflows tailored for Graphical IDEs (like Jupyter Notebooks or VS Code integrated runners) are strictly prohibited.
* **Strict Test-Driven Development (TDD):** Tests strictly dictate implementation. For every task, xUnit-style tests must be written and executed *before* any core implementation logic is authored.
* **Spec-Driven Development (SDD):** `SPEC.md` is the ultimate source of truth. System specifications, API contracts, and data schemas must be explicitly defined and locked in `SPEC.md` before pipeline construction begins.
* **The "Ping-Pong" Protocol:** 1. Define task.
  2. AI writes the failing test.
  3. Developer executes via CLI and provides output.
  4. AI writes the minimum implementation to pass.
  5. Refactor and document.

## 2. Core Design Principles
* **Single Responsibility Principle (SRP):** One module, one class, one job. If a class's purpose cannot be described without using the word "and," it must be split. (e.g., Extract validation logic from extraction logic).
* **Defensive Programming (Fail-Fast):** Validate inputs immediately. Use custom exceptions for validation errors. Do not swallow exceptions; propagate them up or handle them explicitly. 
* **Encapsulation & Abstraction:** Hide internal state. Expose behavior, not data. Protect internal mechanisms from arbitrary modification.
* **Extensibility (Open/Closed):** Code should be open for extension but closed for modification. Use strategy patterns, interfaces, and composition over deep inheritance chains or monolithic `if/else` blocks.
* **Simplicity (KISS, DRY, YAGNI):** Prefer simple solutions. Extract common logic to maintain a single source of truth. Do not build abstractions for hypothetical future needs.

## 3. Language & Environmental Standards

### Python Ecosystem Mandates
* **Cross-Platform Portability:** String concatenation for paths is prohibited. `pathlib` must be used for all file system interactions.
* **Type Safety:** Strict type hints are mandatory for all function signatures and class properties.
* **Data Structures:** Use `dataclasses` (or Pydantic models via the LLM extraction layer) for immutable data passing.
* **Resource Management:** Context managers (`with` statements) are mandatory for file I/O and database connections to ensure automatic cleanup.
* **Interface Design:** Use the `abc` module to define clear abstract base classes for swappable components.

### Golang Ecosystem Mandates
* **Explicit Error Handling:** Go's paradigm of returning errors as values must be strictly followed. Errors must be checked immediately (fail-fast).
* **Interface-Driven:** Rely on small, focused interfaces to ensure components (like the directory watcher and database connector) remain loosely coupled and easily testable.

## 4. SpendSight Domain Rules
* **Absolute Privacy:** The system must never make external network calls for data processing. All LLM inference must occur via the local server (Ollama).
* **Ephemeral Source Data:** Under no circumstances should source PDF/CSV statements be retained. The Golang orchestrator must execute a permanent deletion immediately following a successful database commit.
* **Least Privilege Logging:** Logs must never output sensitive financial data. Account numbers must be masked, and transaction payloads should only log metadata (e.g., timestamps and IDs), not raw amounts or vendors.


## 5. Package Management & Environment
* **No Monolithic Environments:** Monolithic environment managers (like Conda) and full-stack containerization (like Docker) are explicitly rejected to preserve bare-metal hardware access for local LLM inference on Apple Silicon.
* **Python Dependency Management:** `uv` is the mandated package manager for the Python extraction layer. Standard `requirements.txt` or `pyproject.toml` will be used, and execution will occur within a `uv`-managed virtual environment.
* **Go Dependency Management:** The standard `go mod` toolchain is mandatory. No third-party package managers will be used for Go.
* **System Services:** The local inference server (Ollama) must run as a native system service on the host OS to ensure direct GPU/Metal access without virtualization overhead.
