import sys
import json
import argparse
from pathlib import Path
from src.python.config import load_profile
from src.python.ingest import ingest_statement
from src.python.llm import normalize_transactions

def main():
    parser = argparse.ArgumentParser(description="SpendSight Extraction Pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # The "process" command as defined by the Go Orchestrator
    process_parser = subparsers.add_parser("process")
    process_parser.add_argument("--input", required=True, help="Absolute path to the ingest file")
    process_parser.add_argument("--profile", required=True, help="Bank profile name from configs.yaml")
    process_parser.add_argument("--config", default="configs.yaml", help="Path to the yaml configuration file")
    process_parser.add_argument("--output", required=True, choices=["stdout"], help="Output destination")
    process_parser.add_argument("--mock", action="store_true", help="Bypass LLM and return predefined JSON")

    # The "list-profiles" command for Go discovery
    list_parser = subparsers.add_parser("list-profiles")
    list_parser.add_argument("--config", default="configs.yaml", help="Path to the yaml configuration file")

    args = parser.parse_args()

    if args.command == "list-profiles":
        import yaml
        try:
            with open(args.config, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f) or {}
            profiles = list(config_data.get("profiles", {}).keys())
            print(json.dumps(profiles))
            sys.exit(0)
        except Exception as e:
            print(f"Discovery Error: {e}", file=sys.stderr)
            sys.exit(1)

    if args.command == "process":
        try:
            # 1. Load the profile and ingest the file
            profile = load_profile(args.profile, config_path=args.config)
            df = ingest_statement(args.input, profile)
            
            file_path = Path(args.input)
            # Strip the leading dot from the suffix (e.g., '.pdf' -> 'pdf')
            format_str = file_path.suffix.lower().replace('.', '')

            # 2. Handle Mock Mode (Phase 1 & 2 boundary)
            if args.mock:
                mock_payload = {
                    "metadata": {
                        "source_file": file_path.name,
                        "format": format_str,
                        "processed_records": len(df)
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
                }
                print(json.dumps(mock_payload, indent=2))
                sys.exit(0)
                
            # 3. Handle Live LLM Mode (Phase 3 Integration)
            else:
                # Extract columns to native Python lists for processing
                raw_descriptions = df["raw_description"].to_list()
                dates = df["date"].to_list()
                amounts = df["amount"].to_list()
                
                # Send the batch to the local Ollama instance
                entities = normalize_transactions(raw_descriptions)
                
                # Zip the LLM entities back together with the original data
                transactions = []
                for i in range(len(df)):
                    transactions.append({
                        "date": str(dates[i]),
                        "amount": float(amounts[i]),
                        "raw_description": raw_descriptions[i],
                        "vendor": entities[i].vendor,
                        "category": entities[i].category
                    })
                    
                live_payload = {
                    "metadata": {
                        "source_file": file_path.name,
                        "format": format_str,
                        "processed_records": len(df)
                    },
                    "transactions": transactions
                }
                
                # Print to stdout and exit cleanly for the Go orchestrator
                print(json.dumps(live_payload, indent=2))
                sys.exit(0)
                
        except Exception as e:
            # Defensive Programming: Ensure Go catches the failure
            print(f"Pipeline Error: {e}", file=sys.stderr)
            sys.exit(1)

if __name__ == "__main__":
    main()