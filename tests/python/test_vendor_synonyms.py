"""Tests for semantic vendor synonym folds and manual-review flags (SPEC 6.5.7)."""

import os
import sqlite3
import tempfile

import src.python.vendor_canonicalize as vc
from src.python.vendor_canonicalize import (
    apply_canonicalization,
    compute_canonical_mappings,
    get_review_flags,
)

__TXN__ = """
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

__CACHE__ = """
CREATE TABLE vendor_cache (
    raw_description TEXT PRIMARY KEY,
    vendor TEXT NOT NULL,
    category TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""


def make_db(rows, cache_rows=None):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = sqlite3.connect(path)
    c = conn.cursor()
    c.execute(__TXN__)
    c.executemany(
        "INSERT INTO transactions (transaction_date,amount,raw_description,vendor,category,source_format) VALUES (?,?,?,?,?,'csv')",
        rows,
    )
    c.execute(__CACHE__)
    if cache_rows:
        c.executemany(
            "INSERT OR REPLACE INTO vendor_cache (raw_description,vendor,category) VALUES (?,?,?)",
            cache_rows,
        )
    conn.commit()
    conn.close()
    return path


def distinct_vendors(path):
    with sqlite3.connect(path) as conn:
        return {row[0] for row in conn.execute("SELECT DISTINCT vendor FROM transactions")}


def cleanup(path):
    if os.path.exists(path):
        os.unlink(path)


# -- synonym extension --


def test_landsend_distinct_from_lands_end_by_default():
    # Landsend Inc. (key landsendinc) and Lands' End (key landsend) must NOT
    # merge under the default module configuration without a SYNONYMS entry.
    path = make_db(
        [
            ("2024-01-10", -92.16, "Lands End Store", "Lands' End", "Shopping"),
            ("2024-02-15", -130.68, "Landsend Inc.", "Landsend Inc.", "Shopping"),
            ("2024-03-05", -100.00, "Lends End Online", "Landsend Inc.", "Shopping"),
        ]
    )
    try:
        raw = compute_canonical_mappings(path)
        assert "Landsend Inc." not in raw, f"unexpected default merge: {raw}"
    finally:
        cleanup(path)


def test_synonym_fold_applied_when_configured():
    # With a SYNONYM configured, Landsend Inc. is folded into the Lands' End class.
    path = make_db(
        [
            ("2024-01-10", -92.16, "Lands End Store", "Lands' End", "Shopping"),
            ("2024-02-15", -130.68, "Landsend Inc.", "Landsend Inc.", "Shopping"),
            ("2024-03-05", -100.00, "Lends End Online", "Landsend Inc.", "Shopping"),
        ]
    )
    saved = dict(vc.SYNONYMS)
    vc.SYNONYMS.update({"Landsend Inc.": "Lands' End"})
    try:
        mappings = apply_canonicalization(path)
         # The fold joins the two spellings into one equivalence class.
         # The most-frequent spelling wins as representative; either name is OK,
         # so assert the class collapsed to exactly one distinct vendor.
        remaining = distinct_vendors(path)
        assert len(remaining) == 1, f"expected 1 consolidated vendor, got {remaining}"
        conn = sqlite3.connect(path)
        canon = next(iter(remaining))
        net = conn.execute("SELECT ROUND(SUM(amount),2) FROM transactions WHERE vendor=?", (canon,)).fetchone()[0]
        conn.close()
         # The class nets all three rows: -92.16 - 130.68 - 100.00 = -322.84.
        assert abs(net - (-322.84)) < 0.01, f"expected net -322.84, got {net}"
         # Idempotency: second run must be a no-op.
        assert apply_canonicalization(path) == {}, "2nd run not empty"
        assert len(mappings) >= 1, "expected at least one rename"
    finally:
        vc.SYNONYMS.clear()
        vc.SYNONYMS.update(saved)
        cleanup(path)


def test_synonym_idempotent_after_apply():
    # Once renamed, the synonym is no longer effective; 2nd run must return empty.
    path = make_db(
        [
            ("2024-01-10", -92.16, "Lands End Store", "Lands' End", "Shopping"),
            ("2024-02-15", -130.68, "Landsend Inc.", "Landsend Inc.", "Shopping"),
        ]
    )
    saved = dict(vc.SYNONYMS)
    vc.SYNONYMS.update({"Landsend Inc.": "Lands' End"})
    try:
        apply_canonicalization(path)
        vc.SYNONYMS.clear()
        assert compute_canonical_mappings(path) == {}
    finally:
        vc.SYNONYMS.update(saved)
        cleanup(path)


# -- review flags --


def test_thank_you_mobile_is_never_merged():
    # Thank You-Mobile has key 'thankyoumobile' distinct from 'tmobile';
    # REVIEW_FLAGS also blocks it; it must survive canonicalization.
    path = make_db(
        [
            ("2024-01-05", +1000.00, "ACH", "Thank You-Mobile", "Income"),
            ("2024-02-05", +500.00, "ACH", "T-Mobile", "Income"),
        ]
    )
    try:
        mappings = compute_canonical_mappings(path)
        assert all("thank" not in k.lower() for k in mappings), f"merged review-flag: {mappings}"
        apply_canonicalization(path)
        assert "Thank You-Mobile" in distinct_vendors(path)
    finally:
        cleanup(path)


def test_review_flags_are_surfaceable_for_cli_printing():
    # get_review_flags returns flagged vendors still present in the transactions
    # table, enabling CLI-level 'manual review' reporting.
    path = make_db(
        [
            ("2024-01-05", +1000.00, "ACH", "Thank You-Mobile", "Income"),
            ("2024-02-05", +500.00, "ACH", "T-Mobile", "Income"),
        ]
    )
    saved = dict(vc.REVIEW_FLAGS)
    vc.REVIEW_FLAGS.update({"Thank You-Mobile": "ACH processor -- verify category."})
    try:
        conn = sqlite3.connect(path)
        flags = get_review_flags(conn)
        conn.close()
        assert "Thank You-Mobile" in flags
        assert "ACH" in flags["Thank You-Mobile"]
    finally:
        vc.REVIEW_FLAGS.clear()
        vc.REVIEW_FLAGS.update(saved)
        cleanup(path)
