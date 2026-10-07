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


def test_get_ledger_unbounded(mock_db):
    dal = SpendSightDAL(mock_db)
    # When limit=None, all transactions in mock_db (5 total) are returned without truncation
    ledger = dal.get_ledger(limit=None)
    assert len(ledger) == 5
    assert [row.date for row in ledger] == ["2026-04-14", "2026-04-13", "2026-04-12", "2026-04-11", "2026-04-10"]



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

    # Ordered from highest expenditure to lowest: Landlord (-2000), Amazon (-150), Coffee Shop (-60), Employer (+5000)
    assert [v.name for v in directory] == ["Landlord", "Amazon", "Coffee Shop", "Employer"]

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


def test_get_vendor_directory_expenses_only(mock_db):
    dal = SpendSightDAL(mock_db)

    # In mock_db:
    # Amazon: -150.0 (1 txn)
    # Coffee Shop: -50.0, -10.0 (2 txns, -60.0)
    # Employer: 5000.0 (1 txn) -> pure income
    # Landlord: -2000.0 (1 txn)
    
    # When expenses_only=False, 4 vendors including Employer
    all_rows = dal.get_vendor_directory(expenses_only=False)
    assert len(all_rows) == 4
    assert any(v.name == "Employer" for v in all_rows)

    # When expenses_only=True, Employer is excluded because it has only positive amount
    # Ordered from highest expenditure to lowest: Landlord (-2000), Amazon (-150), Coffee Shop (-60)
    expenses_rows = dal.get_vendor_directory(expenses_only=True)
    assert len(expenses_rows) == 3
    assert [v.name for v in expenses_rows] == ["Landlord", "Amazon", "Coffee Shop"]
    assert all(v.total_spend < 0 for v in expenses_rows)


def test_get_executive_kpis(mock_db):
    dal = SpendSightDAL(mock_db)
    kpis = dal.get_executive_kpis()

    # mock_db distinct vendors:
    # Amazon: -150.0
    # Coffee Shop: -60.0
    # Landlord: -2000.0
    # Employer: 5000.0
    # Total spends list: [-2000.0, -150.0, -60.0, 5000.0]
    # Distinct active vendors = 4
    # Median spend = (-150.0 + -60.0) / 2 = -105.0
    assert kpis.active_vendors_count == 4
    assert kpis.median_spend_per_vendor == -105.0


def test_get_transactions_by_vendor(mock_db):
    dal = SpendSightDAL(mock_db)
    txns = dal.get_transactions_by_vendor("Coffee Shop")

    assert len(txns) == 2
    assert all(t.vendor == "Coffee Shop" for t in txns)
    # Ordered by date descending: 2026-04-12 (-10.0) then 2026-04-10 (-50.0)
    assert txns[0].amount == -10.0
    assert txns[0].date == "2026-04-12"
    assert txns[1].amount == -50.0
    assert txns[1].date == "2026-04-10"


def test_get_median_spend_trend_monthly_adaptive(mock_db):
    dal = SpendSightDAL(mock_db)
    trend = dal.get_median_spend_trend()

    # In mock_db, all transactions fall in April 2026 (1 month total: < 24 months -> monthly)
    assert trend.granularity == "month"
    assert len(trend.points) == 1
    assert trend.points[0].period == "2026-04"
    assert trend.points[0].median_spend == -105.0


def test_get_median_spend_trend_adaptive_granularity(tmp_path):
    # Test quarterly (>24 months) and annual (>16 quarters) adaptation
    db_path = tmp_path / "trend_test.db"
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

    # Create 30 consecutive monthly records across 2023, 2024, 2025
    # Distinct months = 30 (> 24 months, <= 16 quarters -> quarterly)
    records = []
    for year in [2023, 2024]:
        for month in range(1, 13):
            records.append((f"{year}-{month:02d}-15", -100.0, "DESC", "VendorA", "Cat", "csv"))
    for month in range(1, 7):
        records.append((f"2025-{month:02d}-15", -100.0, "DESC", "VendorA", "Cat", "csv"))

    cursor.executemany("""
        INSERT INTO transactions (transaction_date, amount, raw_description, vendor, category, source_format)
        VALUES (?, ?, ?, ?, ?, ?)
    """, records)
    conn.commit()
    conn.close()

    dal = SpendSightDAL(str(db_path))
    quarterly_trend = dal.get_median_spend_trend()
    assert quarterly_trend.granularity == "quarter"
    assert len(quarterly_trend.points) > 0
    assert "Q" in quarterly_trend.points[0].period

    # Now add data spanning 5 years (20 quarters, > 16 quarters -> annual)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    more_records = []
    for year in [2020, 2021]:
        for month in range(1, 13):
            more_records.append((f"{year}-{month:02d}-15", -200.0, "DESC", "VendorB", "Cat", "csv"))
    cursor.executemany("""
        INSERT INTO transactions (transaction_date, amount, raw_description, vendor, category, source_format)
        VALUES (?, ?, ?, ?, ?, ?)
    """, more_records)
    conn.commit()
    conn.close()

    annual_trend = dal.get_median_spend_trend()
    assert annual_trend.granularity == "year"
    assert len(annual_trend.points) == 5  # 2020, 2021, 2023, 2024, 2025 (5 active years)
    assert {p.period for p in annual_trend.points} == {"2020", "2021", "2023", "2024", "2025"}