package orchestrator_test

import (
	"os"
	"testing"
	"spendsight/src/go/db"
	"spendsight/src/go/orchestrator"

	_ "github.com/mattn/go-sqlite3"
)

func TestProcessFile(t *testing.T) {
	// 1. Setup: Create a temporary DB and a temporary "statement" file
	dbFile, _ := os.CreateTemp("", "test_spendsight_orchestrator_*.db")
	defer os.Remove(dbFile.Name())

	database, err := db.InitDB(dbFile.Name())
	if err != nil {
		t.Fatalf("Failed to initialize database: %v", err)
	}
	defer database.Close()

	statementFile, _ := os.CreateTemp("", "amex_statement_*.pdf")
	statementPath := statementFile.Name()
	statementFile.Close() // Close it so the orchestrator can delete it

	// 2. Setup: Create a Mock Command Executor
	// This simulates our Python script returning the JSON contract
	mockExecutor := func(filePath string, profile string) ([]byte, error) {
		return []byte(`{
			"metadata": {
				"source_file": "test.pdf",
				"format": "pdf",
				"processed_records": 1
			},
			"transactions": [
				{
					"date": "2026-04-12",
					"amount": -45.50,
					"raw_description": "SQ *LOCAL COFFEE SHOP",
					"vendor": "Local Coffee Shop",
					"category": "Dining"
				}
			]
		}`), nil
	}

	// 3. Execute: Run the orchestrator
	err = orchestrator.ProcessFile(statementPath, "amex_credit", database, mockExecutor)
	if err != nil {
		t.Fatalf("ProcessFile failed: %v", err)
	}

	// 4. Verify DB Insertion
	var count int
	err = database.QueryRow("SELECT count(*) FROM transactions").Scan(&count)
	if err != nil || count != 1 {
		t.Fatalf("Expected 1 row in database, got %d. DB Error: %v", count, err)
	}

	// 5. Verify File Deletion (The Ephemeral Data Rule)
	if _, err := os.Stat(statementPath); !os.IsNotExist(err) {
		t.Fatalf("Expected source file to be deleted, but it still exists: %s", statementPath)
	}
}