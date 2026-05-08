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

def test_normalize_transactions_batch():
    # 1. Setup: A batch of messy strings
    raw_strings = [
        "SQ *LOCAL COFFEE SHOP", 
        "UBER *TRIP SAN FRANCISCO CA",
        "AMZN MKTP US*8J24O AMZN.COM/BILL"
    ]
    
    # 2. Setup: Mock the client and use side_effect to return different models in sequence
    with patch("src.python.llm.client") as mock_client:
        mock_client.chat.completions.create.side_effect = [
            TransactionEntity(vendor="Local Coffee Shop", category="Dining"),
            TransactionEntity(vendor="Uber", category="Transportation"),
            TransactionEntity(vendor="Amazon", category="Shopping")
        ]
        
        # 3. Execute: Call the batch normalization function
        results = normalize_transactions(raw_strings)
        
    # 4. Verify: Check that the batch was processed correctly and in order
    assert len(results) == 3
    assert results[0].vendor == "Local Coffee Shop"
    assert results[1].category == "Transportation"
    assert results[2].vendor == "Amazon"
    
    # Verify the LLM was called exactly 3 times
    assert mock_client.chat.completions.create.call_count == 3