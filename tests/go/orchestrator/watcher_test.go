package orchestrator_test

import (
	"database/sql"
	"os"
	"path/filepath"
	"spendsight/src/go/db"
	"spendsight/src/go/orchestrator"
	"testing"
	"time"

	_ "github.com/mattn/go-sqlite3"
)

func TestWatcher_Success(t *testing.T) {
	// 1. Setup temporary directory for watching
	watchDir, err := os.MkdirTemp("", "spendsight_ingest_*")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(watchDir)

	// 2. Setup temporary DB
	dbPath := filepath.Join(watchDir, "test.db")
	database, err := db.InitDB(dbPath)
	if err != nil {
		t.Fatalf("Failed to init DB: %v", err)
	}
	defer database.Close()

	// 3. Mock Command Executor
	mockExecutor := func(filePath string, profile string) ([]byte, error) {
		return []byte(`{
			"metadata": {"source_file": "test.pdf", "format": "pdf", "processed_records": 1},
			"transactions": [{"date": "2026-04-12", "amount": -10.0, "raw_description": "TEST", "vendor": "Test Vendor", "category": "Dining"}]
		}`), nil
	}

	// 4. Start Watcher in a goroutine
	// We need a way to stop it, so we'll use a context later, but for now let's just use a channel or similar
	stopChan := make(chan struct{})
	go func() {
		// StartWatcher should be a blocking call
		err := orchestrator.StartWatcher(watchDir, database, mockExecutor, stopChan)
		if err != nil && err != sql.ErrConnDone { // ErrConnDone is expected on close
			// In a real test we'd handle this better
		}
	}()

	// Give it a moment to start
	time.Sleep(100 * time.Millisecond)

	// 5. Drop a file into the directory
	testFile := filepath.Join(watchDir, "statement.pdf")
	err = os.WriteFile(testFile, []byte("dummy pdf content"), 0644)
	if err != nil {
		t.Fatalf("Failed to write test file: %v", err)
	}

	// 6. Wait for processing (Debounce + Execution time)
	// Spec says 500ms debounce
	time.Sleep(1 * time.Second)

	// 7. Verify DB Insertion
	var count int
	err = database.QueryRow("SELECT count(*) FROM transactions").Scan(&count)
	if err != nil || count != 1 {
		t.Errorf("Expected 1 transaction in DB, got %d", count)
	}

	// 8. Verify File Deletion
	if _, err := os.Stat(testFile); !os.IsNotExist(err) {
		t.Errorf("Expected source file to be deleted")
	}

	// 9. Stop the watcher
	close(stopChan)
}

func TestWatcher_InitialScan(t *testing.T) {
	// 1. Setup temporary directory with an existing file
	watchDir, err := os.MkdirTemp("", "spendsight_initial_*")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(watchDir)

	testFile := filepath.Join(watchDir, "existing.csv")
	err = os.WriteFile(testFile, []byte("date,amount,description\n2026-01-01,-5.0,Existing"), 0644)
	if err != nil {
		t.Fatalf("Failed to write test file: %v", err)
	}

	// 2. Setup temporary DB
	dbPath := filepath.Join(watchDir, "test_initial.db")
	database, err := db.InitDB(dbPath)
	if err != nil {
		t.Fatalf("Failed to init DB: %v", err)
	}
	defer database.Close()

	// 3. Mock Command Executor
	mockExecutor := func(filePath string, profile string) ([]byte, error) {
		return []byte(`{
			"metadata": {"source_file": "existing.csv", "format": "csv", "processed_records": 1},
			"transactions": [{"date": "2026-01-01", "amount": -5.0, "raw_description": "Existing", "vendor": "Existing Vendor", "category": "Other"}]
		}`), nil
	}

	// 4. Start Watcher (it should process existing files immediately)
	stopChan := make(chan struct{})
	go orchestrator.StartWatcher(watchDir, database, mockExecutor, stopChan)

	// 5. Wait for processing
	time.Sleep(500 * time.Millisecond)

	// 6. Verify DB Insertion
	var count int
	err = database.QueryRow("SELECT count(*) FROM transactions").Scan(&count)
	if err != nil || count != 1 {
		t.Errorf("Expected 1 transaction from initial scan, got %d", count)
	}

	// 7. Verify File Deletion
	if _, err := os.Stat(testFile); !os.IsNotExist(err) {
		t.Errorf("Expected existing file to be deleted")
	}

	close(stopChan)
}
