import sqlite3

import pytest

from src.python.dal import LedgerRow, SpendSightDAL, VendorDirectoryRow


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

def test_get_ledger_expenses_only(mock_db):
    dal = SpendSightDAL(mock_db)
    # When expenses_only=True, positive transaction (2026-04-14, 5000.0) is excluded
    ledger = dal.get_ledger(limit=10, offset=0, expenses_only=True)

    assert len(ledger) == 4
    assert all(row.amount < 0 for row in ledger)
    # Newest expense should be Landlord (2026-04-13)
    assert ledger[0].date == "2026-04-13"
    assert ledger[0].vendor == "Landlord"


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


def test_get_vendor_directory(mock_db):
    dal = SpendSightDAL(mock_db)
    directory = dal.get_vendor_directory()

    # 4 distinct vendors: Amazon, Coffee Shop, Employer, Landlord
    assert len(directory) == 4
    for row in directory:
        assert isinstance(row, VendorDirectoryRow)

    # Alphabetical order: Amazon, Coffee Shop, Employer, Landlord
    assert [v.name for v in directory] == ["Amazon", "Coffee Shop", "Employer", "Landlord"]

    # Check Coffee Shop aggregation (2 transactions, net -60.0, Dining, last 2026-04-12)
    coffee = next(v for v in directory if v.name == "Coffee Shop")
    assert coffee.transaction_count == 2
    assert coffee.total_spend == -60.0
    assert coffee.primary_category == "Dining"
    assert coffee.last_active_date == "2026-04-12"

    # Check Employer income aggregation (1 transaction, +5000.0)
    employer = next(v for v in directory if v.name == "Employer")
    assert employer.transaction_count == 1
    assert employer.total_spend == 5000.0
    assert employer.primary_category == "Income"
    assert employer.last_active_date == "2026-04-14"


def test_get_vendor_directory_empty(tmp_path):
    db_path = tmp_path / "empty.db"
    conn = sqlite3.connect(db_path)
    conn.execute("""
    CREATE TABLE transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        transaction_date TEXT NOT NULL,
        amount REAL NOT NULL,
        raw_description TEXT NOT NULL,
        vendor TEXT NOT NULL,
        category TEXT NOT NULL,
        source_format TEXT NOT NULL
    );
    """)
    conn.commit()
    conn.close()

    dal = SpendSightDAL(str(db_path))
    assert dal.get_vendor_directory() == []


def test_get_vendor_directory_primary_category_frequency(tmp_path):
    db_path = tmp_path / "freq.db"
    conn = sqlite3.connect(db_path)
    conn.execute("""
    CREATE TABLE transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        transaction_date TEXT NOT NULL,
        amount REAL NOT NULL,
        raw_description TEXT NOT NULL,
        vendor TEXT NOT NULL,
        category TEXT NOT NULL,
        source_format TEXT NOT NULL
    );
    """)
    # Target has 2 Groceries and 1 Household
    data = [
        ("2026-01-01", -20.0, "TARGET 1", "Target", "Groceries", "csv"),
        ("2026-01-02", -50.0, "TARGET 2", "Target", "Household", "csv"),
        ("2026-01-03", -30.0, "TARGET 3", "Target", "Groceries", "csv"),
    ]
    conn.executemany("INSERT INTO transactions (transaction_date, amount, raw_description, vendor, category, source_format) VALUES (?, ?, ?, ?, ?, ?)", data)
    conn.commit()
    conn.close()

    dal = SpendSightDAL(str(db_path))
    rows = dal.get_vendor_directory()
    assert len(rows) == 1
    assert rows[0].name == "Target"
    assert rows[0].transaction_count == 3
    assert rows[0].total_spend == -100.0
    assert rows[0].primary_category == "Groceries"
    assert rows[0].last_active_date == "2026-01-03"


def test_get_vendor_directory_search_filter(mock_db):
    dal = SpendSightDAL(mock_db)

    # Substring search case-insensitive
    res_coffee = dal.get_vendor_directory(search="coffee")
    assert len(res_coffee) == 1
    assert res_coffee[0].name == "Coffee Shop"

    res_amaz = dal.get_vendor_directory(search="AMAZ")
    assert len(res_amaz) == 1
    assert res_amaz[0].name == "Amazon"

    res_none = dal.get_vendor_directory(search="nonexistent")
    assert res_none == []