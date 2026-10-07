from unittest.mock import Mock

import pytest

from src.python.dal import (
    AggregateRow,
    ExecutiveKPIs,
    LedgerRow,
    MedianSpendPoint,
    MedianSpendTrend,
    SpendSightDAL,
    VendorDirectoryRow,
)
from src.python.gui import build_gui


@pytest.fixture
def mock_dal() -> Mock:
    dal = Mock(spec=SpendSightDAL)
    dal.get_executive_kpis.return_value = ExecutiveKPIs(
        active_vendors_count=2,
        median_spend_per_vendor=-105.00,
    )
    dal.get_median_spend_trend.return_value = MedianSpendTrend(
        granularity="month",
        points=[
            MedianSpendPoint(period="2026-03", median_spend=-95.0, vendor_count=3),
            MedianSpendPoint(period="2026-04", median_spend=-105.0, vendor_count=2),
        ],
    )
    dal.get_ledger.return_value = [
        LedgerRow(date="2026-04-12", vendor="Coffee Shop", category="Dining", amount=-5.50),
        LedgerRow(date="2026-04-10", vendor="Employer", category="Income", amount=3500.00),
    ]
    dal.get_top_vendors.return_value = [
        AggregateRow(name="Landlord", total_spend=-2000.00),
        AggregateRow(name="Target", total_spend=-120.00),
    ]
    dal.get_bottom_vendors.return_value = [
        AggregateRow(name="Coffee Shop", total_spend=-5.50),
    ]
    dal.get_top_categories.return_value = [
        AggregateRow(name="Rent", total_spend=-2000.00),
        AggregateRow(name="Dining", total_spend=-5.50),
    ]
    dal.get_top_vendors_by_category.return_value = [
        AggregateRow(name="Coffee Shop", total_spend=-5.50),
    ]
    dal.get_vendor_directory.return_value = [
        VendorDirectoryRow(
            name="Target",
            transaction_count=3,
            total_spend=-120.00,
            primary_category="Shopping",
            last_active_date="2026-04-11",
        ),
        VendorDirectoryRow(
            name="Coffee Shop",
            transaction_count=1,
            total_spend=-5.50,
            primary_category="Dining",
            last_active_date="2026-04-12",
        ),
    ]
    dal.get_transactions_by_vendor.return_value = [
        LedgerRow(date="2026-04-12", vendor="Coffee Shop", category="Dining", amount=-5.50)
    ]
    return dal


def test_build_gui_renders_main_containers_and_calls_dal(mock_dal: Mock):
    """Verify build_gui constructs the layout without throwing exceptions and initial queries are called."""
    gui = build_gui(dal=mock_dal)
    assert gui is not None
    
    # Assert initial DAL queries executed
    mock_dal.get_executive_kpis.assert_called_once()
    mock_dal.get_median_spend_trend.assert_called_once()
    mock_dal.get_ledger.assert_called_once_with(limit=None, expenses_only=False)
    mock_dal.get_top_vendors.assert_called_once_with(limit_n=5)
    mock_dal.get_bottom_vendors.assert_called_once_with(limit_n=5)
    mock_dal.get_top_categories.assert_called_once_with(limit_n=10)
    mock_dal.get_vendor_directory.assert_called_once_with(search=None, expenses_only=False)
    assert gui.median_trend_chart is not None
    assert gui.trend_granularity_label is not None
    assert "Month-over-Month" in gui.trend_granularity_label.text


def test_open_vendor_inspection_drawer(mock_dal: Mock):
    """Verify inspecting a vendor queries vendor transactions and opens drawer."""
    gui = build_gui(dal=mock_dal)

    gui.inspect_vendor("Coffee Shop")
    assert gui.selected_vendor_for_inspection == "Coffee Shop"
    mock_dal.get_transactions_by_vendor.assert_called_with("Coffee Shop")
    assert gui.vendor_drawer is not None


def test_ledger_toggle_triggers_dal_with_expenses_only(mock_dal: Mock):
    """Verify toggling ledger expenses calls DAL with expenses_only=True."""
    gui = build_gui(dal=mock_dal)
    
    # Toggle ledger filter
    gui.toggle_ledger_expenses()
    assert gui.ledger_expenses_only is True
    mock_dal.get_ledger.assert_called_with(limit=None, expenses_only=True)


def test_vendor_directory_search_and_toggle(mock_dal: Mock):
    """Verify search input and vendor expense toggle refresh directory properly."""
    gui = build_gui(dal=mock_dal)
    
    # Apply search filter
    gui.filter_vendor_directory("target")
    assert gui.vendor_search_query == "target"
    mock_dal.get_vendor_directory.assert_called_with(search="target", expenses_only=False)
    
    # Toggle vendor expense filter
    gui.toggle_vendor_expenses()
    assert gui.vendor_expenses_only is True
    mock_dal.get_vendor_directory.assert_called_with(search="target", expenses_only=True)


def test_category_drill_down_selection(mock_dal: Mock):
    """Verify selecting a category triggers get_top_vendors_by_category."""
    gui = build_gui(dal=mock_dal)
    
    gui.select_category("Dining")
    assert gui.selected_category == "Dining"
    mock_dal.get_top_vendors_by_category.assert_called_with("Dining", limit_n=5)
