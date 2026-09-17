package orchestrator_test

import (
	"fmt"
	"os"
	"path/filepath"
	"testing"
	"time"

	"spendsight/src/go/db"
	"spendsight/src/go/orchestrator"

	_ "github.com/mattn/go-sqlite3"
)

func TestWatcher_QuarantineFailedStatement(t *testing.T) {
	// 1. Setup temporary directory for watching
	watchDir, err := os.MkdirTemp("", "spendsight_quarantine_*")
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

	// 3. Mock Command Executor to always simulate pipeline failure across all profiles
	mockExecutor := func(filePath string, profile string) ([]byte, error) {
		return nil, fmt.Errorf("parsing failed: invalid format for profile %s", profile)
	}
	mockDiscovery := func() ([]string, error) {
		return []string{"checking", "credit_account_with_split"}, nil
	}

	// 4. Start Watcher
	stopChan := make(chan struct{})
	go func() {
		_ = orchestrator.StartWatcher(watchDir, database, mockExecutor, mockDiscovery, orchestrator.NoopCanonicalizer, dbPath, stopChan)
	}()
	time.Sleep(100 * time.Millisecond)

	// 5. Drop an unparsable statement into the watch directory
	testFileName := "corrupt_statement.csv"
	testFilePath := filepath.Join(watchDir, testFileName)
	if err := os.WriteFile(testFilePath, []byte("garbage,unparsable,data"), 0644); err != nil {
		t.Fatalf("Failed to write test file: %v", err)
	}

	// 6. Wait for debouncing and retries across profiles
	time.Sleep(1500 * time.Millisecond)

	// 7. Verify file was moved from watchDir to watchDir/failed/
	if _, err := os.Stat(testFilePath); !os.IsNotExist(err) {
		t.Errorf("Expected original file to be removed from %s", testFilePath)
	}

	failedDir := filepath.Join(watchDir, "failed")
	quarantinedFile := filepath.Join(failedDir, testFileName)
	if _, err := os.Stat(quarantinedFile); os.IsNotExist(err) {
		t.Errorf("Expected failed file to be quarantined in %s", quarantinedFile)
	}

	close(stopChan)
}
