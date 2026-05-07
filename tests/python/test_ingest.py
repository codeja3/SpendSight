import pytest
import polars as pl
from src.python.config import BankProfile
from src.python.ingest import ingest_statement

def test_ingest_csv_enforces_canonical_standard(tmp_path):
    # 1. Setup: Create a dummy BankProfile
    profile = BankProfile(
        skip_rows=1,
        sign_multiplier=-1,  # This bank lists expenses as positive, so we must flip it
        column_mapping={
            "Post Date": "date",
            "Transaction Details": "raw_description",
            "Amount": "amount"
        }
    )

    # 2. Setup: Create a dummy CSV file with a junk header row
    csv_content = """Junk Bank Header Information...
Post Date,Transaction Details,Amount
2026-04-12,LOCAL COFFEE SHOP,45.50
2026-04-13,PAYROLL DEPOSIT,-1500.00
"""
    csv_file = tmp_path / "statement.csv"
    csv_file.write_text(csv_content)

    # 3. Execute: Call the ingestion pipeline
    df = ingest_statement(str(csv_file), profile)

    # 4. Verify: Check that Polars loaded it, skipped the row, mapped the names, and flipped the signs
    assert isinstance(df, pl.DataFrame)
    assert len(df) == 2
    
    # Check column mappings
    expected_columns = ["date", "raw_description", "amount"]
    assert all(col in df.columns for col in expected_columns)

    # Check the Canonical Sign Standard enforcement
    # The 45.50 expense should now be -45.50. The -1500 deposit should be 1500.
    amounts = df["amount"].to_list()
    assert amounts[0] == -45.50
    assert amounts[1] == 1500.00