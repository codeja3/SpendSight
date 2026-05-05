package db

import (
	"database/sql"
	"fmt"
)

const createTableQuery = `
CREATE TABLE IF NOT EXISTS transactions (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	transaction_date TEXT NOT NULL,
	amount REAL NOT NULL,
	raw_description TEXT NOT NULL,
	vendor TEXT NOT NULL,
	category TEXT NOT NULL,
	source_format TEXT NOT NULL,
	ingested_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);`

// InitDB initializes the SQLite database and enforces the schema
func InitDB(dbPath string) (*sql.DB, error) {
	// Defensive Programming: Fail-fast on invalid input
	if dbPath == "" {
		return nil, fmt.Errorf("database path cannot be empty")
	}

	database, err := sql.Open("sqlite3", dbPath)
	if err != nil {
		return nil, fmt.Errorf("failed to open database connection: %w", err)
	}

	// Fail-fast: Verify the connection is actually alive before proceeding
	if err := database.Ping(); err != nil {
		database.Close() // Prevent resource leak on failure
		return nil, fmt.Errorf("failed to ping database: %w", err)
	}

	// Enforce the schema defined in SPEC.md
	_, err = database.Exec(createTableQuery)
	if err != nil {
		database.Close()
		return nil, fmt.Errorf("failed to create transactions table: %w", err)
	}

	return database, nil
}