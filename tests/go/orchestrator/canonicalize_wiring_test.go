package orchestrator_test

import (
	"os"
	"testing"

	"spendsight/src/go/db"
	"spendsight/src/go/orchestrator"

	_ "github.com/mattn/go-sqlite3"
)

// recordingCanonicalizer returns a Canonicalizer that records every database path
// it is asked to canonicalize, so we can assert the orchestrator actually
// invokes it on the success path.
func recordingCanonicalizer() (orchestrator.Canonicalizer, *[]string) {
	calls := &[]string{}
	canon := func(dbPath string) error {
		*calls = append(*calls, dbPath)
		return nil
	}
	return canon, calls
}

func newMockExecutor(payload string) orchestrator.CommandExecutor {
	return func(filePath string, profile string) ([]byte, error) {
		return []byte(payload), nil
	}
}

// oneRow is a single successful payload shared by the canonicalization-wiring tests.
const oneRow = `{
					"metadata": {"source_file": "test.pdf", "format": "pdf", "processed_records": 1},
					"transactions": [{"date": "2026-04-12", "amount": -45.50, "raw_description": "SQ *LOCAL COFFEE SHOP", "vendor": "Local Coffee Shop", "category": "Dining"}]
				}`

// TestProcessFile_RunsCanonicalizationOnSuccess locks in the wiring contract:
// after a transaction is inserted and the source file deleted, the orchestrator
// must invoke the supplied Canonicalizer with the database path. This is the
// "post-ingestion vendor canonicalization" behavior from SPEC.md 6.5 / PRD 2.
func TestProcessFile_RunsCanonicalizationOnSuccess(t *testing.T) {
	dbFile, _ := os.CreateTemp("", "test_spendsight_canon_*.db")
	defer os.Remove(dbFile.Name())
	dbPath := dbFile.Name()

	database, err := db.InitDB(dbPath)
	if err != nil {
		t.Fatalf("Failed to initialize database: %v", err)
	}
	defer database.Close()

	statementFile, _ := os.CreateTemp("", "amex_statement_*.pdf")
	statementPath := statementFile.Name()
	statementFile.Close()

	can, calls := recordingCanonicalizer()
	err = orchestrator.ProcessFile(statementPath, "amex_credit", database, newMockExecutor(oneRow), can, dbPath)
	if err != nil {
		t.Fatalf("ProcessFile failed: %v", err)
	}

	// 1. Canonicalization was invoked exactly once, with the database path.
	if len(*calls) != 1 {
		t.Fatalf("Expected canonicalization to run exactly once, got %d calls", len(*calls))
	}
	if (*calls)[0] != dbPath {
		t.Fatalf("Expected canonicalizer invoked with %q, got %q", dbPath, (*calls)[0])
	}

	// 2. The insert still happened (canonicalization is post-ingestion, not part of it).
	var count int
	if err := database.QueryRow("SELECT count(*) FROM transactions").Scan(&count); err != nil {
		t.Fatalf("Failed to query database: %v", err)
	}
	if count != 1 {
		t.Fatalf("Expected 1 row in transactions, got %d", count)
	}

	// 3. Ephemeral-data rule: the source is deleted before canonicalization runs.
	if _, err := os.Stat(statementPath); !os.IsNotExist(err) {
		t.Fatalf("Expected source file to be deleted, but it still exists: %s", statementPath)
	}
}

// TestProcessFile_NoopCanonicalizerIsSafeDefault verifies the default wiring used
// by the pre-existing orchestrator tests: a NoopCanonicalizer must let a
// successful ingest proceed without invoking any external process.
func TestProcessFile_NoopCanonicalizerIsSafeDefault(t *testing.T) {
	dbFile, _ := os.CreateTemp("", "test_spendsight_canon_noop_*.db")
	defer os.Remove(dbFile.Name())
	dbPath := dbFile.Name()

	database, err := db.InitDB(dbPath)
	if err != nil {
		t.Fatalf("Failed to initialize database: %v", err)
	}
	defer database.Close()

	statementFile, _ := os.CreateTemp("", "amex_statement_*.pdf")
	statementPath := statementFile.Name()
	statementFile.Close()

	err = orchestrator.ProcessFile(statementPath, "amex_credit", database, newMockExecutor(oneRow), orchestrator.NoopCanonicalizer, dbPath)
	if err != nil {
		t.Fatalf("ProcessFile with NoopCanonicalizer failed: %v", err)
	}

	var count int
	if err := database.QueryRow("SELECT count(*) FROM transactions").Scan(&count); err != nil || count != 1 {
		t.Fatalf("Expected 1 row in transactions, got %d (err: %v)", count, err)
	}
}

