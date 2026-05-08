import sys
import json
import argparse
from pathlib import Path
from src.python.config import load_profile
from src.python.ingest import ingest_statement

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

    args = parser.parse_args()

    if args.command == "process":
        try:
            # 1. Load the profile and ingest the file
            profile = load_profile(args.profile, config_path=args.config)
            df = ingest_statement(args.input, profile)

            # 2. Handle Mock Mode (Phase 1 & 2 boundary)
            if args.mock:
                file_path = Path(args.input)
                # Strip the leading dot from the suffix (e.g., '.pdf' -> 'pdf')
                format_str = file_path.suffix.lower().replace('.', '')
                
                # Construct the exact JSON payload defined in SPEC.md
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
                
                # Print to stdout and exit cleanly for the Go orchestrator
                print(json.dumps(mock_payload, indent=2))
                sys.exit(0)
            else:
                # We will build this in Phase 3
                raise NotImplementedError("Live LLM extraction is deferred to Phase 3. Please use --mock.")
                
        except Exception as e:
            # Defensive Programming: Ensure Go catches the failure
            print(f"Pipeline Error: {e}", file=sys.stderr)
            sys.exit(1)

if __name__ == "__main__":
    main()