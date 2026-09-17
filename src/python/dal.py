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

    def get_ledger(self, limit: int = 50, offset: int = 0) -> list[LedgerRow]:
        """Feature 1: Retrieves chronological transactions."""
        query = """
            SELECT transaction_date AS date, vendor, category, amount 
            FROM transactions 
            ORDER BY transaction_date DESC 
            LIMIT ? OFFSET ?
        """
        rows = self._execute_query(query, (limit, offset))
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

    def get_vendor_directory(self, search: str | None = None) -> list[VendorDirectoryRow]:
        """Feature 2.5: Retrieves all unique vendors with count, net spend, primary category, and last date."""
        query = """
            SELECT 
                t.vendor as name,
                COUNT(*) as transaction_count,
                SUM(t.amount) as total_spend,
                (
                    SELECT t2.category 
                    FROM transactions t2 
                    WHERE t2.vendor = t.vendor 
                    GROUP BY t2.category 
                    ORDER BY COUNT(*) DESC, t2.category ASC 
                    LIMIT 1
                ) as primary_category,
                MAX(t.transaction_date) as last_active_date
            FROM transactions t
            WHERE t.vendor IS NOT NULL AND t.vendor != ''
        """
        params: list[str] = []
        if search:
            query += " AND LOWER(t.vendor) LIKE ?"
            params.append(f"%{search.lower()}%")

        query += " GROUP BY t.vendor ORDER BY t.vendor COLLATE NOCASE ASC"

        rows = self._execute_query(query, tuple(params))
        return [VendorDirectoryRow(**dict(row)) for row in rows]