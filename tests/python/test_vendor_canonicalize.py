"""Tests for post-ingestion vendor canonicalization (SPEC.md 6.5).

Covers:
  * canonical_key equivalence (case-insensitive, strips non-alphanumerics)
  * canonical representative selection (most-frequent wins, lex tie-break)
  * single-spelling classes are left untouched
  * amounts are consolidated by rename, not row-merge (net by sign)
  * vendor_cache invalidation
  * idempotency (a second run is a no-op)
  * CLI exit codes for valid, empty, and corrupt databases
"""

import os
import sqlite3
import subprocess
import tempfile

import pytest

# -- helpers -----------------------------------------------------------------
TXN_SCHEMA = """
    CREATE TABLE transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        transaction_date TEXT NOT NULL,
        amount REAL NOT NULL,
        raw_description TEXT NOT NULL,
        vendor TEXT NOT NULL,
        category TEXT NOT NULL,
        source_format TEXT NOT NULL,
        ingested_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
"""

CACHE_SCHEMA = """
    CREATE TABLE vendor_cache (
        raw_description TEXT PRIMARY KEY,
        vendor TEXT NOT NULL,
        category TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
"""


def make_db(rows, cache_rows=None):
    """Create a temp SQLite DB seeded with transactions and a vendor_cache.

    rows:       list of (date, amount, raw_description, vendor, category)
    cache_rows: list of (raw_description, vendor, category) or None
    """
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = sqlite3.connect(path)
    c = conn.cursor()
    c.execute(TXN_SCHEMA)
    c.executemany(
        "INSERT INTO transactions "
        "(transaction_date, amount, raw_description, vendor, category, source_format) "
        "VALUES (?, ?, ?, ?, ?, 'csv')",
        rows,
    )
    c.execute(CACHE_SCHEMA)
    if cache_rows:
        c.executemany(
            "INSERT OR REPLACE INTO vendor_cache (raw_description, vendor, category) "
            "VALUES (?, ?, ?)",
            cache_rows,
        )
    conn.commit()
    conn.close()
    return path


def distinct_vendors(path):
    with sqlite3.connect(path) as conn:
        return {row[0] for row in conn.execute("SELECT DISTINCT vendor FROM transactions")}


def sum_by_vendor(path):
    with sqlite3.connect(path) as conn:
        rows = conn.execute("SELECT vendor, SUM(amount) FROM transactions GROUP BY vendor")
        return {row[0]: row[1] for row in rows}


def cleanup(path):
    if os.path.exists(path):
        os.unlink(path)


# -- canonical_key: pure equivalence function --------------------------------
def test_canonical_key_case_and_punctuation_insensitive():
    from src.python.vendor_canonicalize import canonical_key

    assert canonical_key("T-Mobile") == canonical_key("TMOBILE")
    assert canonical_key("T-Mobile") == canonical_key("T-MOBILE.")
    assert canonical_key("Quick Park.") == canonical_key("Quickpark")
    assert canonical_key("*LOCAL COFFEE*") == canonical_key("Local Coffee")


def test_canonical_key_is_lowercased():
    from src.python.vendor_canonicalize import canonical_key

    assert canonical_key("HELLO") == "hello"
    # A raw description's asterisks/stars are stripped, matching its clean vendor.
    assert canonical_key("* T-MOBILE *") == "tmobile"


def test_distinct_letters_are_not_merged():
    from src.python.vendor_canonicalize import canonical_key

    # The key must not collapse distinct letters, so "ab" and "aa" differ.
    assert canonical_key("ab") != canonical_key("aa")
    assert canonical_key("abc") != canonical_key("abd")


def test_canonical_key_generalized_rules():
    from src.python.vendor_canonicalize import canonical_key

    # 1. Leading articles stripped
    assert canonical_key("The Home Depot") == canonical_key("Home Depot")
    assert canonical_key("A Local Bakery") == canonical_key("Local Bakery")

    # 2. Web domains stripped
    assert canonical_key("Zappos.com") == canonical_key("Zappos")
    assert canonical_key("Amazon.com") == canonical_key("Amazon")
    assert canonical_key("JW.ORG") == canonical_key("JW")

    # 3. Corporate suffixes stripped
    assert canonical_key("Kinetico Incorporated") == canonical_key("Kinetico")
    assert canonical_key("Landsend Inc.") == canonical_key("Landsend")
    assert canonical_key("Acme LLC") == canonical_key("Acme")
    assert canonical_key("Global Corp") == canonical_key("Global")

    # 4. Retail store/channel qualifiers stripped
    assert canonical_key("Meijer Store") == canonical_key("Meijer")
    assert canonical_key("Costco Wholesale") == canonical_key("Costco")


