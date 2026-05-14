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

// StartWatcher begins monitoring the target directory for new financial statements.
// It performs an initial scan before entering the event-listening loop.
func StartWatcher(dirPath string, database *sql.DB, execCmd CommandExecutor, stopChan <-chan struct{}) error {
	// 1. Initial Scan
	if err := initialScan(dirPath, database, execCmd); err != nil {
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
	return watchLoop(watcher, database, execCmd, stopChan)
}

func initialScan(dirPath string, database *sql.DB, execCmd CommandExecutor) error {
	entries, err := os.ReadDir(dirPath)
	if err != nil {
		return err
	}

	for _, entry := range entries {
		if !entry.IsDir() && isSupportedFile(entry.Name()) {
			filePath := filepath.Join(dirPath, entry.Name())
			processWithLog(filePath, database, execCmd)
		}
	}
	return nil
}

func watchLoop(watcher *fsnotify.Watcher, database *sql.DB, execCmd CommandExecutor, stopChan <-chan struct{}) error {
	var mu sync.Mutex
	timers := make(map[string]*time.Timer)
	
	// Sequential processing channel
	queue := make(chan string, 10)
	
	// Worker goroutine
	go func() {
		for filePath := range queue {
			processWithLog(filePath, database, execCmd)
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

func processWithLog(filePath string, database *sql.DB, execCmd CommandExecutor) {
	fmt.Printf("Processing detected file: %s\n", filePath)
	
	// Basic profile mapping (to be refined in Phase 2)
	profile := "standard"
	if strings.Contains(strings.ToLower(filePath), "amex") {
		profile = "amex"
	}

	err := ProcessFile(filePath, profile, database, execCmd)
	if err != nil {
		log.Printf("FAILED to process %s: %v", filePath, err)
	} else {
		fmt.Printf("SUCCESSfully processed and deleted: %s\n", filePath)
	}
}
