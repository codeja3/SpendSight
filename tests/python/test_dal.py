import pytest
import sqlite3
from src.python.dal import SpendSightDAL, LedgerRow, AggregateRow

@pytest.fixture
def mock_db(tmp_path):
    # Setup: Create a temporary SQLite database with our exact schema
    db_path = tmp_path / "spendsight.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        transaction_date TEXT NOT NULL,
        amount REAL NOT NULL,
        raw_description TEXT NOT NULL,
        vendor TEXT NOT NULL,
        category TEXT NOT NULL,
        source_format TEXT NOT NULL,
        ingested_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Setup: Insert dummy data (mixing expenses and income)
    data = [
        ("2026-04-10", -50.0, "SQ *COFFEE", "Coffee Shop", "Dining", "csv"),
        ("2026-04-11", -150.0, "AMZN", "Amazon", "Shopping", "csv"),
        ("2026-04-12", -10.0, "SQ *COFFEE", "Coffee Shop", "Dining", "csv"),
        ("2026-04-13", -2000.0, "RENT", "Landlord", "Housing", "csv"),
        ("2026-04-14", 5000.0, "PAYROLL", "Employer", "Income", "csv"), # Income
    ]

    cursor.executemany("""
        INSERT INTO transactions (transaction_date, amount, raw_description, vendor, category, source_format)
        VALUES (?, ?, ?, ?, ?, ?)
    """, data)
    conn.commit()
    conn.close()

    return str(db_path)

def test_get_ledger(mock_db):
    dal = SpendSightDAL(mock_db)
    ledger = dal.get_ledger(limit=2, offset=0)

    assert len(ledger) == 2
    assert isinstance(ledger[0], LedgerRow)
    # Verify ordering: newest transaction (04-14) should be first
    assert ledger[0].date == "2026-04-14"

def test_get_top_vendors(mock_db):
    dal = SpendSightDAL(mock_db)
    vendors = dal.get_top_vendors(limit_n=2)

    assert len(vendors) == 2
    # Verify aggregation: Landlord should be top expense (-2000)
    assert vendors[0].name == "Landlord"
    assert vendors[0].total_spend == -2000.0

def test_get_bottom_vendors(mock_db):
    dal = SpendSightDAL(mock_db)
    vendors = dal.get_bottom_vendors(limit_n=2)

    assert len(vendors) == 2
    # Verify aggregation: Coffee Shop should be closest to zero (-60 total)
    assert vendors[0].name == "Coffee Shop"
    assert vendors[0].total_spend == -60.0 

def test_get_top_categories(mock_db):
    dal = SpendSightDAL(mock_db)
    cats = dal.get_top_categories(limit_n=1)

    assert len(cats) == 1
    # Verify filtering: Income (+5000) is ignored, Housing (-2000) is top expense category
    assert cats[0].name == "Housing"
    assert cats[0].total_spend == -2000.0

def test_get_top_vendors_by_category(mock_db):
    dal = SpendSightDAL(mock_db)
    vendors = dal.get_top_vendors_by_category("Dining", limit_n=5)

    assert len(vendors) == 1
    assert vendors[0].name == "Coffee Shop"
    assert vendors[0].total_spend == -60.0