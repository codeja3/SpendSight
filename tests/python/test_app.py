import pytest
from unittest.mock import Mock
from textual.widgets import DataTable, TabbedContent
from src.python.app import SpendSightApp
from src.python.dal import SpendSightDAL, LedgerRow, AggregateRow

@pytest.mark.asyncio
async def test_app_mounts_and_loads_layout():
    # 1. Setup: Mock the ENTIRE DAL so all on_mount calls succeed
    mock_dal = Mock(spec=SpendSightDAL)
    mock_dal.get_ledger.return_value = [
        LedgerRow(date="2026-04-12", vendor="Coffee Shop", category="Dining", amount=-5.50)
    ]
    mock_dal.get_top_vendors.return_value = [AggregateRow(name="Landlord", total_spend=-2000.0)]
    mock_dal.get_bottom_vendors.return_value = [AggregateRow(name="Coffee Shop", total_spend=-5.50)]
    mock_dal.get_top_categories.return_value = [AggregateRow(name="Dining", total_spend=-5.50)]
    mock_dal.get_top_vendors_by_category.return_value = [AggregateRow(name="Coffee Shop", total_spend=-5.50)]

    app = SpendSightApp(dal=mock_dal)
    
    # 2. Execute & Verify
    async with app.run_test() as pilot:
        assert app.is_running
        
        # Verify the main layout pieces exist
        table = app.query_one("#ledger-pane", DataTable)
        assert table is not None
        
        tabs = app.query_one(TabbedContent)
        assert tabs is not None