package pipeline_test

import (
	"spendsight/src/go/pipeline"
	"testing"
)

func TestParsePayload(t *testing.T) {
	// 1. Setup: A mock JSON string matching exactly what is defined in SPEC.md
	mockJSON := []byte(`{
		"metadata": {
			"source_file": "statement_april_2026.pdf",
			"format": "pdf",
			"processed_records": 1
		},
		"transactions": [
			{
				"date": "2026-04-12",
				"amount": -45.50,
				"raw_description": "SQ *LOCAL COFFEE SHOP NEW YORK NY",
				"vendor": "Local Coffee Shop",
				"category": "Dining"
			}
		]
	}`)

	// 2. Execute: Call the function under test
	payload, err := pipeline.ParsePayload(mockJSON)
	if err != nil {
		t.Fatalf("ParsePayload returned an error: %v", err)
	}
	if payload == nil {
		t.Fatalf("Expected parsed payload, got nil")
	}

	// 3. Verify: Check that the unmarshaling mapped the fields correctly
	if payload.Metadata.Format != "pdf" {
		t.Errorf("Expected format 'pdf', got '%s'", payload.Metadata.Format)
	}
	if len(payload.Transactions) != 1 {
		t.Fatalf("Expected 1 transaction, got %d", len(payload.Transactions))
	}
	if payload.Transactions[0].Vendor != "Local Coffee Shop" {
		t.Errorf("Expected vendor 'Local Coffee Shop', got '%s'", payload.Transactions[0].Vendor)
	}
	if payload.Transactions[0].Amount != -45.50 {
		t.Errorf("Expected amount -45.50, got %f", payload.Transactions[0].Amount)
	}
}