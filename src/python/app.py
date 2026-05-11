from textual.app import App, ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Header, Footer, DataTable, TabbedContent, TabPane, Select, Label
from textual_plotext import PlotextPlot
from src.python.dal import SpendSightDAL

class SpendSightApp(App):
    """The main Textual dashboard for SpendSight."""
    
    TITLE = "SpendSight Analytics"
    
    CSS = """
    #ledger-pane {
        width: 2fr;
        height: 100%;
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
    """

    def __init__(self, dal: SpendSightDAL, **kwargs):
        super().__init__(**kwargs)
        self.dal = dal

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
        
        with Horizontal():
            # Left Pane: The Ledger (Feature 1)
            yield DataTable(id="ledger-pane")
            
            # Right Pane: Analytics
            with TabbedContent(id="analytics-pane"):
                
                with TabPane("Categories", id="tab-categories"):
                    with VerticalScroll():
                        yield Label("Top Expenses by Category", classes="widget-title")
                        yield PlotextPlot(id="category-chart")
                        
                        yield Label("Vendor Drill-down by Category", classes="widget-title")
                        yield Select([], id="category-select", prompt="Select a Category...")
                        yield DataTable(id="category-drill-down")
                    
                with TabPane("Vendors", id="tab-vendors"):
                    with VerticalScroll():
                        yield Label("Top 5 Highest Spends", classes="widget-title")
                        yield DataTable(id="top-vendors-table")
                        
                        yield Label("Bottom 5 Lowest Spends", classes="widget-title")
                        yield DataTable(id="bottom-vendors-table")
                    
        yield Footer()

    def on_mount(self) -> None:
        """Load data into the UI when the app mounts."""
        self._load_ledger()
        self._load_vendors()
        self._load_categories()

    def _load_ledger(self) -> None:
        table = self.query_one("#ledger-pane", DataTable)
        table.add_columns("Date", "Vendor", "Category", "Amount")
        for row in self.dal.get_ledger(limit=50, offset=0):
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

if __name__ == "__main__":
    import os
    
    # We default to a local SQLite file, but allow an environment variable override
    db_path = os.getenv("SPENDSIGHT_DB", "spendsight.db")
    
    # Instantiate the DAL and inject it into the Textual App
    dal = SpendSightDAL(db_path)
    app = SpendSightApp(dal=dal)
    
    # Launch the terminal UI
    app.run()