package main

import (
	"fmt"
	"os"
	"os/exec"
	"spendsight/src/go/db"
)

func main() {
	if len(os.Args) < 2 {
		printUsage()
		os.Exit(1)
	}

	command := os.Args[1]

	switch command {
	case "init":
		initDatabase()
	case "dashboard":
		launchDashboard()
	case "watch":
		fmt.Println("SpendSight Watcher initialized. Monitoring /ingest directory for statements...")
	default:
		fmt.Printf("Unknown command: '%s'\n\n", command)
		printUsage()
		os.Exit(1)
	}
}

func initDatabase() {
	fmt.Println("Initializing SpendSight database...")
	// Calls the Phase 1 Go function to create the schema safely
	_, err := db.InitDB("spendsight.db")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to initialize database: %v\n", err)
		os.Exit(1)
	}
	fmt.Println("Success! 'spendsight.db' is ready.")
}

func launchDashboard() {
	cmd := exec.Command("uv", "run", "python", "-m", "src.python.app")
	cmd.Stdin = os.Stdin
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr

	if err := cmd.Run(); err != nil {
		fmt.Fprintf(os.Stderr, "\nDashboard exited with error: %v\n", err)
		os.Exit(1)
	}
}

func printUsage() {
	fmt.Println("SpendSight: Privacy-First Personal Finance CLI")
	fmt.Println("Usage: spendsight <command>")
	fmt.Println("\nCommands:")
	fmt.Println("  init       Initialize the SQLite database schema")
	fmt.Println("  watch      Monitor the /ingest directory for new statements")
	fmt.Println("  dashboard  Launch the interactive Textual analytics UI")
}