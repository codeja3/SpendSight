package orchestrator

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"log"
	"os"
	"os/exec"
	"spendsight/src/go/db"
	"spendsight/src/go/pipeline"
)

// CommandExecutor defines the signature for calling the Python script.
// This allows us to inject a mock executor during unit tests.
type CommandExecutor func(filePath string, profile string) ([]byte, error)

// IsMock determines if the Python pipeline should run in mock mode.
var IsMock bool

// PythonExecutor is the real implementation that triggers the Python processing script via UV.
func PythonExecutor(filePath string, profile string) ([]byte, error) {
	// Signatures match the CLI Interface defined in SPEC.md
	args := []string{"run", "python", "-m", "src.python.pipeline", "process", "--input", filePath, "--profile", profile, "--output", "stdout"}
	if IsMock {
		args = append(args, "--mock")
	}
	
	cmd := exec.Command("uv", args...)
	
	output, err := cmd.Output()
	if err != nil {
		if exitErr, ok := err.(*exec.ExitError); ok {
			return nil, fmt.Errorf("python script failed: %s", string(exitErr.Stderr))
		}
		return nil, err
	}
	return output, nil
}

// GetAvailableProfiles queries the Python script for the list of profiles in configs.yaml.
func GetAvailableProfiles() ([]string, error) {
	cmd := exec.Command("uv", "run", "python", "-m", "src.python.pipeline", "list-profiles")
	
	// We ensure we run from the project root if possible, 
	// but usually the app is executed from the root.
	output, err := cmd.Output()
	if err != nil {
		if exitErr, ok := err.(*exec.ExitError); ok {
			return nil, fmt.Errorf("profile discovery failed (stderr: %s): %w", string(exitErr.Stderr), err)
		}
		return nil, fmt.Errorf("profile discovery failed: %w", err)
	}

	var profiles []string
	if err := json.Unmarshal(output, &profiles); err != nil {
		return nil, fmt.Errorf("failed to parse profile list: %w", err)
	}
	return profiles, nil
}

// ProcessFile coordinates the pipeline: extracts JSON, inserts to DB, deletes
// the source file (Ephemeral Data Rule), then reconciles vendor spellings.
//
// Canonicalization is a post-ingestion step (SPEC.md 6.5): it runs only after a
// successful commit and file deletion, so the ledger — not the ephemeral source
// — is what gets consolidated. A canonicalization failure is logged but never
// fails the ingestion: the source is already deleted and the commit already
// landed, so the ephemeral-data guarantee holds regardless, and idempotency
// means a later ingestion or a manual `canonicalize` run reconciles the state.
func ProcessFile(filePath string, profile string, database *sql.DB, execCmd CommandExecutor, canon Canonicalizer, dbPath string) error {
	if canon == nil {
		canon = NoopCanonicalizer
	}

	// 1. Trigger the extraction pipeline (Python script via Executor)
	rawJSON, err := execCmd(filePath, profile)
	if err != nil {
		return fmt.Errorf("extraction pipeline failed: %w", err)
	}

	// 2. Parse the returned JSON payload
	payload, err := pipeline.ParsePayload(rawJSON)
	if err != nil {
		return fmt.Errorf("failed to parse payload: %w", err)
	}

	// 3. Insert the records into the database
	err = db.InsertTransactions(database, payload)
	if err != nil {
		return fmt.Errorf("failed to insert transactions: %w", err)
	}

	// 4. Securely delete the original statement file (Ephemeral Data Rule)
	err = os.Remove(filePath)
	if err != nil {
		return fmt.Errorf("failed to delete source file %s: %w", filePath, err)
	}

	// 5. Reconcile vendor spellings. Non-fatal: a failure is logged but never
	// fails the ingestion, because the source is already deleted and the commit
	// already landed (see the function doc).
	if err := canon(dbPath); err != nil {
		log.Printf("WARNING: vendor canonicalization skipped: %v", err)
	}

	return nil
}