// TestProcessFile_SkipsCanonicalizationOnFailure guards against canonicalization
// leaking onto the failure path: when the payload yields no transactions,
// InsertTransactions fails and ProcessFile returns that error BEFORE touching
// canonicalization or the file.
func TestProcessFile_SkipsCanonicalizationOnFailure(t *testing.T) {
	dbFile, _ := os.CreateTemp("", "test_spendsight_canon_fail_*.db")
	defer os.Remove(dbFile.Name())
	dbPath := dbFile.Name()

	database, err := db.InitDB(dbPath)
	if err != nil {
		t.Fatalf("Failed to initialize database: %v", err)
	}
	defer database.Close()

	empty := `{"metadata": {"source_file": "test.csv", "format": "csv", "processed_records": 0}, "transactions": []}`

	can, calls := recordingCanonicalizer()
	err = orchestrator.ProcessFile(dbPath, "checking", database, newMockExecutor(empty), can, dbPath)
	if err == nil {
		t.Fatalf("Expected ProcessFile to fail when payload has no transactions")
	}
	if len(*calls) != 0 {
		t.Fatalf("Expected canonicalization NOT to run on the failure path, got %d calls", len(*calls))
	}
}

// TestProcessFile_CanonicalizationErrorIsNonFatal asserts that a failure returned
// by Canonicalizer is swallowed as a warning and does not fail ProcessFile or rollback
// the ingestion (SPEC 6.5.8).
func TestProcessFile_CanonicalizationErrorIsNonFatal(t *testing.T) {
	dbFile, _ := os.CreateTemp("", "test_spendsight_canon_err_*.db")
	defer os.Remove(dbFile.Name())
	dbPath := dbFile.Name()

	database, err := db.InitDB(dbPath)
	if err != nil {
		t.Fatalf("Failed to initialize database: %v", err)
	}
	defer database.Close()

	statementFile, _ := os.CreateTemp("", "amex_statement_*.pdf")
	statementPath := statementFile.Name()
	statementFile.Close()

	failingCanon := func(string) error {
		return os.ErrPermission
	}

	err = orchestrator.ProcessFile(statementPath, "amex_credit", database, newMockExecutor(oneRow), failingCanon, dbPath)
	if err != nil {
		t.Fatalf("Expected ProcessFile to succeed despite canonicalization error, got: %v", err)
	}

	// 1. Transaction was still committed.
	var count int
	if err := database.QueryRow("SELECT count(*) FROM transactions").Scan(&count); err != nil || count != 1 {
		t.Fatalf("Expected 1 row in transactions, got %d (err: %v)", count, err)
	}

	// 2. Source file was still deleted.
	if _, err := os.Stat(statementPath); !os.IsNotExist(err) {
		t.Fatalf("Expected source file to be deleted, but it still exists")
	}
}

// TestProcessFile_NilCanonicalizerIsSafe ensures that passing nil for canon
// defaults to NoopCanonicalizer rather than panicking with a nil-pointer dereference.
func TestProcessFile_NilCanonicalizerIsSafe(t *testing.T) {
	dbFile, _ := os.CreateTemp("", "test_spendsight_canon_nil_*.db")
	defer os.Remove(dbFile.Name())
	dbPath := dbFile.Name()

	database, err := db.InitDB(dbPath)
	if err != nil {
		t.Fatalf("Failed to initialize database: %v", err)
	}
	defer database.Close()

	statementFile, _ := os.CreateTemp("", "amex_statement_*.pdf")
	statementPath := statementFile.Name()
	statementFile.Close()

	err = orchestrator.ProcessFile(statementPath, "amex_credit", database, newMockExecutor(oneRow), nil, dbPath)
	if err != nil {
		t.Fatalf("Expected ProcessFile to succeed with nil Canonicalizer, got: %v", err)
	}
}

// TestPythonCanonicalizer_EndToEnd exercises the real PythonCanonicalizer
// against a temporary database with typographically mismatched vendors.
func TestPythonCanonicalizer_EndToEnd(t *testing.T) {
	dbFile, err := os.CreateTemp("", "test_spendsight_pycanon_*.db")
	if err != nil {
		t.Fatalf("Failed to create temp db: %v", err)
	}
	defer os.Remove(dbFile.Name())
	dbPath := dbFile.Name()

	database, err := db.InitDB(dbPath)
	if err != nil {
		t.Fatalf("Failed to initialize database: %v", err)
	}
	defer database.Close()

	// Seed typo-variant vendors:
	seed := []struct {
		d, raw, vendor string
		a              float64
	}{
		{"2026-01-01", "A", "T-Mobile", -10},
		{"2026-01-02", "B", "TMOBILE", -10},
		{"2026-01-03", "C", "T-MOBILE.", -10},
	}
	for _, s := range seed {
		_, err := database.Exec(
			"INSERT INTO transactions (transaction_date,amount,raw_description,vendor,category,source_format) VALUES (?,?,?,?,?,?)",
			s.d, s.a, s.raw, s.vendor, "Telecom", "csv",
		)
		if err != nil {
			t.Fatalf("Failed to seed transaction: %v", err)
		}
	}

	canon := orchestrator.PythonCanonicalizer()
	if err := canon(dbPath); err != nil {
		t.Fatalf("PythonCanonicalizer failed: %v", err)
	}

	var count int
	if err := database.QueryRow("SELECT COUNT(DISTINCT vendor) FROM transactions").Scan(&count); err != nil {
		t.Fatalf("Failed to count distinct vendors: %v", err)
	}
	if count != 1 {
		t.Fatalf("Expected 1 consolidated vendor, got %d", count)
	}
}

