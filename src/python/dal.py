import sqlite3
import statistics

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
    active_vendors_count: int
    median_spend_per_vendor: float

class MedianSpendPoint(BaseModel):
    period: str
    median_spend: float
    vendor_count: int

class MedianSpendTrend(BaseModel):
    granularity: str  # "month", "quarter", or "year"
    points: list[MedianSpendPoint]

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
        """Computes vendor-centric KPI metrics: active vendors count and median spend per vendor."""
        # Query total spend for each distinct vendor that has transactions
        query = """
            SELECT SUM(amount) as total_spend
            FROM transactions
            WHERE vendor IS NOT NULL AND vendor != ''
            GROUP BY vendor
        """
        rows = self._execute_query(query)
        active_count = len(rows)
        if active_count > 0:
            spends = [float(r["total_spend"]) for r in rows]
            median_val = float(statistics.median(spends))
        else:
            median_val = 0.0

        return ExecutiveKPIs(
            active_vendors_count=active_count,
            median_spend_per_vendor=median_val,
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

    def get_median_spend_trend(self) -> MedianSpendTrend:
        """Calculates historical median spend per vendor over time, adapting granularity.
        
        Granularity logic:
        - If total span across active periods is <= 24 months, group by month (YYYY-MM).
        - If > 24 months and <= 16 quarters, group by quarter (YYYY-Q1..Q4).
        - Otherwise, group by year (YYYY).
        """
        # First query distinct months to inspect temporal span
        month_query = """
            SELECT DISTINCT SUBSTR(transaction_date, 1, 7) as ym
            FROM transactions
            WHERE transaction_date IS NOT NULL AND transaction_date != ''
              AND vendor IS NOT NULL AND vendor != ''
            ORDER BY ym ASC
        """
        month_rows = self._execute_query(month_query)
        total_months = len(month_rows)

        if total_months == 0:
            return MedianSpendTrend(granularity="month", points=[])

        # Decide granularity
        if total_months <= 24:
            granularity = "month"
            # period expression: SUBSTR(transaction_date, 1, 7)
            period_expr = "SUBSTR(transaction_date, 1, 7)"
        else:
            # Check number of quarters
            quarters_count = len({
                f"{r['ym'][:4]}-Q{(int(r['ym'][5:7]) - 1) // 3 + 1}"
                for r in month_rows
            })
            if quarters_count <= 16:
                granularity = "quarter"
                # SQLite quarter calculation:
                # YYYY || '-Q' || ((CAST(SUBSTR(transaction_date, 6, 2) AS INTEGER) - 1) / 3 + 1)
                period_expr = "SUBSTR(transaction_date, 1, 4) || '-Q' || ((CAST(SUBSTR(transaction_date, 6, 2) AS INTEGER) - 1) / 3 + 1)"
            else:
                granularity = "year"
                period_expr = "SUBSTR(transaction_date, 1, 4)"

        query = f"""
            SELECT 
                {period_expr} as period,
                vendor,
                SUM(amount) as vendor_spend
            FROM transactions
            WHERE transaction_date IS NOT NULL AND transaction_date != ''
              AND vendor IS NOT NULL AND vendor != ''
            GROUP BY period, vendor
            ORDER BY period ASC
        """
        rows = self._execute_query(query)

        # Group vendor_spends by period and calculate median
        from collections import defaultdict
        period_spends: dict[str, list[float]] = defaultdict(list)
        for r in rows:
            period_spends[r["period"]].append(float(r["vendor_spend"]))

        points: list[MedianSpendPoint] = []
        for period in sorted(period_spends.keys()):
            spends = period_spends[period]
            med = float(statistics.median(spends))
            points.append(
                MedianSpendPoint(
                    period=period,
                    median_spend=med,
                    vendor_count=len(spends),
                )
            )

        return MedianSpendTrend(granularity=granularity, points=points)