import pytest
from unittest.mock import patch
from src.python.llm import normalize_vendor, normalize_transactions, TransactionEntity

def test_normalize_vendor_returns_structured_entity():
    # 1. Setup: The raw, messy string from a bank statement
    raw_string = "SQ *LOCAL COFFEE SHOP NEW YORK NY"
    
    # 2. Setup: Mock the ENTIRE client object so the dynamic proxies don't escape
    with patch("src.python.llm.client") as mock_client:
        # Simulate the LLM successfully returning our Pydantic model
        mock_client.chat.completions.create.return_value = TransactionEntity(
            vendor="Local Coffee Shop",
            category="Dining"
        )
        
        # 3. Execute: Call our normalization function
        result = normalize_vendor(raw_string)
        
    # 4. Verify: Check that it returned the exact Pydantic model structure
    assert isinstance(result, TransactionEntity)
    assert result.vendor == "Local Coffee Shop"
    assert result.category == "Dining"


def test_normalize_vendor_prompts_enforce_parent_brand_rule():
    # Verify the system prompt and field instructions instruct Parent Brand normalization
    with patch("src.python.llm.client") as mock_client:
        mock_client.chat.completions.create.return_value = TransactionEntity(
            vendor="Home Depot",
            category="Shopping"
        )
        normalize_vendor("THE HOME DEPOT #1234")
        
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        messages = call_kwargs["messages"]
        system_msg = next(m["content"] for m in messages if m["role"] == "system")
        assert "parent brand" in system_msg.lower()

    # Verify field description in TransactionEntity includes brand guidance
    schema_desc = TransactionEntity.model_fields["vendor"].description or ""
    assert "corporate suffixes" in schema_desc.lower() or "parent brand" in schema_desc.lower()

def test_normalize_transactions_batch():
    # 1. Setup: A batch of messy strings
    raw_strings = [
        "SQ *LOCAL COFFEE SHOP", 
        "UBER *TRIP SAN FRANCISCO CA",
        "AMZN MKTP US*8J24O AMZN.COM/BILL"
    ]
    
    # 2. Setup: Mock the client returning BatchTransactionEntities as defined in SPEC.md
    with patch("src.python.llm.client") as mock_client:
        from src.python.llm import BatchTransactionEntities
        mock_client.chat.completions.create.return_value = BatchTransactionEntities(
            items=[
                TransactionEntity(vendor="Local Coffee Shop", category="Dining"),
                TransactionEntity(vendor="Uber", category="Transportation"),
                TransactionEntity(vendor="Amazon", category="Shopping")
            ]
        )
        
        # 3. Execute: Call the batch normalization function
        results = normalize_transactions(raw_strings, db_path=":memory:")
        
    # 4. Verify: Check that the batch was processed correctly and in order
    assert len(results) == 3
    assert results[0].vendor == "Local Coffee Shop"
    assert results[1].category == "Transportation"
    assert results[2].vendor == "Amazon"
    
    # Verify the LLM was called once via micro-batching instead of 3 individual calls
    assert mock_client.chat.completions.create.call_count == 1


def test_normalize_transactions_with_vendor_cache(tmp_path):
    import sqlite3
    from src.python.llm import BatchTransactionEntities

    db_file = tmp_path / "test_cache.db"
    with sqlite3.connect(str(db_file)) as conn:
        conn.execute("""
            CREATE TABLE vendor_cache (
                raw_description TEXT PRIMARY KEY,
                vendor TEXT NOT NULL,
                category TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Pre-seed cache with one known vendor
        conn.execute(
            "INSERT INTO vendor_cache (raw_description, vendor, category) VALUES (?, ?, ?)",
            ("SQ *LOCAL COFFEE SHOP", "Local Coffee Shop", "Dining")
        )
        conn.commit()

    raw_strings = [
        "SQ *LOCAL COFFEE SHOP",           # Cache HIT
        "UBER *TRIP SAN FRANCISCO CA",     # Cache MISS
        "AMZN MKTP US*8J24O AMZN.COM/BILL" # Cache MISS
    ]

    with patch("src.python.llm.client") as mock_client:
        mock_client.chat.completions.create.return_value = BatchTransactionEntities(
            items=[
                TransactionEntity(vendor="Uber", category="Transportation"),
                TransactionEntity(vendor="Amazon", category="Shopping")
            ]
        )

        results = normalize_transactions(raw_strings, db_path=str(db_file))

    # All 3 items should be resolved and maintain original order
    assert len(results) == 3
    assert results[0].vendor == "Local Coffee Shop"
    assert results[0].category == "Dining"
    assert results[1].vendor == "Uber"
    assert results[1].category == "Transportation"
    assert results[2].vendor == "Amazon"
    assert results[2].category == "Shopping"

    # Only 1 LLM call made for the 2 cache misses via micro-batching
    assert mock_client.chat.completions.create.call_count == 1

    # Verify newly normalized vendors were written into vendor_cache
    with sqlite3.connect(str(db_file)) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT raw_description, vendor, category FROM vendor_cache ORDER BY vendor")
        cached_rows = cursor.fetchall()
        assert len(cached_rows) == 3
        vendors = {row[1] for row in cached_rows}
        assert vendors == {"Amazon", "Local Coffee Shop", "Uber"}


def test_normalize_transactions_custom_model():
    from src.python.llm import BatchTransactionEntities

    raw_strings = ["SQ *LOCAL COFFEE SHOP"]

    with patch("src.python.llm.client") as mock_client:
        mock_client.chat.completions.create.return_value = BatchTransactionEntities(
            items=[TransactionEntity(vendor="Local Coffee Shop", category="Dining")]
        )

        results = normalize_transactions(raw_strings, db_path=":memory:", model="llama3.2:3b")

        assert len(results) == 1
        assert mock_client.chat.completions.create.call_count == 1
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == "llama3.2:3b"