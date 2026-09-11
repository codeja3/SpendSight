package db_test

import (
	"os"
	"path/filepath"
	"testing"
	"spendsight/src/go/db"
	"spendsight/src/go/pipeline"

	_ "github.com/mattn/go-sqlite3"
)

func TestInsertTransactions_Deduplication(t *testing.T) {
	// 1. Setup: Create a temporary DB and initialize schema
	tmpDir, err := os.MkdirTemp("", "test_spendsight_dedup_*")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tmpDir)

	dbPath := filepath.Join(tmpDir, "dedup_test.db")
	database, err := db.InitDB(dbPath)
	if err != nil {
		t.Fatalf("Failed to initialize database: %v", err)
	}
	defer database.Close()

	payload := &pipeline.Payload{
		Metadata: pipeline.Metadata{
			SourceFile:       "statement1.pdf",
			Format:           "pdf",
			ProcessedRecords: 2,
		},
		Transactions: []pipeline.Transaction{
			{
				Date:           "2026-04-12",
				Amount:         -45.50,
				RawDescription: "SQ *LOCAL COFFEE SHOP",
				Vendor:         "Local Coffee Shop",
				Category:       "Dining",
			},
			{
				Date:           "2026-04-13",
				Amount:         -12.00,
				RawDescription: "UBER TRIP",
				Vendor:         "Uber",
				Category:       "Transportation",
			},
		},
	}

	// 2. First Insert: Should insert 2 transactions
	if err := db.InsertTransactions(database, payload); err != nil {
		t.Fatalf("First InsertTransactions failed: %v", err)
	}

	var count int
	if err := database.QueryRow("SELECT count(*) FROM transactions").Scan(&count); err != nil {
		t.Fatalf("Failed to query transactions count: %v", err)
	}
	if count != 2 {
		t.Fatalf("Expected 2 rows after first insert, got %d", count)
	}

	// 3. Second Insert (Duplicate Statement / Overlapping Transactions):
	// Re-inserting the exact same transactions must NOT fail and must NOT create duplicate rows.
	duplicatePayload := &pipeline.Payload{
		Metadata: pipeline.Metadata{
			SourceFile:       "statement2.pdf",
			Format:           "pdf",
			ProcessedRecords: 2,
		},
		Transactions: []pipeline.Transaction{
			{
				Date:           "2026-04-12",
				Amount:         -45.50,
				RawDescription: "SQ *LOCAL COFFEE SHOP",
				Vendor:         "Local Coffee Shop",
				Category:       "Dining",
			},
			{
				Date:           "2026-04-14",
				Amount:         -85.00,
				RawDescription: "GROCERY MART",
				Vendor:         "Grocery Mart",
				Category:       "Groceries",
			},
		},
	}

	if err := db.InsertTransactions(database, duplicatePayload); err != nil {
		t.Fatalf("Second InsertTransactions (with duplicate) should not fail, got: %v", err)
	}

	// 4. Verify: Total rows should be 3 (2 unique from payload 1 + 1 new unique from payload 2)
	if err := database.QueryRow("SELECT count(*) FROM transactions").Scan(&count); err != nil {
		t.Fatalf("Failed to query transactions count: %v", err)
	}
	if count != 3 {
		t.Errorf("Expected 3 unique rows after idempotent insert, got %d", count)
	}
}