# -- group selection: most-frequent wins, lexicographic tie-break ------------
def test_most_frequent_wins_as_canonical():
    from src.python.vendor_canonicalize import compute_canonical_mappings

    path = make_db(
        [
            ("2024-01-05", -89.90, "TMobile Bill Pay", "TMOBILE", "Utilities"),
            ("2024-01-12", -45.00, "T-Mobile Payment", "TMOBILE", "Utilities"),
            ("2024-02-05", -62.50, "T-MOBILE STORE", "TMOBILE", "Utilities"),
            ("2024-02-15", +89.90, "TMobile Refund", "T-Mobile", "Utilities"),
        ]
    )
    try:
        mappings = compute_canonical_mappings(path)
        # TMOBILE (freq 3) is the representative; T-Mobile (freq 1) is renamed to it.
        assert mappings.get("T-Mobile") == "TMOBILE"
        # A spelling that is already its own representative is not in the mapping.
        assert "TMOBILE" not in mappings
    finally:
        cleanup(path)


def test_tie_break_uses_lexicographically_smallest():
    from src.python.vendor_canonicalize import compute_canonical_mappings

    # Same key ("tmobile"), each spelling once -> lexicographically smallest wins.
    path = make_db(
        [
            ("2024-01-01", -10.0, "AAAA", "TMOBILE", "Utilities"),
            ("2024-02-01", -20.0, "BBBB", "T-Mobile", "Utilities"),
        ]
    )
    try:
        mappings = compute_canonical_mappings(path)
        assert mappings.get("TMOBILE") == "T-Mobile", f"got {mappings}"
        assert "T-Mobile" not in mappings
    finally:
        cleanup(path)


def test_single_spelling_class_is_left_untouched():
    from src.python.vendor_canonicalize import compute_canonical_mappings

    path = make_db(
        [
            ("2024-01-15", -15.00, "WholeFoods Market", "WholeFoods", "Groceries"),
            ("2024-03-01", -80.00, "Target Super", "Target", "Shopping"),
        ]
    )
    try:
        mappings = compute_canonical_mappings(path)
        assert "WholeFoods" not in mappings or mappings["WholeFoods"] == "WholeFoods"
        assert "Target" not in mappings or mappings["Target"] == "Target"
    finally:
        cleanup(path)


# -- amount consolidation is by rename, not by row-merge ---------------------
def test_mixed_sign_rows_net_by_aggregation_not_row_merge():
    from src.python.vendor_canonicalize import apply_canonicalization

    # Four T-Mobile spellings (all key to "tmobile"): three expenditures and one
    # deposit that nets *against* them.
    # Net = -89.90 - 45.00 - 62.50 + 90.00 = -107.40 (the deposit "subtracts").
    path = make_db(
        [
            ("2024-01-05", -89.90, "TMobile Bill Pay", "TMOBILE", "Utilities"),
            ("2024-01-12", -45.00, "T-Mobile Payment", "T-Mobile", "Utilities"),
            ("2024-02-05", -62.50, "T-MOBILE Store #12", "T-MOBILE.", "Utilities"),
            ("2024-02-15", +90.00, "TMobile Refund", "Tmobile", "Utilities"),
        ]
    )
    try:
        mappings = apply_canonicalization(path)
        assert len(mappings) > 0

        # All four distinct spellings collapse to one canonical vendor.
        remaining = distinct_vendors(path)
        canonicals = {mappings[k] for k in mappings}
        assert len(remaining & canonicals) == 1, "all spellings should share one canonical vendor"

        # No row-merge: the row count is unchanged and the canonical vendor's summed
        # amount reflects both the expenses and the deposit netted against them.
        with sqlite3.connect(path) as conn:
            row_count = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
        assert row_count == 4, "canonicalization renames rows; it must not delete them"

        sums = sum_by_vendor(path)
        net = next(value for key, value in sums.items() if key in canonicals)
        assert net == pytest.approx(-107.40), f"deposit must net against expenses, got {net}"
        # If the deposit had not netted (treated as an expense) the sum would be
        # -197.40; the smaller magnitude proves the sign was applied.
        assert net != pytest.approx(-197.40)
    finally:
        cleanup(path)


def test_all_deposit_group_sums_to_positive_net():
    from src.python.vendor_canonicalize import apply_canonicalization

    path = make_db(
        [
            ("2024-01-01", +100.00, "ACME Payroll", "ACME Payroll", "Income"),
            ("2024-02-01", +150.00, "Acme-Payroll Inc", "acme payroll", "Income"),
        ]
    )
    try:
        apply_canonicalization(path)
        sums = sum_by_vendor(path)
        assert len(sums) == 1, "both payroll spellings should merge into one vendor"
        net = next(iter(sums.values()))
        assert net == pytest.approx(250.00), "the two deposits should sum"
    finally:
        cleanup(path)


