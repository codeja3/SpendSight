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
    def fake_get_vendor_directory(search=None, **kwargs):
        if not search:
            return all_vendors
        return [v for v in all_vendors if search.lower() in v.name.lower()]

    mock_dal.get_vendor_directory.side_effect = fake_get_vendor_directory

    app = SpendSightApp(dal=mock_dal)

    async with app.run_test() as pilot:
        search_input = app.query_one("#vendor-search-input", Input)
        vendor_table = app.query_one("#vendor-directory-table", DataTable)
        
        # Verify column ordering: "Total Spend" must precede "Txns" to ensure visibility in 1/3 pane
        col_labels = [col.label.plain for col in vendor_table.columns.values()]
        assert col_labels == ["Vendor", "Total Spend", "Txns", "Category", "Last Date"]

        # Verify initial row count and proper negative currency formatting (-$150.00, not $-150.00)
        assert vendor_table.row_count == 2
        first_row = vendor_table.get_row_at(0)
        assert first_row[0] == "Amazon"
        assert first_row[1] == "-$150.00"
        assert first_row[2] == "3"
        assert first_row[3] == "Shopping"
        assert first_row[4] == "2026-04-11"

        # Simulate typing into the search box
        search_input.value = "coffee"
        await pilot.pause()

        assert vendor_table.row_count == 1
        filtered_row = vendor_table.get_row_at(0)
        assert filtered_row[0] == "Coffee Shop"
        assert filtered_row[1] == "-$60.00"


@pytest.mark.asyncio
async def test_ledger_income_toggle():
    mock_dal = Mock(spec=SpendSightDAL)
    all_txns = [
        LedgerRow(date="2026-04-14", vendor="Employer", category="Income", amount=5000.0),
        LedgerRow(date="2026-04-13", vendor="Landlord", category="Housing", amount=-2000.0),
    ]
    expenses_only_txns = [
        LedgerRow(date="2026-04-13", vendor="Landlord", category="Housing", amount=-2000.0),
    ]

    def fake_get_ledger(limit=None, offset=0, expenses_only=False):
        return expenses_only_txns if expenses_only else all_txns

    mock_dal.get_ledger.side_effect = fake_get_ledger
    mock_dal.get_top_vendors.return_value = []
    mock_dal.get_bottom_vendors.return_value = []
    mock_dal.get_top_categories.return_value = []
    mock_dal.get_top_vendors_by_category.return_value = []
    mock_dal.get_vendor_directory.return_value = []

    app = SpendSightApp(dal=mock_dal)

    async with app.run_test() as pilot:
        toggle = app.query_one("#ledger-income-toggle")
        ledger_table = app.query_one("#ledger-pane", DataTable)

        # Initial state: toggle is not active (all transactions loaded)
        assert ledger_table.row_count == 2
        row0 = ledger_table.get_row_at(0)
        assert row0[1] == "Employer"

        # Toggle to expenses only
        if hasattr(toggle, "value"):
            toggle.value = True
        else:
            await pilot.click("#ledger-income-toggle")
        await pilot.pause()

        assert ledger_table.row_count == 1
        row0 = ledger_table.get_row_at(0)
        assert row0[1] == "Landlord"


@pytest.mark.asyncio
async def test_vendor_income_toggle():
    mock_dal = Mock(spec=SpendSightDAL)
    mock_dal.get_ledger.return_value = []
    mock_dal.get_top_vendors.return_value = []
    mock_dal.get_bottom_vendors.return_value = []
    mock_dal.get_top_categories.return_value = []
    mock_dal.get_top_vendors_by_category.return_value = []

    all_directory = [
        VendorDirectoryRow(name="Amazon", transaction_count=3, total_spend=-150.0, primary_category="Shopping", last_active_date="2026-04-11"),
        VendorDirectoryRow(name="Employer", transaction_count=1, total_spend=5000.0, primary_category="Income", last_active_date="2026-04-14"),
    ]
    expenses_only_directory = [
        VendorDirectoryRow(name="Amazon", transaction_count=3, total_spend=-150.0, primary_category="Shopping", last_active_date="2026-04-11"),
    ]

    def fake_get_vendor_directory(search=None, expenses_only=False):
        data = expenses_only_directory if expenses_only else all_directory
        if search:
            return [v for v in data if search.lower() in v.name.lower()]
        return data

    mock_dal.get_vendor_directory.side_effect = fake_get_vendor_directory

    app = SpendSightApp(dal=mock_dal)

    async with app.run_test() as pilot:
        tabs = app.query_one(TabbedContent)
        tabs.active = "tab-all-vendors"
        await pilot.pause()

        toggle = app.query_one("#vendor-income-toggle")
        vendor_table = app.query_one("#vendor-directory-table", DataTable)

        # Initial state: toggle is default ("Expenses Only", vendor_expenses_only=False)
        assert vendor_table.row_count == 2
        row0 = vendor_table.get_row_at(0)
        assert row0[0] == "Amazon"
        row1 = vendor_table.get_row_at(1)
        assert row1[0] == "Employer"

        # Click the toggle button to switch to Expenses Only
        await pilot.click("#vendor-income-toggle")
        await pilot.pause()

        assert vendor_table.row_count == 1
        row0 = vendor_table.get_row_at(0)
        assert row0[0] == "Amazon"
        assert toggle.label.plain == "Show All"