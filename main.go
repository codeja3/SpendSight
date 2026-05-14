package main

import (
	"fmt"
	"os"
	"os/exec"
	"os/signal"
	"spendsight/src/go/db"
	"spendsight/src/go/orchestrator"
	"syscall"
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
		startWatcher()
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

func startWatcher() {
	// 1. Ensure /ingest exists
	if _, err := os.Stat("./ingest"); os.IsNotExist(err) {
		err := os.Mkdir("./ingest", 0755)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Failed to create /ingest directory: %v\n", err)
			os.Exit(1)
		}
	}

	// 2. Open DB Connection
	database, err := db.InitDB("spendsight.db")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to connect to database: %v\n", err)
		os.Exit(1)
	}
	defer database.Close()

	// 3. Setup termination signaling
	stopChan := make(chan struct{})
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, os.Interrupt, syscall.SIGTERM)

	go func() {
		<-sigChan
		fmt.Println("\nStopping SpendSight Watcher...")
		close(stopChan)
	}()

		// 4. Start the Watcher (Blocking call)
	fmt.Println("SpendSight Watcher active. Drop PDF or CSV statements into './ingest'.")
	err = orchestrator.StartWatcher("./ingest", database, orchestrator.PythonExecutor, orchestrator.GetAvailableProfiles, stopChan)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Watcher encountered a fatal error: %v\n", err)
		os.Exit(1)
	}
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