# -- vendor_cache invalidation -----------------------------------------------
def test_vendor_cache_non_canonical_vendors_are_rewritten():
    from src.python.vendor_canonicalize import apply_canonicalization, canonical_key

    # QUICK PARK (freq 1) vs Quickpark (freq 2) -> canonical "Quickpark".
    path = make_db(
        rows=[
            ("2024-01-10", -25.00, "Quick Park Garage", "Quickpark", "Transportation"),
            ("2024-01-20", -30.00, "QPark Express", "Quickpark", "Transportation"),
            ("2024-02-10", -25.00, "Quick Parking Lot", "QUICK PARK", "Transportation"),
        ],
        cache_rows=[
            ("QUICK PARK GARAGE", "QUICK PARK", "Transportation"),
            ("Q PARK EXPRESS", "Quickpark", "Transportation"),
        ],
    )
    try:
        apply_canonicalization(path)
        with sqlite3.connect(path) as conn:
            cache_vendors = {row[0] for row in conn.execute(
                "SELECT DISTINCT vendor FROM vendor_cache")}
        # No cached vendor may still be a non-canonical spelling of a merged group.
        if "quickpark" in {canonical_key(v) for v in cache_vendors}:
            assert "QUICK PARK" not in cache_vendors, "non-canonical cache vendor was not rewritten"
    finally:
        cleanup(path)


# -- idempotency -------------------------------------------------------------
def test_repeated_run_is_a_noop():
    from src.python.vendor_canonicalize import apply_canonicalization

    path = make_db(
        [
            ("2024-01-05", -89.90, "TMobile Bill Pay", "TMOBILE", "Utilities"),
            ("2024-01-12", -45.00, "T-Mobile Payment", "T-Mobile", "Utilities"),
        ]
    )
    try:
        first = apply_canonicalization(path)
        assert len(first) > 0, "first run should rename at least one spelling"
        second = apply_canonicalization(path)
        assert second == {}, f"second run must be empty (idempotent), got {second}"
    finally:
        cleanup(path)


def test_idempotency_via_apply_then_compute():
    from src.python.vendor_canonicalize import apply_canonicalization, compute_canonical_mappings

    path = make_db(
        [
            ("2024-01-05", -89.90, "TMobile Bill Pay", "TMOBILE", "Utilities"),
            ("2024-01-12", -45.00, "T-Mobile Payment", "T-Mobile", "Utilities"),
        ]
    )
    try:
        apply_canonicalization(path)
        # After applying, a fresh compute is empty: the state has advanced.
        assert compute_canonical_mappings(path) == {}
    finally:
        cleanup(path)


# -- CLI exit codes ----------------------------------------------------------
def seed_valid_db(path, empty_transactions=False):
    conn = sqlite3.connect(path)
    conn.execute(TXN_SCHEMA)
    conn.execute(CACHE_SCHEMA)
    if not empty_transactions:
        conn.execute(
            "INSERT INTO transactions "
            "(transaction_date,amount,raw_description,vendor,category,source_format) "
            "VALUES ('2024-01-01',-5.0,'Test','TestVendor','Other','csv')"
        )
    conn.commit()
    conn.close()
    return path


def run_cli(db_path):
    return subprocess.run(
        ["python", "-m", "src.python.vendor_canonicalize", "canonicalize",
         "--input", db_path],
        capture_output=True,
        text=True,
        check=False,
    )


def test_cli_exit_code_on_valid_db(tmp_path):
    path = str(tmp_path / "valid.db")
    seed_valid_db(path, empty_transactions=False)
    result = run_cli(path)
    assert result.returncode == 0, f"stderr={result.stderr}"


def test_cli_exit_code_on_empty_transactions(tmp_path):
    path = str(tmp_path / "empty.db")
    seed_valid_db(path, empty_transactions=True)
    result = run_cli(path)
    assert result.returncode == 0, f"empty transactions should not crash; stderr={result.stderr}"


def test_cli_nonzero_when_transactions_table_missing(tmp_path):
    # A valid SQLite file without the transactions table is not a SpendSight DB.
    path = str(tmp_path / "bogus.db")
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE unrelated (id INTEGER)")
    conn.commit()
    conn.close()
    result = run_cli(path)
    assert result.returncode != 0


def test_cli_nonzero_on_corrupt_db(tmp_path):
    path = tmp_path / "corrupt.db"
    path.write_text("this is not a sqlite database")
    result = run_cli(str(path))
    assert result.returncode != 0
