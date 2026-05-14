import polars as pl
import pdfplumber
from pathlib import Path
from src.python.config import BankProfile

def ingest_statement(file_path: str, profile: BankProfile) -> pl.DataFrame:
    """
    Ingests a CSV or PDF statement, renames columns according to the profile mapping, 
    and enforces the Canonical Sign Standard for amounts.
    """
    path = Path(file_path)
    
    # Defensive Programming: Fail-fast on missing files
    if not path.is_file():
        raise FileNotFoundError(f"Statement file not found: {file_path}")

    # 1. Parse Data Based on File Type
    if path.suffix.lower() == '.csv':
        try:
            df = pl.read_csv(path, skip_rows=profile.skip_rows, truncate_ragged_lines=True)
        except Exception as e:
            raise ValueError(f"Failed to parse CSV file {file_path}: {e}")
            
    elif path.suffix.lower() == '.pdf':
        try:
            all_rows = []
            with pdfplumber.open(path) as pdf:
                for page in pdf.pages:
                    table = page.extract_table()
                    if table:
                        all_rows.extend(table)
            
            if not all_rows:
                raise ValueError(f"No tabular data could be extracted from PDF: {file_path}")
            
            # Apply skip_rows. The row immediately after the skipped rows is our header.
            headers = all_rows[profile.skip_rows]
            data_rows = all_rows[profile.skip_rows + 1:]
            
            # Convert the 2D string array into a Polars DataFrame
            df = pl.DataFrame(data_rows, schema=headers, orient="row")
        except Exception as e:
            raise ValueError(f"Failed to parse PDF file {file_path}: {e}")
            
    else:
        raise ValueError(f"Unsupported file format: {path.suffix}. Only .csv and .pdf are supported.")

    # 2. Map the raw columns to our standard names and drop the rest
    try:
        mapping_exprs = [
            pl.col(raw_col).alias(std_col) 
            for raw_col, std_col in profile.column_mapping.items()
        ]
        df = df.select(mapping_exprs)
    except Exception as e:
        raise ValueError(f"Column mapping failed. Ensure headers match the profile. Error: {e}")

    # 3. Enforce the Canonical Sign Standard and Date Normalization
    # Check for split columns (Debit/Credit) vs single Amount column
    if "debit" in df.columns and "credit" in df.columns:
        # Synthesis logic for split columns: amount = Credit - Debit
        # We must clean both columns first (handle commas, nulls, and empty strings)
        df = df.with_columns([
            pl.col("debit").cast(pl.String).str.replace_all(",", "").fill_null("0").alias("debit"),
            pl.col("credit").cast(pl.String).str.replace_all(",", "").fill_null("0").alias("credit")
        ])
        
        # Convert empty strings to "0" and cast to float
        df = df.with_columns([
            pl.when(pl.col("debit") == "").then(pl.lit("0")).otherwise(pl.col("debit")).cast(pl.Float64).alias("debit"),
            pl.when(pl.col("credit") == "").then(pl.lit("0")).otherwise(pl.col("credit")).cast(pl.Float64).alias("credit")
        ])
        
        # Calculate canonical amount: Deposits (+) - Expenditures (-)
        df = df.with_columns([
            (pl.col("credit") - pl.col("debit")).alias("amount")
        ])
    
    # Finalize the 'amount' column (apply sign multiplier and ensure Float64)
    # This handles both synthesized amounts and directly mapped amounts.
    df = df.with_columns([
        (pl.col("amount")
         .cast(pl.String)
         .str.replace_all(",", "")
         .fill_null("0")
         .replace("", "0") # Handle empty strings
         .cast(pl.Float64) * profile.sign_multiplier).alias("amount"),

        # Normalize Date: Parse based on profile format and cast to string (ISO)
        (pl.col("date")
         .str.to_date(format=profile.date_format)
         .cast(pl.String) # Convert back to ISO string YYYY-MM-DD for JSON/SQLite
        ).alias("date")
    ])

    return df