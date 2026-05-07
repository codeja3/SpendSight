package db_test

import (
	"os"
	"testing"
	"spendsight/src/go/db"
	"spendsight/src/go/pipeline"

	_ "github.com/mattn/go-sqlite3"
)

func TestInsertTransactions(t *testing.T) {
	// 1. Setup: Create a temporary DB and initialize the schema
	tmpFile, err := os.CreateTemp("", "test_spendsight_insert_*.db")
	if err != nil {
		t.Fatalf("Failed to create temp file: %v", err)
	}
	defer os.Remove(tmpFile.Name())

	database, err := db.InitDB(tmpFile.Name())
	if err != nil {
		t.Fatalf("Failed to initialize database: %v", err)
	}
	defer database.Close()

	// Create a dummy payload matching our structs
	dummyPayload := &pipeline.Payload{
		Metadata: pipeline.Metadata{
			SourceFile:       "test.pdf",
			Format:           "pdf",
			ProcessedRecords: 1,
		},
		Transactions: []pipeline.Transaction{
			{
				Date:           "2026-04-12",
				Amount:         -45.50,
				RawDescription: "SQ *LOCAL COFFEE SHOP",
				Vendor:         "Local Coffee Shop",
				Category:       "Dining",
			},
		},
	}

	// 2. Execute: Attempt to insert the dummy payload
	err = db.InsertTransactions(database, dummyPayload)
	if err != nil {
		t.Fatalf("InsertTransactions failed: %v", err)
	}

	// 3. Verify: Check the database to see if the row exists
	var count int
	err = database.QueryRow("SELECT count(*) FROM transactions").Scan(&count)
	if err != nil {
		t.Fatalf("Failed to query database: %v", err)
	}
	if count != 1 {
		t.Errorf("Expected 1 row in transactions table, found %d", count)
	}
}