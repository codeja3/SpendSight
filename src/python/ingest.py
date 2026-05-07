import polars as pl
from pathlib import Path
from src.python.config import BankProfile

def ingest_statement(file_path: str, profile: BankProfile) -> pl.DataFrame:
    """
    Ingests a CSV statement, renames columns according to the profile mapping, 
    and enforces the Canonical Sign Standard for amounts.
    """
    path = Path(file_path)
    
    # Defensive Programming: Fail-fast on missing files
    if not path.is_file():
        raise FileNotFoundError(f"Statement file not found: {file_path}")

    # Phase 1 of Task 7: Handling CSVs. (PDF extraction will be added later)
    if path.suffix.lower() != '.csv':
        raise ValueError(f"Unsupported file format: {path.suffix}. Only .csv is currently supported.")

    # 1. Read the CSV, skipping junk rows defined in the YAML profile
    try:
        df = pl.read_csv(path, skip_rows=profile.skip_rows)
    except Exception as e:
        raise ValueError(f"Failed to parse CSV file {file_path}: {e}")

    # 2. Map the raw columns to our standard names and drop the rest
    try:
        mapping_exprs = [
            pl.col(raw_col).alias(std_col) 
            for raw_col, std_col in profile.column_mapping.items()
        ]
        df = df.select(mapping_exprs)
    except Exception as e:
        raise ValueError(f"Column mapping failed. Ensure the CSV headers match the profile. Error: {e}")

    # 3. Enforce the Canonical Sign Standard
    df = df.with_columns(
        (pl.col("amount") * profile.sign_multiplier).alias("amount")
    )

    return df