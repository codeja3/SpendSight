package db_test

import (
	"os"
	"testing"
	"spendsight/src/go/db" 

	_ "github.com/mattn/go-sqlite3" 
)

func TestInitDB(t *testing.T) {
	tmpFile, err := os.CreateTemp("", "test_spendsight_*.db")
	if err != nil {
		t.Fatalf("Failed to create temp file: %v", err)
	}
	defer os.Remove(tmpFile.Name()) 

	database, err := db.InitDB(tmpFile.Name())
	if err != nil {
		t.Fatalf("InitDB returned an error: %v", err)
	}
	if database == nil {
		t.Fatalf("Expected database connection, got nil")
	}
	defer database.Close()

	var tableName string
	query := `SELECT name FROM sqlite_master WHERE type='table' AND name='transactions';`
	err = database.QueryRow(query).Scan(&tableName)
	if err != nil {
		t.Fatalf("Transactions table not found. Schema creation failed: %v", err)
	}
}
