from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    Select,
    TabbedContent,
    TabPane,
)
from textual_plotext import PlotextPlot

from src.python.dal import SpendSightDAL


class SpendSightApp(App):
    """The main Textual dashboard for SpendSight."""
    
    TITLE = "SpendSight Analytics"
    
    CSS = """
    #ledger-container {
        width: 2fr;
        height: 100%;
    }
    #ledger-header-bar {
        height: auto;
        padding: 1;
        background: $boost;
        align-horizontal: right;
    }
    #ledger-income-toggle {
        dock: right;
    }
    #ledger-pane {
        height: 1fr;
    }
    #analytics-pane {
        width: 1fr;
        height: 100%;
    }
    .widget-title {
        padding: 1;
        text-style: bold;
        background: $boost;
    }
    #category-drill-down {
        height: 1fr;
    }
    #vendor-header-bar {
        height: auto;
        padding: 1;
        background: $boost;
        align-horizontal: right;
    }
    #vendor-income-toggle {
        dock: right;
    }
    #vendor-search-input {
        margin: 1 0;
    }
    #vendor-directory-table {
        height: 1fr;
    }
    """

    def __init__(self, dal: SpendSightDAL, **kwargs):
        super().__init__(**kwargs)
        self.dal = dal
        self.expenses_only = False
        self.vendor_expenses_only = False

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
        
        with Horizontal():
            # Left Pane: The Ledger (Feature 1)
            with Vertical(id="ledger-container"):
                with Horizontal(id="ledger-header-bar"):
                    yield Label("Ledger Transactions", classes="widget-title")
                    yield Button("Expenses Only", id="ledger-income-toggle", variant="default")
                yield DataTable(id="ledger-pane")
            
            # Right Pane: Analytics
            with TabbedContent(id="analytics-pane"):
                
                with TabPane("Categories", id="tab-categories"), VerticalScroll():
                    yield Label("Top Expenses by Category", classes="widget-title")
                    yield PlotextPlot(id="category-chart")
                    
                    yield Label("Vendor Drill-down by Category", classes="widget-title")
                    yield Select([], id="category-select", prompt="Select a Category...")
                    yield DataTable(id="category-drill-down")
                    
                with TabPane("Vendors", id="tab-vendors"), VerticalScroll():
                    yield Label("Top 5 Highest Spends", classes="widget-title")
                    yield DataTable(id="top-vendors-table")
                    
                    yield Label("Bottom 5 Lowest Spends", classes="widget-title")
                    yield DataTable(id="bottom-vendors-table")

                with TabPane("All Vendors", id="tab-all-vendors"), VerticalScroll():
                    with Horizontal(id="vendor-header-bar"):
                        yield Label("Vendor Directory", classes="widget-title")
                        yield Button("Expenses Only", id="vendor-income-toggle", variant="default")
                    yield Input(placeholder="Search vendors...", id="vendor-search-input")
                    yield DataTable(id="vendor-directory-table")
                    
        yield Footer()

    def on_mount(self) -> None:
        """Load data into the UI when the app mounts."""
        self._load_ledger()
        self._load_vendors()
        self._load_categories()
        self._load_vendor_directory()

    def _load_ledger(self) -> None:
        table = self.query_one("#ledger-pane", DataTable)
        if not table.columns:
            table.add_columns("Date", "Vendor", "Category", "Amount")
        table.clear()
        for row in self.dal.get_ledger(limit=50, offset=0, expenses_only=self.expenses_only):
            table.add_row(row.date, row.vendor, row.category, f"${row.amount:,.2f}")


    def _load_vendors(self) -> None:
        # Feature 2.1
        top_table = self.query_one("#top-vendors-table", DataTable)
        top_table.add_columns("Vendor", "Total Spend")
        for row in self.dal.get_top_vendors(limit_n=5):
            top_table.add_row(row.name, f"${row.total_spend:,.2f}")

        # Feature 2.2
        bottom_table = self.query_one("#bottom-vendors-table", DataTable)
        bottom_table.add_columns("Vendor", "Total Spend")
        for row in self.dal.get_bottom_vendors(limit_n=5):
            bottom_table.add_row(row.name, f"${row.total_spend:,.2f}")

    def _load_vendor_directory(self, search: str | None = None) -> None:
        # Feature 2.5: Populate the All Vendors directory table
        table = self.query_one("#vendor-directory-table", DataTable)
        if not table.columns:
            table.add_columns("Vendor", "Total Spend", "Txns", "Category", "Last Date")
        table.clear()
        for row in self.dal.get_vendor_directory(search=search, expenses_only=self.vendor_expenses_only):
            spend_str = f"-${abs(row.total_spend):,.2f}" if row.total_spend < 0 else f"${row.total_spend:,.2f}"
            table.add_row(
                row.name,
                spend_str,
                str(row.transaction_count),
                row.primary_category,
                row.last_active_date,
            )

    def _load_categories(self) -> None:
        categories = self.dal.get_top_categories(limit_n=10)
        
        # Feature 2.3: Populate the Plotext Chart
        plot = self.query_one("#category-chart", PlotextPlot)
        names = [c.name for c in categories]
        # Plotext visually handles positive bars better, so we use abs() for the chart
        spends = [abs(c.total_spend) for c in categories] 
        
        plt = plot.plt
        plt.bar(names, spends)
        plt.title("Expenses by Category")
        plt.theme("dark")
        plot.refresh()

        # Setup Feature 2.4: Populate the Dropdown Select
        select = self.query_one("#category-select", Select)
        select.set_options([(c.name, c.name) for c in categories])
        
        drill_table = self.query_one("#category-drill-down", DataTable)
        drill_table.add_columns("Vendor", "Spend")

    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle category selection for drill-down (Feature 2.4)."""
        if event.select.id == "category-select" and event.value != Select.BLANK:
            drill_table = self.query_one("#category-drill-down", DataTable)
            drill_table.clear()
            
            vendors = self.dal.get_top_vendors_by_category(str(event.value), limit_n=5)
            for v in vendors:
                drill_table.add_row(v.name, f"${v.total_spend:,.2f}")

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle real-time vendor directory search (Feature 2.5)."""
        if event.input.id == "vendor-search-input":
            query = event.value.strip() or None
            self._load_vendor_directory(search=query)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle toggle between All Transactions and Expenses Only."""
        if event.button.id == "ledger-income-toggle":
            self.expenses_only = not self.expenses_only
            event.button.label = "Show All" if self.expenses_only else "Expenses Only"
            event.button.variant = "primary" if self.expenses_only else "default"
            self._load_ledger()
        elif event.button.id == "vendor-income-toggle":
            self.vendor_expenses_only = not self.vendor_expenses_only
            event.button.label = "Show All" if self.vendor_expenses_only else "Expenses Only"
            event.button.variant = "primary" if self.vendor_expenses_only else "default"
            search_input = self.query_one("#vendor-search-input", Input)
            query = search_input.value.strip() or None
            self._load_vendor_directory(search=query)



if __name__ == "__main__":
    import os
    
    # We default to a local SQLite file, but allow an environment variable override
    db_path = os.getenv("SPENDSIGHT_DB", "spendsight.db")
    
    # Instantiate the DAL and inject it into the Textual App
    dal = SpendSightDAL(db_path)
    app = SpendSightApp(dal=dal)
    
    # Launch the terminal UI
    app.run()