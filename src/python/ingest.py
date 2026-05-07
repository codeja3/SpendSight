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
            df = pl.read_csv(path, skip_rows=profile.skip_rows)
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

    # 3. Enforce the Canonical Sign Standard
    # PDFs return amounts as strings ("1,500.00"). CSVs often return floats.
    # We cast to String to safely strip commas, then cast to Float64 before multiplying.
    df = df.with_columns(
        (pl.col("amount")
         .cast(pl.String)
         .str.replace_all(",", "")
         .cast(pl.Float64) * profile.sign_multiplier).alias("amount")
    )

    return df