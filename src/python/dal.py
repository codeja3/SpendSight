import sqlite3

from pydantic import BaseModel


# Schema Definitions from SPEC.md Section 6.1
class LedgerRow(BaseModel):
    date: str
    vendor: str
    category: str
    amount: float

class AggregateRow(BaseModel):
    name: str 
    total_spend: float

class VendorDirectoryRow(BaseModel):
    name: str
    transaction_count: int
    total_spend: float
    primary_category: str
    last_active_date: str

class ExecutiveKPIs(BaseModel):
    total_expenses: float
    net_income: float
    active_vendors_count: int
    top_expense_category: str | None
    top_expense_vendor: str | None

class SpendSightDAL:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def _execute_query(self, query: str, params: tuple = ()) -> list[sqlite3.Row]:
        """Helper method to handle connection context and row factory."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.fetchall()

    def get_ledger(self, limit: int | None = None, offset: int = 0, expenses_only: bool = False) -> list[LedgerRow]:
        """Feature 1: Retrieves chronological transactions."""
        where_clause = "WHERE amount < 0" if expenses_only else ""
        pagination_clause = ""
        params: list[int] = []

        if limit is not None:
            pagination_clause = "LIMIT ? OFFSET ?"
            params.extend([limit, offset])
        elif offset > 0:
            pagination_clause = "LIMIT -1 OFFSET ?"
            params.append(offset)

        query = f"""
            SELECT transaction_date AS date, vendor, category, amount 
            FROM transactions 
            {where_clause}
            ORDER BY transaction_date DESC 
            {pagination_clause}
        """
        rows = self._execute_query(query, tuple(params))
        return [LedgerRow(**dict(row)) for row in rows]


    def get_top_vendors(self, limit_n: int = 5) -> list[AggregateRow]:
        """Feature 2.1: Retrieves the vendors with the most negative sum."""
        query = """
            SELECT vendor as name, SUM(amount) as total_spend 
            FROM transactions 
            WHERE amount < 0 
            GROUP BY vendor 
            ORDER BY total_spend ASC 
            LIMIT ?
        """
        rows = self._execute_query(query, (limit_n,))
        return [AggregateRow(**dict(row)) for row in rows]

    def get_bottom_vendors(self, limit_n: int = 5) -> list[AggregateRow]:
        """Feature 2.2: Retrieves the vendors with the sum closest to zero."""
        query = """
            SELECT vendor as name, SUM(amount) as total_spend 
            FROM transactions 
            WHERE amount < 0 
            GROUP BY vendor 
            ORDER BY total_spend DESC 
            LIMIT ?
        """
        rows = self._execute_query(query, (limit_n,))
        return [AggregateRow(**dict(row)) for row in rows]

    def get_top_categories(self, limit_n: int = 5) -> list[AggregateRow]:
        """Feature 2.3: Aggregates total expenses by category."""
        query = """
            SELECT category as name, SUM(amount) as total_spend 
            FROM transactions 
            WHERE amount < 0 
            GROUP BY category 
            ORDER BY total_spend ASC 
            LIMIT ?
        """
        rows = self._execute_query(query, (limit_n,))
        return [AggregateRow(**dict(row)) for row in rows]

    def get_top_vendors_by_category(self, target_category: str, limit_n: int = 5) -> list[AggregateRow]:
        """Feature 2.4: Drill-down metric for specific budget areas."""
        query = """
            SELECT vendor as name, SUM(amount) as total_spend 
            FROM transactions 
            WHERE category = ? AND amount < 0 
            GROUP BY vendor 
            ORDER BY total_spend ASC 
            LIMIT ?
        """
        rows = self._execute_query(query, (target_category, limit_n))
        return [AggregateRow(**dict(row)) for row in rows]

    def get_vendor_directory(self, search: str | None = None, expenses_only: bool = False) -> list[VendorDirectoryRow]:
        """Feature 2.5: Retrieves all unique vendors with count, net spend, primary category, and last date."""
        where_conditions = ["t.vendor IS NOT NULL", "t.vendor != ''"]
        subquery_expense_filter = ""
        params: list[str] = []

        if expenses_only:
            where_conditions.append("t.amount < 0")
            subquery_expense_filter = " AND t2.amount < 0"

        if search:
            where_conditions.append("LOWER(t.vendor) LIKE ?")
            params.append(f"%{search.lower()}%")

        where_clause = " AND ".join(where_conditions)

        query = f"""
            SELECT 
                t.vendor as name,
                COUNT(*) as transaction_count,
                SUM(t.amount) as total_spend,
                (
                    SELECT t2.category 
                    FROM transactions t2 
                    WHERE t2.vendor = t.vendor{subquery_expense_filter}
                    GROUP BY t2.category 
                    ORDER BY COUNT(*) DESC, t2.category ASC 
                    LIMIT 1
                ) as primary_category,
                MAX(t.transaction_date) as last_active_date
            FROM transactions t
            WHERE {where_clause}
            GROUP BY t.vendor 
            ORDER BY total_spend ASC, t.vendor COLLATE NOCASE ASC
        """

        rows = self._execute_query(query, tuple(params))
        return [VendorDirectoryRow(**dict(row)) for row in rows]

    def get_executive_kpis(self) -> ExecutiveKPIs:
        """Computes top-level KPI metrics: total expenses, net income, active vendor count, top category, and top vendor."""
        # 1. Total expenses (amount < 0) and Net income (sum of all amounts)
        totals_query = """
            SELECT 
                COALESCE(SUM(CASE WHEN amount < 0 THEN amount ELSE 0 END), 0.0) as total_expenses,
                COALESCE(SUM(amount), 0.0) as net_income,
                COUNT(DISTINCT CASE WHEN vendor IS NOT NULL AND vendor != '' THEN vendor END) as active_vendors_count
            FROM transactions
        """
        totals_row = self._execute_query(totals_query)[0]

        # 2. Top category (most negative sum)
        top_cats = self.get_top_categories(limit_n=1)
        top_category = top_cats[0].name if top_cats else None

        # 3. Top vendor (most negative sum)
        top_vens = self.get_top_vendors(limit_n=1)
        top_vendor = top_vens[0].name if top_vens else None

        return ExecutiveKPIs(
            total_expenses=float(totals_row["total_expenses"]),
            net_income=float(totals_row["net_income"]),
            active_vendors_count=int(totals_row["active_vendors_count"]),
            top_expense_category=top_category,
            top_expense_vendor=top_vendor,
        )

    def get_transactions_by_vendor(self, vendor: str) -> list[LedgerRow]:
        """Retrieves all chronological transactions for a specific vendor."""
        query = """
            SELECT transaction_date AS date, vendor, category, amount 
            FROM transactions 
            WHERE vendor = ?
            ORDER BY transaction_date DESC
        """
        rows = self._execute_query(query, (vendor,))
        return [LedgerRow(**dict(row)) for row in rows]