import os

from nicegui import ui

from src.python.dal import SpendSightDAL


class SpendSightGUI:
    """NiceGUI web frontend controller for SpendSight."""

    def __init__(self, dal: SpendSightDAL) -> None:
        self.dal = dal
        self.ledger_expenses_only = False
        self.vendor_expenses_only = False
        self.vendor_search_query: str | None = None
        self.selected_category: str | None = None

        # Component handles
        self.ledger_table: ui.table | None = None
        self.ledger_toggle_btn: ui.button | None = None
        self.vendor_toggle_btn: ui.button | None = None
        self.vendor_table: ui.table | None = None
        self.category_drill_table: ui.table | None = None
        self.category_chart: ui.echart | None = None
        self.category_select: ui.select | None = None

    def format_currency(self, amount: float) -> str:
        if amount < 0:
            return f"-${abs(amount):,.2f}"
        return f"${amount:,.2f}"

    def build_layout(self) -> None:
        # Global dark styling & fonts
        ui.colors(primary="#3b82f6", secondary="#64748b", accent="#10b981", dark="#0f172a")

        # Top Header
        with ui.header().classes("items-center justify-between bg-slate-900 text-white px-6 py-3"):
            with ui.row().classes("items-center gap-2"):
                ui.icon("insights", size="md").classes("text-blue-400")
                ui.label("SpendSight Analytics").classes("text-xl font-bold tracking-tight")
            ui.label("Vendor-Level Spending Intelligence").classes("text-sm text-slate-400")

        # Main Split Content
        with ui.row().classes("w-full p-4 gap-4 no-wrap items-stretch"):
            # Left Pane: Ledger (2/3 width)
            with ui.card().classes("w-2/3 p-4 shadow-sm"):
                with ui.row().classes("w-full items-center justify-between pb-2 mb-2 border-b"):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("receipt_long").classes("text-blue-500")
                        ui.label("Ledger Transactions").classes("text-lg font-bold")
                    self.ledger_toggle_btn = ui.button(
                        "Expenses Only",
                        on_click=self.toggle_ledger_expenses,
                    ).props("outline dense").classes("text-xs")

                ledger_columns = [
                    {"name": "date", "label": "Date", "field": "date", "sortable": True, "align": "left"},
                    {"name": "vendor", "label": "Vendor", "field": "vendor", "sortable": True, "align": "left"},
                    {"name": "category", "label": "Category", "field": "category", "sortable": True, "align": "left"},
                    {"name": "amount", "label": "Amount", "field": "amount_str", "sortable": True, "align": "right"},
                ]
                self.ledger_table = ui.table(
                    columns=ledger_columns,
                    rows=[],
                    row_key="id",
                    pagination={"rowsPerPage": 20},
                ).classes("w-full")

            # Right Pane: Analytics (1/3 width)
            with ui.card().classes("w-1/3 p-4 shadow-sm"):
                with ui.tabs().classes("w-full border-b") as tabs:
                    tab_categories = ui.tab("Categories", icon="pie_chart")
                    tab_vendors = ui.tab("Vendors", icon="leaderboard")
                    tab_all_vendors = ui.tab("All Vendors", icon="storefront")

                with ui.tab_panels(tabs, value=tab_categories).classes("w-full pt-3"):
                    # Tab 1: Categories
                    with ui.tab_panel(tab_categories):
                        ui.label("Top Expenses by Category").classes("font-semibold text-sm mb-2 text-slate-700")
                        self.category_chart = ui.echart({
                            "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
                            "xAxis": {"type": "category", "data": [], "axisLabel": {"rotate": 30, "interval": 0}},
                            "yAxis": {"type": "value"},
                            "series": [{"data": [], "type": "bar", "color": "#3b82f6"}],
                        }).classes("w-full h-64")

                        ui.separator().classes("my-3")
                        ui.label("Vendor Drill-down by Category").classes("font-semibold text-sm mb-1 text-slate-700")
                        self.category_select = ui.select(
                            options=[],
                            label="Select Category",
                            on_change=lambda e: self.select_category(e.value),
                        ).classes("w-full mb-2")

                        drill_cols = [
                            {"name": "vendor", "label": "Vendor", "field": "name", "align": "left"},
                            {"name": "spend", "label": "Spend", "field": "spend_str", "align": "right"},
                        ]
                        self.category_drill_table = ui.table(
                            columns=drill_cols,
                            rows=[],
                            pagination={"rowsPerPage": 5},
                        ).classes("w-full")

                    # Tab 2: Vendors (Top 5 & Bottom 5)
                    with ui.tab_panel(tab_vendors):
                        ui.label("Top 5 Highest Spends").classes("font-semibold text-sm mb-2 text-slate-700")
                        top_cols = [
                            {"name": "name", "label": "Vendor", "field": "name", "align": "left"},
                            {"name": "spend", "label": "Total Spend", "field": "spend_str", "align": "right"},
                        ]
                        top_vendors = self.dal.get_top_vendors(limit_n=5)
                        top_rows = [
                            {"name": r.name, "spend_str": self.format_currency(r.total_spend)}
                            for r in top_vendors
                        ]
                        ui.table(columns=top_cols, rows=top_rows).classes("w-full mb-4")

                        ui.label("Bottom 5 Lowest Spends").classes("font-semibold text-sm mb-2 text-slate-700")
                        bottom_vendors = self.dal.get_bottom_vendors(limit_n=5)
                        bottom_rows = [
                            {"name": r.name, "spend_str": self.format_currency(r.total_spend)}
                            for r in bottom_vendors
                        ]
                        ui.table(columns=top_cols, rows=bottom_rows).classes("w-full")

                    # Tab 3: All Vendors Directory
                    with ui.tab_panel(tab_all_vendors):
                        with ui.row().classes("w-full items-center justify-between pb-2 mb-2 border-b"):
                            ui.label("Vendor Directory").classes("font-semibold text-sm")
                            self.vendor_toggle_btn = ui.button(
                                "Expenses Only",
                                on_click=self.toggle_vendor_expenses,
                            ).props("outline dense").classes("text-xs")

                        ui.input(
                            placeholder="Search vendors...",
                            on_change=lambda e: self.filter_vendor_directory(e.value),
                        ).props("clearable dense outlined").classes("w-full mb-3")

                        directory_cols = [
                            {"name": "name", "label": "Vendor", "field": "name", "sortable": True, "align": "left"},
                            {"name": "spend", "label": "Total Spend", "field": "spend_str", "sortable": True, "align": "right"},
                            {"name": "txns", "label": "Txns", "field": "transaction_count", "sortable": True, "align": "center"},
                            {"name": "category", "label": "Category", "field": "primary_category", "sortable": True, "align": "left"},
                            {"name": "last_date", "label": "Last Date", "field": "last_active_date", "sortable": True, "align": "center"},
                        ]
                        self.vendor_table = ui.table(
                            columns=directory_cols,
                            rows=[],
                            pagination={"rowsPerPage": 10},
                        ).classes("w-full")

        # Initial data loading
        self.load_ledger()
        self.load_categories()
        self.load_vendor_directory()

    def load_ledger(self) -> None:
        rows = self.dal.get_ledger(limit=None, expenses_only=self.ledger_expenses_only)
        table_rows = [
            {
                "id": idx,
                "date": r.date,
                "vendor": r.vendor,
                "category": r.category,
                "amount": r.amount,
                "amount_str": self.format_currency(r.amount),
            }
            for idx, r in enumerate(rows)
        ]
        if self.ledger_table is not None:
            self.ledger_table.rows = table_rows
            self.ledger_table.update()

    def toggle_ledger_expenses(self) -> None:
        self.ledger_expenses_only = not self.ledger_expenses_only
        if self.ledger_toggle_btn is not None:
            self.ledger_toggle_btn.text = "Show All" if self.ledger_expenses_only else "Expenses Only"
            self.ledger_toggle_btn.props("color=primary" if self.ledger_expenses_only else "outline")
        self.load_ledger()

    def load_categories(self) -> None:
        categories = self.dal.get_top_categories(limit_n=10)
        names = [c.name for c in categories]
        spends = [abs(c.total_spend) for c in categories]

        if self.category_chart is not None:
            self.category_chart.options["xAxis"]["data"] = names
            self.category_chart.options["series"][0]["data"] = spends
            self.category_chart.update()

        if self.category_select is not None:
            self.category_select.options = names
            self.category_select.update()

    def select_category(self, category: str | None) -> None:
        self.selected_category = category
        if not category:
            if self.category_drill_table is not None:
                self.category_drill_table.rows = []
                self.category_drill_table.update()
            return

        vendors = self.dal.get_top_vendors_by_category(category, limit_n=5)
        rows = [
            {"name": v.name, "spend_str": self.format_currency(v.total_spend)}
            for v in vendors
        ]
        if self.category_drill_table is not None:
            self.category_drill_table.rows = rows
            self.category_drill_table.update()

    def filter_vendor_directory(self, query: str | None) -> None:
        cleaned_query = query.strip() if query else None
        self.vendor_search_query = cleaned_query or None
        self.load_vendor_directory()

    def toggle_vendor_expenses(self) -> None:
        self.vendor_expenses_only = not self.vendor_expenses_only
        if self.vendor_toggle_btn is not None:
            self.vendor_toggle_btn.text = "Show All" if self.vendor_expenses_only else "Expenses Only"
            self.vendor_toggle_btn.props("color=primary" if self.vendor_expenses_only else "outline")
        self.load_vendor_directory()

    def load_vendor_directory(self) -> None:
        rows = self.dal.get_vendor_directory(
            search=self.vendor_search_query,
            expenses_only=self.vendor_expenses_only,
        )
        table_rows = [
            {
                "name": r.name,
                "spend_str": self.format_currency(r.total_spend),
                "transaction_count": r.transaction_count,
                "primary_category": r.primary_category,
                "last_active_date": r.last_active_date,
            }
            for r in rows
        ]
        if self.vendor_table is not None:
            self.vendor_table.rows = table_rows
            self.vendor_table.update()


def build_gui(dal: SpendSightDAL) -> SpendSightGUI:
    """Instantiate and construct the SpendSight NiceGUI layout."""
    gui = SpendSightGUI(dal=dal)
    gui.build_layout()
    return gui


def main() -> None:
    db_path = os.getenv("SPENDSIGHT_DB", "spendsight.db")
    dal = SpendSightDAL(db_path)

    @ui.page("/")
    def index():
        build_gui(dal)

    ui.run(title="SpendSight Analytics", port=8080, reload=False)


if __name__ in {"__main__", "__mp_main__"}:
    main()
