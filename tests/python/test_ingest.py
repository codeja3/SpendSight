import pytest
import polars as pl
from src.python.config import BankProfile
from src.python.ingest import ingest_statement
from unittest.mock import patch, MagicMock


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

def test_ingest_split_debit_credit_columns(tmp_path):
    # Setup: Create a profile with split debit and credit columns
    profile = BankProfile(
        skip_rows=0,
        sign_multiplier=1,
        date_format="%Y-%m-%d",
        column_mapping={
            "Transaction Date": "date",
            "Description": "raw_description",
            "Debit": "debit",
            "Credit": "credit"
        }
    )

    # Setup: Create a CSV with separate Debit and Credit columns
    csv_content = """Transaction Date,Posted Date,Card No.,Description,Category,Debit,Credit
2026-04-27,2026-04-29,9172,MEIJER STORE #068,Merchandise,,1.80
2026-04-27,2026-04-28,9172,MEIJER STORE #068,Merchandise,99.33,
2026-04-14,2026-04-14,1446,GOOGLE *Google One,Internet,19.99,
"""
    csv_file = tmp_path / "split_statement.csv"
    csv_file.write_text(csv_content)

    # Execute
    df = ingest_statement(str(csv_file), profile)

    # Verify
    assert isinstance(df, pl.DataFrame)
    assert len(df) == 3
    assert "amount" in df.columns
    
    amounts = df["amount"].to_list()
    # Credit 1.80 -> 1.80 (Refund/Payment)
    # Debit 99.33 -> -99.33 (Expense)
    # Debit 19.99 -> -19.99 (Expense)
    assert amounts[0] == 1.80
    assert amounts[1] == -99.33
    assert amounts[2] == -19.99

def test_ingest_normalizes_dates(tmp_path):
    # Setup: Profile with a non-ISO date format (MM/DD/YYYY)
    profile = BankProfile(
        skip_rows=0,
        sign_multiplier=1,
        date_format="%m/%d/%Y",
        column_mapping={
            "Date": "date",
            "Description": "raw_description",
            "Amount": "amount"
        }
    )

    csv_content = """Date,Description,Amount
05/13/2026,TMOBILE,-153.28
01/01/2026,OPENING BALANCE,1000.00
"""
    csv_file = tmp_path / "dates.csv"
    csv_file.write_text(csv_content)

    # Execute
    df = ingest_statement(str(csv_file), profile)

    # Verify
    dates = df["date"].to_list()
    assert dates[0] == "2026-05-13" # Normalized to ISO
    assert dates[1] == "2026-01-01" # Normalized to ISO

def test_ingest_pdf_enforces_canonical_standard(tmp_path):
    # 1. Setup: Create a profile for a standard credit card PDF
    profile = BankProfile(
        skip_rows=0, 
        sign_multiplier=1, # Assume this bank uses negative for expenses normally
        column_mapping={
            "Date": "date",
            "Description": "raw_description",
            "Amount": "amount"
        }
    )

    # 2. Setup: Create a dummy file just so path.is_file() passes
    pdf_file = tmp_path / "statement.pdf"
    pdf_file.write_bytes(b"%PDF-dummy") 

    # 3. Setup: Mock pdfplumber to return a pre-parsed 2D array (table)
    with patch("src.python.ingest.pdfplumber.open") as mock_pdf:
        mock_page = MagicMock()
        # Simulating what pdfplumber.extract_table() returns
        mock_page.extract_table.return_value = [
            ["Date", "Description", "Amount"],
            ["2026-04-12", "LOCAL COFFEE SHOP", "-45.50"],
            ["2026-04-13", "PAYROLL DEPOSIT", "1500.00"]
        ]
        # Attach the fake page to the fake PDF object
        mock_pdf.return_value.__enter__.return_value.pages = [mock_page]

        # 4. Execute: Call the ingestion pipeline
        df = ingest_statement(str(pdf_file), profile)

    # 5. Verify: Check that Polars built the dataframe and mapped the data
    assert isinstance(df, pl.DataFrame)
    assert len(df) == 2
    assert all(col in df.columns for col in ["date", "raw_description", "amount"])

    amounts = df["amount"].to_list()
    assert amounts[0] == -45.50
    assert amounts[1] == 1500.00