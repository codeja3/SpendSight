from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import Header, Footer, DataTable, TabbedContent, TabPane, Placeholder
from src.python.dal import SpendSightDAL

class SpendSightApp(App):
    """The main Textual dashboard for SpendSight."""
    
    TITLE = "SpendSight Analytics"
    
    # We use basic CSS to enforce the 2/3 (2fr) and 1/3 (1fr) split defined in SPEC.md
    CSS = """
    #ledger-pane {
        width: 2fr;
        height: 100%;
    }
    #analytics-pane {
        width: 1fr;
        height: 100%;
    }
    """

    def __init__(self, dal: SpendSightDAL, **kwargs):
        super().__init__(**kwargs)
        # Inject the Data Access Layer
        self.dal = dal

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
        
        with Horizontal():
            # Left Pane: The Ledger (2/3 width)
            yield DataTable(id="ledger-pane")
            
            # Right Pane: Analytics (1/3 width)
            with TabbedContent(id="analytics-pane"):
                
                with TabPane("Categories", id="tab-categories"):
                    yield Placeholder("Feature 2.3: Top-N Categories Bar Chart")
                    yield Placeholder("Feature 2.4: Top-N Vendors in Category Drill-down")
                    
                with TabPane("Vendors", id="tab-vendors"):
                    yield Placeholder("Feature 2.1: Top-N Vendors (Highest Spend)")
                    yield Placeholder("Feature 2.2: Bottom-N Vendors (Lowest Spend)")
                    
        yield Footer()

    def on_mount(self) -> None:
        """Load data into the UI when the app mounts."""
        # Setup the DataTable columns
        table = self.query_one(DataTable)
        table.add_columns("Date", "Vendor", "Category", "Amount")
        
        # Fetch the ledger data from our DAL
        ledger_rows = self.dal.get_ledger(limit=50, offset=0)
        
        # Populate the table
        for row in ledger_rows:
            table.add_row(row.date, row.vendor, row.category, f"${row.amount:,.2f}")