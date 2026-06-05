package orchestrator

import (
	"database/sql"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"

	"github.com/fsnotify/fsnotify"
)

// ProfileDiscovery defines the signature for fetching available bank profiles.
type ProfileDiscovery func() ([]string, error)

// StartWatcher begins monitoring the target directory for new financial statements.
// It performs an initial scan before entering the event-listening loop.
func StartWatcher(dirPath string, database *sql.DB, execCmd CommandExecutor, discoverProfiles ProfileDiscovery, stopChan <-chan struct{}) error {
	// 1. Initial Scan
	if err := initialScan(dirPath, database, execCmd, discoverProfiles); err != nil {
		return fmt.Errorf("initial scan failed: %w", err)
	}

	// 2. Setup fsnotify
	watcher, err := fsnotify.NewWatcher()
	if err != nil {
		return fmt.Errorf("failed to create watcher: %w", err)
	}
	defer watcher.Close()

	if err := watcher.Add(dirPath); err != nil {
		return fmt.Errorf("failed to watch directory: %w", err)
	}

	fmt.Printf("Watching directory: %s\n", dirPath)

	// 3. Watch Loop
	return watchLoop(watcher, database, execCmd, discoverProfiles, stopChan)
}

func initialScan(dirPath string, database *sql.DB, execCmd CommandExecutor, discoverProfiles ProfileDiscovery) error {
	entries, err := os.ReadDir(dirPath)
	if err != nil {
		return err
	}

	for _, entry := range entries {
		if !entry.IsDir() && isSupportedFile(entry.Name()) {
			filePath := filepath.Join(dirPath, entry.Name())
			processWithLog(filePath, database, execCmd, discoverProfiles)
		}
	}
	return nil
}

func watchLoop(watcher *fsnotify.Watcher, database *sql.DB, execCmd CommandExecutor, discoverProfiles ProfileDiscovery, stopChan <-chan struct{}) error {
	var mu sync.Mutex
	timers := make(map[string]*time.Timer)
	
	// Sequential processing channel
	queue := make(chan string, 10)
	
	// Worker goroutine
	go func() {
		for filePath := range queue {
			processWithLog(filePath, database, execCmd, discoverProfiles)
		}
	}()

	for {
		select {
		case event, ok := <-watcher.Events:
			if !ok {
				return nil
			}

			// Supported events: Create or Rename (Move-in)
			if event.Has(fsnotify.Create) || event.Has(fsnotify.Rename) {
				if isSupportedFile(event.Name) {
					mu.Lock()
					if timer, exists := timers[event.Name]; exists {
						timer.Stop()
					}
					
					// Debounce: Wait 500ms before adding to queue
					filePath := event.Name
					timers[event.Name] = time.AfterFunc(500*time.Millisecond, func() {
						queue <- filePath
						mu.Lock()
						delete(timers, filePath)
						mu.Unlock()
					})
					mu.Unlock()
				}
			}

		case err, ok := <-watcher.Errors:
			if !ok {
				return nil
			}
			log.Printf("Watcher error: %v", err)

		case <-stopChan:
			close(queue)
			return nil
		}
	}
}

func isSupportedFile(fileName string) bool {
	ext := strings.ToLower(filepath.Ext(fileName))
	return ext == ".pdf" || ext == ".csv"
}

func processWithLog(filePath string, database *sql.DB, execCmd CommandExecutor, discoverProfiles ProfileDiscovery) {
	fmt.Printf("Processing detected file: %s\n", filePath)
	
	// 1. Get all available profiles for dynamic retry
	allProfiles, err := discoverProfiles()
	if err != nil {
		log.Printf("ERROR: Could not discover profiles: %v", err)
		return
	}

	// 2. Initial Heuristic Guess
	lowerPath := strings.ToLower(filePath)
	initialProfile := "checking" 
	if strings.Contains(lowerPath, "credit") || 
	   strings.Contains(lowerPath, "visa") || 
	   strings.Contains(lowerPath, "mastercard") ||
	   strings.Contains(lowerPath, "amex") ||
	   strings.Contains(lowerPath, "chase") {
		// If it's likely a credit card, try credit_account_with_split then others
		initialProfile = "credit_account_with_split"
	}

	// 3. Execution Loop with Exhaustive Retry
	// We start with the initialProfile, then try all others if it fails.
	tried := make(map[string]bool)
	
	// First attempt with the heuristic
	fmt.Printf("Attempting first pass with heuristic profile: %s\n", initialProfile)
	err = ProcessFile(filePath, initialProfile, database, execCmd)
	tried[initialProfile] = true

	if err != nil {
		log.Printf("Heuristic profile '%s' failed. Entering exhaustive retry...", initialProfile)
		
		success := false
		for _, profile := range allProfiles {
			if tried[profile] {
				continue
			}
			
			log.Printf("Retrying with profile: %s", profile)
			err = ProcessFile(filePath, profile, database, execCmd)
			tried[profile] = true
			
			if err == nil {
				success = true
				break
			}
		}
		
		if !success {
			log.Printf("FAILED to process %s after trying all %d profiles.", filePath, len(allProfiles))
		} else {
			fmt.Printf("SUCCESSfully processed and deleted: %s\n", filePath)
		}
	} else {
		fmt.Printf("SUCCESSfully processed and deleted: %s\n", filePath)
	}
}
