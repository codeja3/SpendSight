import sqlite3
from typing import List
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

    def get_ledger(self, limit: int = 50, offset: int = 0) -> List[LedgerRow]:
        """Feature 1: Retrieves chronological transactions."""
        query = """
            SELECT transaction_date AS date, vendor, category, amount 
            FROM transactions 
            ORDER BY transaction_date DESC 
            LIMIT ? OFFSET ?
        """
        rows = self._execute_query(query, (limit, offset))
        return [LedgerRow(**dict(row)) for row in rows]

    def get_top_vendors(self, limit_n: int = 5) -> List[AggregateRow]:
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

    def get_bottom_vendors(self, limit_n: int = 5) -> List[AggregateRow]:
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

    def get_top_categories(self, limit_n: int = 5) -> List[AggregateRow]:
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

    def get_top_vendors_by_category(self, target_category: str, limit_n: int = 5) -> List[AggregateRow]:
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