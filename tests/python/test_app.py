from unittest.mock import Mock

import pytest
from textual.widgets import DataTable, Input, TabbedContent

from src.python.app import SpendSightApp
from src.python.dal import AggregateRow, LedgerRow, SpendSightDAL, VendorDirectoryRow


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
    mock_dal.get_vendor_directory.return_value = []

    app = SpendSightApp(dal=mock_dal)
    
    # 2. Execute & Verify
    async with app.run_test():
        assert app.is_running
        
        # Verify the main layout pieces exist
        table = app.query_one("#ledger-pane", DataTable)
        assert table is not None
        
        tabs = app.query_one(TabbedContent)
        assert tabs is not None


@pytest.mark.asyncio
async def test_vendor_directory_tab_mounts_and_loads_rows():
    mock_dal = Mock(spec=SpendSightDAL)
    mock_dal.get_ledger.return_value = []
    mock_dal.get_top_vendors.return_value = []
    mock_dal.get_bottom_vendors.return_value = []
    mock_dal.get_top_categories.return_value = []
    mock_dal.get_top_vendors_by_category.return_value = []
    mock_dal.get_vendor_directory.return_value = [
        VendorDirectoryRow(name="Amazon", transaction_count=3, total_spend=-150.0, primary_category="Shopping", last_active_date="2026-04-11"),
        VendorDirectoryRow(name="Coffee Shop", transaction_count=2, total_spend=-60.0, primary_category="Dining", last_active_date="2026-04-12"),
    ]

    app = SpendSightApp(dal=mock_dal)

    async with app.run_test():
        assert app.is_running

        # Verify Search Input & Table exist
        search_input = app.query_one("#vendor-search-input", Input)
        assert search_input is not None
        assert search_input.placeholder == "Search vendors..."

        vendor_table = app.query_one("#vendor-directory-table", DataTable)
        assert vendor_table is not None
        assert vendor_table.row_count == 2


@pytest.mark.asyncio
async def test_vendor_directory_search_filters_rows():
    mock_dal = Mock(spec=SpendSightDAL)
    mock_dal.get_ledger.return_value = []
    mock_dal.get_top_vendors.return_value = []
    mock_dal.get_bottom_vendors.return_value = []
    mock_dal.get_top_categories.return_value = []
    mock_dal.get_top_vendors_by_category.return_value = []
    
    all_vendors = [
        VendorDirectoryRow(name="Amazon", transaction_count=3, total_spend=-150.0, primary_category="Shopping", last_active_date="2026-04-11"),
        VendorDirectoryRow(name="Coffee Shop", transaction_count=2, total_spend=-60.0, primary_category="Dining", last_active_date="2026-04-12"),
    ]
    def fake_get_vendor_directory(search=None):
        if not search:
            return all_vendors
        return [v for v in all_vendors if search.lower() in v.name.lower()]

    mock_dal.get_vendor_directory.side_effect = fake_get_vendor_directory

    app = SpendSightApp(dal=mock_dal)

    async with app.run_test() as pilot:
        search_input = app.query_one("#vendor-search-input", Input)
        vendor_table = app.query_one("#vendor-directory-table", DataTable)
        assert vendor_table.row_count == 2

        # Simulate typing into the search box
        search_input.value = "coffee"
        await pilot.pause()

        assert vendor_table.row_count == 1