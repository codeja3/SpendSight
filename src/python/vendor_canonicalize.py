"""Post-ingestion vendor canonicalization (SPEC.md 6.5).

Bank statements from different sources do not guarantee a stable spelling
for the same vendor, so semantically identical vendors such as "TMOBILE"
and "T-Mobile" (or "Quickpark" and "Quick Park") can land as distinct
vendors and fragment spending. This module reconciles them by a lossless
rename: it computes a deterministic canonical key for each vendor, groups
spellings that share a key, picks the most frequent spelling as the
canonical representative, and renames every affected row. No row is
inserted or deleted and no per-row amount or date is mutated.

Two extension points sit on top of the mechanical key for cases the key
cannot infer on its own. SYNONYMS is a user-maintained {spelling: target}
map of semantic folds. REVIEW_FLAGS is a {vendor: note} map of vendors
that look like a duplicate but must not be auto-merged.
"""

import re
import sqlite3
from pathlib import Path

import yaml

_NON_ALNUM = re.compile(r"[^a-z0-9]")

# Populated from vendor_overrides.yaml at CLI launch.
SYNONYMS: dict[str, str] = {}
REVIEW_FLAGS: dict[str, str] = {
    "Thank You-Mobile": "T-Mobile ACH/payroll processor -- verify category.",
}
DEFAULT_CONFIG = "vendor_overrides.yaml"


def canonical_key(vendor: str) -> str:
    """Return the comparison key for a vendor spelling (lowercase, stripped)."""
    return _NON_ALNUM.sub("", vendor.lower())


def class_key(vendor: str) -> str:
    """Grouping key honouring user-supplied SYNONYMS."""
    if vendor in SYNONYMS:
        return canonical_key(SYNONYMS[vendor])
    return canonical_key(vendor)


def _representative(spellings: set[str], counts: dict[str, int]) -> str:
    """Most-frequent spelling wins; ties break lexicographically."""
    return min(spellings, key=lambda name: (-counts[name], name))


def _group_by_key(conn: sqlite3.Connection) -> dict[str, set[str]]:
    """Return {representative: set(spellings)} using class_key for grouping."""
    cursor = conn.execute(
        "SELECT vendor, COUNT(*) AS n FROM transactions WHERE vendor IS NOT NULL GROUP BY vendor"
    )
    counts = {vendor: n for vendor, n in cursor.fetchall()}
    classes: dict[str, set[str]] = {}
    for vendor in counts:
        classes.setdefault(class_key(vendor), set()).add(vendor)
    representative_by_key = {key: _representative(sp, counts) for key, sp in classes.items()}
    merged: dict[str, set[str]] = {}
    for key, spellings in classes.items():
        merged[representative_by_key[key]] = spellings
    return merged


def mappings_for(conn: sqlite3.Connection) -> dict[str, str]:
    """Return {old: canonical} renames; a self-representative is excluded."""
    mappings: dict[str, str] = {}
    for representative, spellings in _group_by_key(conn).items():
        for spelling in spellings:
            if spelling != representative:
                mappings[spelling] = representative
    return mappings


def compute_canonical_mappings(db_path: str) -> dict[str, str]:
    """Return {old_vendor: canonical_name} for the database (pure read)."""
    with sqlite3.connect(db_path) as conn:
        return mappings_for(conn)


def get_review_flags(conn: sqlite3.Connection) -> dict[str, str]:
    """Return {vendor: note} for REVIEW_FLAGS still present in transactions."""
    present = {row[0] for row in conn.execute("SELECT DISTINCT vendor FROM transactions")}
    return {vendor: note for vendor, note in REVIEW_FLAGS.items() if vendor in present}


def apply_canonicalization(db_path: str) -> dict[str, str]:
    """Merge duplicate vendors by rename and reconcile vendor_cache.

    Within one transaction this renames transactions.vendor for every
    affected row and rewrites any vendor_cache row whose vendor is
    non-canonical. Returns {old: canonical}; empty when nothing to merge.
    """
    with sqlite3.connect(db_path) as conn:
        mappings = mappings_for(conn)
        if not mappings:
            return {}
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


def load_override_config(
    config_path: str | None,
) -> tuple[dict[str, str], dict[str, str]]:
    """Load (SYNONYMS, REVIEW_FLAGS) from a YAML file.

    Schema (both sections optional):
        synonyms:
            "Landsend Inc.": "Lands' End"
        review_flags:
            "Thank You-Mobile": "ACH processor -- verify category."

    A missing file or config_path=None yields ({}, {}).
    """
    if config_path is None:
        return {}, {}

    p = Path(config_path)
    if not p.is_file():
        raise FileNotFoundError(f"Vendor override config not found: {config_path}")
    with open(p, "r", encoding="utf-8") as f:
        try:
            data = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ValueError(f"Failed to parse vendor override YAML: {e}")
    return dict(data.get("synonyms") or {}), dict(data.get("review_flags") or {})


def apply_override_config(config_path: str | None) -> None:
    """Populate module-level SYNONYMS and REVIEW_FLAGS from a YAML config file."""
    synonyms, review_flags = load_override_config(config_path)
    SYNONYMS.clear()
    SYNONYMS.update(synonyms)
    REVIEW_FLAGS.clear()
    REVIEW_FLAGS.update(review_flags)


def _print_summary(
    before: int,
    after: int,
    mappings: dict[str, str],
    conn: sqlite3.Connection,
) -> None:
    lines = [
        "Vendor canonicalization:",
        f"  vendors before: {before}",
        f"  vendors after:      {after}",
        f"  renames:            {len(mappings)}",
    ]
    if mappings:
        lines.append("  name changes:")
        for old, canonical in sorted(mappings.items(), key=lambda kv: kv[1]):
            lines.append(f"        {old!r:28} -> {canonical!r}")
    else:
        lines.append("  no vendors needed canonicalization")
    flags = get_review_flags(conn)
    if flags:
        lines.append("")
        lines.append(f"    {len(flags)} vendor(s) flagged for manual review (NOT merged):")
        for vendor, note in sorted(flags.items()):
            lines.append(f"        {vendor!r:28} -- {note}")
    print("\n".join(lines))


def main() -> None:
    import argparse
    import sys
    from pathlib import Path

    parser = argparse.ArgumentParser(
        description="Consolidate typographically duplicate vendors in the ledger."
    )
    sub = parser.add_subparsers(dest="command", required=True)
    cg = sub.add_parser("canonicalize", help="Merge duplicate vendors and print a summary.")
    cg.add_argument("--input", required=True, help="Path to the spendsight SQLite database.")
    cg.add_argument(
        "--config",
        default=DEFAULT_CONFIG,
        help="YAML file with synonym/review_flag overrides. Skipped when absent.",
    )
    args = parser.parse_args()

    if args.command == "canonicalize":
        if Path(args.config).is_file():
            apply_override_config(args.config)
        else:
            print(f"Note: override config not found: {args.config} (using no overrides)")
        try:
            mappings = apply_canonicalization(args.input)
        except (sqlite3.Error, FileNotFoundError, ValueError) as err:
            print(f"Canonicalization error: {err}", file=sys.stderr)
            sys.exit(1)
        conn = sqlite3.connect(args.input)
        # after counts distinct vendors now in the DB; before adds back
        # the removed "old" keys. Correct even when nothing was merged.
        after = conn.execute(
            "SELECT COUNT(DISTINCT vendor) FROM transactions WHERE vendor IS NOT NULL",
        ).fetchone()[0]
        before = after + len(mappings)
        _print_summary(before, after, mappings, conn)
        conn.close()
        sys.exit(0)


if __name__ == "__main__":
    main()
