package orchestrator

import (
	"fmt"
	"os/exec"
)

// Canonicalizer reconciles typographically distinct but semantically duplicate
// vendor spellings after a successful ingestion. It is a post-ingestion step
// (SPEC.md 6.5): by the time it runs, the source statement has already been
// committed to the database and deleted, leaving only the ledger to consolidate.
//
// It is intentionally an optional, idempotent step: the orchestrator never fails
// an ingestion because canonicalization could not run. A canonicalization
// failure is logged and swallowed so the ephemeral-data guarantee (source file
// deleted immediately after a successful commit) always holds, and so a later
// ingestion — or a manual `canonicalize` run — reconciles any skipped state.
type Canonicalizer func(dbPath string) error

// NoopCanonicalizer is the default Canonicalizer used by unit tests and by any
// deployment that does not wish to auto-canonicalize. It performs no work and
// never invokes an external process, keeping ingestion hermetic.
var NoopCanonicalizer Canonicalizer = func(string) error { return nil }

// PythonCanonicalizer wires a Canonicalizer to the canonicalization module via
// the project's CLI contract (SPEC.md 6.5.4):
//
//	uv run python -m src.python.vendor_canonicalize canonicalize --input <db>
//
// It returns an error on a non-zero exit (a malformed override config, a missing
// module, or a Python/Go toolchain failure) so the caller can log it. The
// caller is responsible for treating that failure as non-fatal.
func PythonCanonicalizer() Canonicalizer {
	return func(dbPath string) error {
		cmd := exec.Command("uv", "run", "python", "-m", "src.python.vendor_canonicalize", "canonicalize", "--input", dbPath)
		output, err := cmd.CombinedOutput()
		if err != nil {
			return fmt.Errorf("vendor canonicalization failed: %s", string(output))
		}
		return nil
	}
}
