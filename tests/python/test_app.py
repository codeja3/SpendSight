import pytest
from unittest.mock import Mock
from textual.widgets import DataTable, TabbedContent
from src.python.app import SpendSightApp
from src.python.dal import SpendSightDAL, LedgerRow

@pytest.mark.asyncio
async def test_app_mounts_and_loads_layout():
    # 1. Setup: Mock the DAL so we don't need a real SQLite database for UI tests
    mock_dal = Mock(spec=SpendSightDAL)
    mock_dal.get_ledger.return_value = [
        LedgerRow(date="2026-04-12", vendor="Coffee Shop", category="Dining", amount=-5.50)
    ]

    # Inject the mocked DAL into our App
    app = SpendSightApp(dal=mock_dal)
    
    # 2. Execute & Verify: Run the app in headless test mode
    async with app.run_test() as pilot:
        # The app should have mounted successfully
        assert app.is_running
        
        # 3. Verify Layout: Check that our SPEC.md components are present
        # This will raise a NoMatches error in our Red state
        table = app.query_one(DataTable)
        assert table is not None
        
        tabs = app.query_one(TabbedContent)
        assert tabs is not None