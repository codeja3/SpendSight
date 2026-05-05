package pipeline

import (
	"encoding/json"
	"fmt"
)

// Payload matches the Python-to-Go JSON Contract in SPEC.md
type Payload struct {
	Metadata     Metadata      `json:"metadata"`
	Transactions []Transaction `json:"transactions"`
}

type Metadata struct {
	SourceFile       string `json:"source_file"`
	Format           string `json:"format"`
	ProcessedRecords int    `json:"processed_records"`
}

type Transaction struct {
	Date           string  `json:"date"`
	Amount         float64 `json:"amount"`
	RawDescription string  `json:"raw_description"`
	Vendor         string  `json:"vendor"`
	Category       string  `json:"category"`
}

// ParsePayload takes a raw JSON string and unmarshals it into our Go structs
func ParsePayload(rawJSON []byte) (*Payload, error) {
	// Defensive Programming: Fail-fast on empty input
	if len(rawJSON) == 0 {
		return nil, fmt.Errorf("cannot parse empty JSON payload")
	}

	var payload Payload
	err := json.Unmarshal(rawJSON, &payload)
	if err != nil {
		return nil, fmt.Errorf("failed to unmarshal JSON payload: %w", err)
	}

	return &payload, nil
}