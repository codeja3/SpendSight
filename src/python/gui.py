import os

from nicegui import ui

from src.python.dal import SpendSightDAL


class SpendSightGUI:
    """NiceGUI web frontend controller for SpendSight with Hybrid Analytics-First Layout."""

    def __init__(self, dal: SpendSightDAL) -> None:
        self.dal = dal
        self.ledger_expenses_only = False
        self.vendor_expenses_only = False
        self.vendor_search_query: str | None = None
        self.selected_category: str | None = None
        self.selected_vendor_for_inspection: str | None = None

        # Component handles
        self.kpi_vendors_label: ui.label | None = None
        self.kpi_median_spend_label: ui.label | None = None
        self.median_trend_chart: ui.echart | None = None
        self.trend_granularity_label: ui.label | None = None

        self.category_chart: ui.echart | None = None
        self.category_select: ui.select | None = None
        self.category_drill_table: ui.table | None = None

        self.vendor_table: ui.table | None = None
        self.vendor_toggle_btn: ui.button | None = None

        # Slide-out Drawer for Vendor Transactions
        self.vendor_drawer: ui.right_drawer | None = None
        self.drawer_title_label: ui.label | None = None
        self.drawer_stats_label: ui.label | None = None
        self.drawer_table: ui.table | None = None

        # Dedicated Full Ledger tab components
        self.ledger_table: ui.table | None = None
        self.ledger_toggle_btn: ui.button | None = None

    def format_currency(self, amount: float) -> str:
        if amount < 0:
            return f"-${abs(amount):,.2f}"
        return f"${amount:,.2f}"

    def build_layout(self) -> None:
        # Theme styling
        ui.colors(primary="#2563eb", secondary="#64748b", accent="#10b981", dark="#0f172a")

        # Top Navigation Header with Brand & Global Tabs
        with ui.header().classes("items-center justify-between bg-slate-900 text-white px-6 py-2 shadow-md"):
            with ui.row().classes("items-center gap-2"):
                ui.icon("insights", size="md").classes("text-blue-400")
                ui.label("SpendSight: Vendor-Level Spending Intelligence").classes("text-xl font-bold tracking-tight")

            with ui.tabs().classes("text-white") as nav_tabs:
                tab_analytics = ui.tab("Analytics Hub", icon="dashboard")
                tab_ledger = ui.tab("Full Ledger", icon="receipt_long")

        # Slide-Out Inspection Drawer
        with ui.right_drawer(value=False).classes("bg-slate-50 p-4 w-96 md:w-[480px] shadow-2xl") as drawer:
            self.vendor_drawer = drawer
            with ui.row().classes("w-full items-center justify-between border-b pb-2 mb-3"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("storefront", size="sm").classes("text-blue-600")
                    self.drawer_title_label = ui.label("Vendor Inspector").classes("text-base font-bold text-slate-800")
                ui.button(icon="close", on_click=drawer.hide).props("flat round dense")

            self.drawer_stats_label = ui.label("").classes("text-xs text-slate-500 mb-3")

            drawer_cols = [
                {"name": "date", "label": "Date", "field": "date", "sortable": True, "align": "left"},
                {"name": "category", "label": "Category", "field": "category", "sortable": True, "align": "left"},
                {"name": "amount", "label": "Amount", "field": "amount_str", "sortable": True, "align": "right"},
            ]
            self.drawer_table = ui.table(
                columns=drawer_cols,
                rows=[],
                pagination={"rowsPerPage": 10},
            ).classes("w-full")

        # Tab Panels
        with ui.tab_panels(nav_tabs, value=tab_analytics).classes("w-full p-4 bg-slate-100 min-h-screen"):
            # ==========================================
            # TAB 1: Analytics Hub (Default Home View)
            # ==========================================
            with ui.tab_panel(tab_analytics).classes("p-0 space-y-4"):
                # 1. Top Ribbon: 1/3 KPI Cards (stacked) + 2/3 Smart Trend Graph Box
                with ui.row().classes("w-full gap-4 items-stretch"):
                    # 1/3 Left: 2 KPI metric boxes stacked vertically
                    with ui.column().classes("w-full md:w-[32%] gap-4 justify-between"):
                        with ui.card().classes("w-full p-4 bg-white shadow-sm border-l-4 border-blue-500 flex-1"):
                            ui.label("Active Vendors Tracked").classes("text-xs font-semibold text-slate-500 uppercase")
                            self.kpi_vendors_label = ui.label("0").classes("text-2xl font-bold text-slate-800")

                        with ui.card().classes("w-full p-4 bg-white shadow-sm border-l-4 border-purple-500 flex-1"):
                            ui.label("Median Spend Per Vendor").classes("text-xs font-semibold text-slate-500 uppercase")
                            self.kpi_median_spend_label = ui.label("$0.00").classes("text-2xl font-bold text-slate-800")

                    # 2/3 Right: Smart Median Spend Trend Graph box
                    with ui.card().classes("w-full md:w-[66%] flex-1 p-4 bg-white shadow-sm"):
                        with ui.row().classes("w-full items-center justify-between border-b pb-1 mb-1"):
                            with ui.row().classes("items-center gap-2"):
                                ui.icon("show_chart", size="xs").classes("text-purple-600")
                                ui.label("Median Spend Development").classes("font-bold text-slate-800 text-sm")
                            self.trend_granularity_label = ui.label("Month-over-Month").classes("text-xs text-purple-700 bg-purple-50 px-2 py-0.5 rounded font-medium")

                        self.median_trend_chart = ui.echart({
                            "tooltip": {"trigger": "axis", "formatter": "{b}: ${c}"},
                            "grid": {"left": "10%", "right": "5%", "top": "12%", "bottom": "20%"},
                            "xAxis": {"type": "category", "data": [], "axisLabel": {"fontSize": 10}},
                            "yAxis": {"type": "value", "axisLabel": {"formatter": "${value}"}},
                            "series": [{
                                "data": [],
                                "type": "line",
                                "smooth": True,
                                "symbol": "circle",
                                "symbolSize": 6,
                                "lineStyle": {"color": "#8b5cf6", "width": 3},
                                "itemStyle": {"color": "#7c3aed"},
                                "areaStyle": {"color": "rgba(139, 92, 246, 0.15)"},
                            }],
                        }).classes("w-full h-32")

                # 2. Main Analytics Columns (~45% Left / ~55% Right)
                with ui.row().classes("w-full gap-4 items-start no-wrap"):
                    # Left Column: Category Chart & Drill-down
                    with ui.card().classes("w-[45%] p-4 bg-white shadow-sm space-y-3"):
                        with ui.row().classes("items-center justify-between border-b pb-2"):
                            ui.label("Top Expenses by Category").classes("font-bold text-slate-800 text-sm")
                            ui.label("Tap bar or select to drill").classes("text-xs text-slate-400")

                        self.category_chart = ui.echart({
                            "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
                            "xAxis": {"type": "category", "data": [], "axisLabel": {"rotate": 35, "interval": 0, "fontSize": 11}},
                            "yAxis": {"type": "value"},
                            "series": [{"data": [], "type": "bar", "color": "#2563eb", "barMaxWidth": 32}],
                            "grid": {"left": "12%", "right": "5%", "bottom": "25%"},
                        }).classes("w-full h-72")

                        ui.separator()
                        ui.label("Category Vendor Drill-down").classes("font-bold text-slate-800 text-sm")
                        self.category_select = ui.select(
                            options=[],
                            label="Select Category to inspect",
                            on_change=lambda e: self.select_category(e.value),
                        ).classes("w-full")

                        drill_cols = [
                            {"name": "vendor", "label": "Vendor (Click to inspect)", "field": "name", "align": "left"},
                            {"name": "spend", "label": "Spend", "field": "spend_str", "align": "right"},
                        ]
                        self.category_drill_table = ui.table(
                            columns=drill_cols,
                            rows=[],
                            pagination={"rowsPerPage": 5},
                        ).classes("w-full")
                        # Wire row click to inspect vendor
                        self.category_drill_table.on(
                            "rowClick",
                            lambda e: self.inspect_vendor(e.args[1]["name"]),
                        )

                    # Right Column: Vendor Directory & Extremes
                    with ui.card().classes("w-[55%] p-4 bg-white shadow-sm space-y-3"):
                        with ui.row().classes("w-full items-center justify-between border-b pb-2"):
                            with ui.row().classes("items-center gap-2"):
                                ui.label("Vendor Intelligence Directory").classes("font-bold text-slate-800 text-sm")
                                ui.label("(Click row to audit)").classes("text-xs text-slate-400")
                            self.vendor_toggle_btn = ui.button(
                                "Expenses Only",
                                on_click=self.toggle_vendor_expenses,
                            ).props("outline dense").classes("text-xs")

                        ui.input(
                            placeholder="Search vendors...",
                            on_change=lambda e: self.filter_vendor_directory(e.value),
                        ).props("clearable dense outlined").classes("w-full")

                        directory_cols = [
                            {"name": "name", "label": "Vendor", "field": "name", "sortable": True, "align": "left"},
                            {"name": "spend", "label": "Total Spend", "field": "spend_str", "sortable": True, "align": "right"},
                            {"name": "txns", "label": "Txns", "field": "transaction_count", "sortable": True, "align": "center"},
                            {"name": "category", "label": "Primary Category", "field": "primary_category", "sortable": True, "align": "left"},
                            {"name": "last_date", "label": "Last Date", "field": "last_active_date", "sortable": True, "align": "center"},
                        ]
                        self.vendor_table = ui.table(
                            columns=directory_cols,
                            rows=[],
                            pagination={"rowsPerPage": 8},
                        ).classes("w-full cursor-pointer")
                        self.vendor_table.on(
                            "rowClick",
                            lambda e: self.inspect_vendor(e.args[1]["name"]),
                        )

                        ui.separator().classes("my-2")
                        # Outliers Highlights
                        with ui.row().classes("w-full gap-3"):
                            with ui.column().classes("flex-1 p-2 bg-slate-50 rounded border"):
                                ui.label("Top 5 Highest Spends").classes("text-xs font-bold text-slate-700")
                                top_vendors = self.dal.get_top_vendors(limit_n=5)
                                for r in top_vendors:
                                    with ui.row().classes("w-full justify-between items-center text-xs py-0.5"):
                                        ui.button(r.name, on_click=lambda _, name=r.name: self.inspect_vendor(name)).props("flat dense no-caps").classes("text-blue-600 p-0 text-xs truncate")
                                        ui.label(self.format_currency(r.total_spend)).classes("font-semibold text-slate-700")

                            with ui.column().classes("flex-1 p-2 bg-slate-50 rounded border"):
                                ui.label("Bottom 5 Lowest Spends").classes("text-xs font-bold text-slate-700")
                                bottom_vendors = self.dal.get_bottom_vendors(limit_n=5)
                                for r in bottom_vendors:
                                    with ui.row().classes("w-full justify-between items-center text-xs py-0.5"):
                                        ui.button(r.name, on_click=lambda _, name=r.name: self.inspect_vendor(name)).props("flat dense no-caps").classes("text-blue-600 p-0 text-xs truncate")
                                        ui.label(self.format_currency(r.total_spend)).classes("font-semibold text-slate-700")

            # ==========================================
            # TAB 2: Dedicated Full Ledger Tab
            # ==========================================
            with ui.tab_panel(tab_ledger).classes("p-0"), ui.card().classes("w-full p-4 bg-white shadow-sm space-y-3"):
                with ui.row().classes("w-full items-center justify-between border-b pb-2"):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("receipt_long", size="sm").classes("text-blue-600")
                        ui.label("Chronological Transaction Ledger").classes("font-bold text-slate-800 text-base")
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
                    pagination={"rowsPerPage": 25},
                ).classes("w-full")

        # Initial data loading
        self.load_kpis()
        self.load_median_trend()
        self.load_categories()
        self.load_vendor_directory()
        self.load_ledger()

    def load_kpis(self) -> None:
        kpis = self.dal.get_executive_kpis()
        if self.kpi_vendors_label is not None:
            self.kpi_vendors_label.text = str(kpis.active_vendors_count)
        if self.kpi_median_spend_label is not None:
            self.kpi_median_spend_label.text = self.format_currency(kpis.median_spend_per_vendor)

    def load_median_trend(self) -> None:
        trend = self.dal.get_median_spend_trend()
        
        # Format granularity badge
        granularity_display = {
            "month": "Month-over-Month",
            "quarter": "Quarterly Trend",
            "year": "Annual Trend",
        }.get(trend.granularity, "Trend")
        
        if self.trend_granularity_label is not None:
            self.trend_granularity_label.text = granularity_display

        periods = [p.period for p in trend.points]
        medians = [round(abs(p.median_spend), 2) for p in trend.points]

        if self.median_trend_chart is not None:
            self.median_trend_chart.options["xAxis"]["data"] = periods
            self.median_trend_chart.options["series"][0]["data"] = medians
            self.median_trend_chart.update()

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

    def inspect_vendor(self, vendor_name: str) -> None:
        """Opens slide-out drawer populated with chronological transactions for the specified vendor."""
        self.selected_vendor_for_inspection = vendor_name
        txns = self.dal.get_transactions_by_vendor(vendor_name)

        if self.drawer_title_label is not None:
            self.drawer_title_label.text = vendor_name

        total_vendor_spend = sum(t.amount for t in txns)
        if self.drawer_stats_label is not None:
            self.drawer_stats_label.text = f"{len(txns)} transactions • Net: {self.format_currency(total_vendor_spend)}"

        drawer_rows = [
            {
                "date": t.date,
                "category": t.category,
                "amount": t.amount,
                "amount_str": self.format_currency(t.amount),
            }
            for t in txns
        ]

        if self.drawer_table is not None:
            self.drawer_table.rows = drawer_rows
            self.drawer_table.update()

        if self.vendor_drawer is not None:
            self.vendor_drawer.show()

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

    ui.run(title="SpendSight: Vendor-Level Spending Intelligence", port=8080, reload=False)


if __name__ in {"__main__", "__mp_main__"}:
    main()
