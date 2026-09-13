"""Post-ingestion vendor canonicalization (SPEC.md 6.5).

Bank statements from different sources do not guarantee a stable spelling for the
same vendor, so semantically identical vendors such as "TMOBILE" and "T-Mobile"
(or "Quickpark" and "Quick Park") can land as distinct vendors and fragment
spending. This module reconciles them by a lossless rename: it computes a
deterministic canonical key for each vendor, groups spellings that share a key,
picks a single canonical representative per group, and renames every affected
row's vendor. No row is inserted or deleted and no per-row amount, date, or
raw_description is mutated, so consolidated spending per vendor is obtained by
summing the signed amounts in the analytics layer (negative expenditures sum into
a larger net expense; positive deposits net against it). The vendor_cache is
reconciled so future normalizations resolve to the canonical name, and the
operation is idempotent: once every spelling equals its representative, a further
run makes no changes.
"""

import re
import sqlite3

_NON_ALNUM = re.compile(r"[^a-z0-9]")


def canonical_key(vendor: str) -> str:
    """Return the deterministic comparison key for a vendor spelling."""
    return _NON_ALNUM.sub("", vendor.lower())


def _representative(spellings: set[str], counts: dict[str, int]) -> str:
    """Pick the canonical spelling for one equivalence class.

    Most frequent wins; ties break to the lexicographically smallest spelling.
    """
    return min(spellings, key=lambda name: (-counts[name], name))


def _group_by_key(conn: sqlite3.Connection) -> dict[str, set[str]]:
    """Return {canonical_representative: set(all spellings in the class)}."""
    cursor = conn.execute(
        "SELECT vendor, COUNT(*) AS n FROM transactions WHERE vendor IS NOT NULL GROUP BY vendor"
    )
    counts = {vendor: n for vendor, n in cursor.fetchall()}

    classes: dict[str, set[str]] = {}
    for vendor in counts:
        classes.setdefault(canonical_key(vendor), set()).add(vendor)

    representative_by_key = {
        key: _representative(spellings, counts) for key, spellings in classes.items()
    }

    merged: dict[str, set[str]] = {}
    for key, spellings in classes.items():
        merged[representative_by_key[key]] = spellings
    return merged


def mappings_for(conn: sqlite3.Connection) -> dict[str, str]:
    """Compute renames {old: canonical} for every non-self representative.

    A spelling that is already its own representative is excluded, so a database
    in canonical form yields an empty mapping -- the basis for idempotency.
    """
    mappings: dict[str, str] = {}
    for representative, spellings in _group_by_key(conn).items():
        for spelling in spellings:
            if spelling != representative:
                mappings[spelling] = representative
    return mappings


def compute_canonical_mappings(db_path: str) -> dict[str, str]:
    """Return {old_vendor: canonical_name} for the database at db_path.

    Pure read; no mutation. Database errors propagate.
    """
    with sqlite3.connect(db_path) as conn:
        return mappings_for(conn)


def apply_canonicalization(db_path: str) -> dict[str, str]:
    """Merge typographically duplicate vendors by rename and return the mapping.

    Within one transaction this renames transactions.vendor for every affected
    row and rewrites any vendor_cache row whose vendor is a non-canonical
    spelling so the cache stays consistent. Returns {old: canonical}; empty
    when there is nothing to merge. Database or connection errors propagate
    to the caller (the CLI maps these to a non-zero exit code).
    """
    with sqlite3.connect(db_path) as conn:
        mappings = mappings_for(conn)
        if not mappings:
            return {}

        # Detect vendor_cache once, outside the rename loop.
        has_cache = bool(
            conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'vendor_cache' LIMIT 1"
            ).fetchone()
        )

        for old, canonical in mappings.items():
            conn.execute(
                "UPDATE transactions SET vendor = ? WHERE vendor = ?",
                (canonical, old),
            )
            if has_cache:
                conn.execute(
                    "UPDATE vendor_cache SET vendor = ? WHERE vendor = ?",
                    (canonical, old),
                )
        conn.commit()
        return mappings


def _print_summary(before: int, after: int, mappings: dict[str, str]) -> None:
    lines = [
        "Vendor canonicalization:",
        f"  vendors before: {before}",
        f"  vendors after:   {after}",
        f"  renames:         {len(mappings)}",
    ]
    if mappings:
        lines.append("  name changes:")
        for old, canonical in sorted(mappings.items(), key=lambda kv: kv[1]):
            lines.append(f"      {old!r} -> {canonical!r}")
    else:
        lines.append("  no vendors needed canonicalization")
    print("\n".join(lines))


def main() -> None:
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Consolidate typographically duplicate vendors in the ledger."
    )
    sub = parser.add_subparsers(dest="command", required=True)
    canonical = sub.add_parser("canonicalize", help="Merge duplicate vendors and print a summary.")
    canonical.add_argument("--input", required=True, help="Path to the spendsight SQLite database.")
    args = parser.parse_args()

    if args.command == "canonicalize":
        try:
            mappings = apply_canonicalization(args.input)
        except sqlite3.Error as err:
            print(f"Canonicalization error: {err}", file=sys.stderr)
            sys.exit(1)

        with sqlite3.connect(args.input) as conn:
            before = conn.execute(
                "SELECT COUNT(DISTINCT vendor) FROM transactions WHERE vendor IS NOT NULL"
            ).fetchone()[0]
            after = before - len(mappings)
        _print_summary(before, after, mappings)
        sys.exit(0)


if __name__ == "__main__":
    main()
