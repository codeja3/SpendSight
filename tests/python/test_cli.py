import subprocess
import json
import pytest
from pathlib import Path

def test_cli_mock_mode_outputs_valid_json(tmp_path):
    # 1. Setup: Create a valid dummy CSV statement and a dummy config
    csv_file = tmp_path / "statement.csv"
    csv_file.write_text("Date,Description,Amount\n2026-04-12,LOCAL COFFEE SHOP,-45.50\n")
    
    config_file = tmp_path / "configs.yaml"
    config_file.write_text("""
profiles:
  test_bank:
    skip_rows: 0
    sign_multiplier: 1
    column_mapping:
      Date: date
      Description: raw_description
      Amount: amount
    """)

    # 2. Execute: Run the CLI exactly as the Go orchestrator will (using --mock)
    cmd = [
        "python", "-m", "src.python.pipeline", 
        "process", 
        "--input", str(csv_file), 
        "--profile", "test_bank", 
        "--config", str(config_file), 
        "--mock", 
        "--output", "stdout"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)

    # 3. Verify: Check that it didn't crash
    assert result.returncode == 0, f"CLI crashed with error: {result.stderr}"

    # Verify: Check that stdout contains valid JSON matching the SPEC.md contract
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        pytest.fail(f"stdout was not valid JSON. Output was: {result.stdout}")

    assert "metadata" in payload
    assert "transactions" in payload
    assert payload["metadata"]["format"] == "csv"
    assert payload["metadata"]["processed_records"] == 1
    assert len(payload["transactions"]) > 0