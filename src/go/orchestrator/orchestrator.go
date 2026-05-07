package orchestrator

import (
	"database/sql"
	"fmt"
	"os"
	"spendsight/src/go/db"
	"spendsight/src/go/pipeline"
)

// CommandExecutor defines the signature for calling the Python script.
// This allows us to inject a mock executor during unit tests.
type CommandExecutor func(filePath string, profile string) ([]byte, error)

// ProcessFile coordinates the pipeline: extracts JSON, inserts to DB, and deletes the file.
func ProcessFile(filePath string, profile string, database *sql.DB, execCmd CommandExecutor) error {
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

	return nil
}