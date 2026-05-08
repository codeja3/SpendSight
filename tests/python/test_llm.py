import pytest
from unittest.mock import patch
from src.python.llm import normalize_vendor, TransactionEntity

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