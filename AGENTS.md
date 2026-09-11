# AGENTS.md — Autonomous Spec-Driven & Test-Driven Development Protocol

## 1. Operating Principles
- **Autonomous Execution:** Work end-to-end without stopping for intermediate affirmations, small-step confirmations, or high-level design chit-chat. Rely on static checks, file inspections, and test outputs as the primary feedback loop.
- **Single Source of Truth:** Code follows contracts strictly. Always read `PRD.md`, `SPEC.md`, `TODO.md`, and `MEMORY.md` before generating or modifying code.
- **Zero Premature Implementation:** Never write application logic without an authoritative, failing test case demonstrating the missing functionality.

---

## 2. Documentation Contracts
Maintain and respect the following contract files:
1. `PRD.md`: Defines product intent, constraints, and business domain boundaries.
2. `SPEC.md`: Defines architectural contracts, interface signatures, data schemas, and edge cases.
3. `TODO.md`: Master checklist of atomic work items. Only pick unchecked items (`[ ]`).
4. `MEMORY.md`: Log of technical decisions, unresolved debt, and discovered project constraints.
5. `CONSTITUTION.md`: Environment setup, command aliases, and testing configurations.

---

## 3. Strict TDD Loop (Red-Green-Refactor)

For every task selected from `TODO.md`:

### Step 1: Red (Authoritative Failure)
- Write targeted test cases in `tests/` matching the contract in `SPEC.md`.
- Run pytest: `pytest tests/test_<target>.py -v`.
- **Verification:** Ensure tests execute and **fail** due to missing logic or assertion mismatch, not due to missing imports or syntax errors in the test itself.

### Step 2: Green (Minimal Implementation)
- Write the minimal code in `src/` required to satisfy the test assertions.
- Run pytest: `pytest tests/test_<target>.py -v`.
- **Verification:** Iterate on implementation until all target tests pass. Do not write anticipatory code beyond what the current test demands.

### Step 3: Refactor & Quality Gate
- Eliminate duplication, optimize performance, and enforce strict type hints.
- Run the full test suite and linters:
  ```bash
  pytest
  ruff check .
  mypy src