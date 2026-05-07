package db

import (
	"database/sql"
	"fmt"
	"spendsight/src/go/pipeline"
)

// InsertTransactions takes a parsed JSON payload and inserts the records into SQLite
func InsertTransactions(database *sql.DB, payload *pipeline.Payload) error {
	// Defensive Programming: Fail-fast on nil inputs or empty transactions
	if database == nil {
		return fmt.Errorf("database connection cannot be nil")
	}
	if payload == nil || len(payload.Transactions) == 0 {
		return fmt.Errorf("payload contains no transactions to insert")
	}

	// Begin a SQL transaction to ensure atomicity (all-or-nothing insert)
	tx, err := database.Begin()
	if err != nil {
		return fmt.Errorf("failed to begin database transaction: %w", err)
	}
	// Defer a rollback. If tx.Commit() succeeds later, this becomes a no-op.
	// If the function returns early due to an error, this cleans up the state.
	defer tx.Rollback()

	// Prepare the insert statement for efficiency and security
	stmt, err := tx.Prepare(`
		INSERT INTO transactions (
			transaction_date, amount, raw_description, vendor, category, source_format
		) VALUES (?, ?, ?, ?, ?, ?)
	`)
	if err != nil {
		return fmt.Errorf("failed to prepare insert statement: %w", err)
	}
	defer stmt.Close()

	// Iterate through the payload and execute the statement for each record
	sourceFormat := payload.Metadata.Format
	for _, t := range payload.Transactions {
		_, err := stmt.Exec(t.Date, t.Amount, t.RawDescription, t.Vendor, t.Category, sourceFormat)
		if err != nil {
			return fmt.Errorf("failed to insert transaction (vendor: %s): %w", t.Vendor, err)
		}
	}

	// Commit the transaction to disk
	if err := tx.Commit(); err != nil {
		return fmt.Errorf("failed to commit database transaction: %w", err)
	}

	return nil
}