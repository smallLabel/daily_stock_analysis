from typing import List, Optional
from datetime import datetime
from data_provider.repository.base_repo import BaseRepository
import logging

logger = logging.getLogger(__name__)

class StockRepository(BaseRepository):
    def __init__(self):
        super().__init__()
        self._init_table()

    def _init_table(self):
        """Initialize stock_basic_info table."""
        create_table_sql = '''
            CREATE TABLE IF NOT EXISTS stock_basic_info (
                code TEXT PRIMARY KEY,
                name TEXT,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        '''
        try:
            with self.db.get_cursor() as cursor:
                cursor.execute(create_table_sql)
        except Exception as e:
            logger.error(f"Failed to init stock table: {e}")

    def save_all(self, stocks: List[tuple]):
        """
        Save all stocks to DB.
        stocks: List of (code, name, updated_at) tuples.
        """
        try:
            with self.db.get_cursor() as cursor:
                cursor.execute("DELETE FROM stock_basic_info")
                cursor.executemany(
                    "INSERT INTO stock_basic_info (code, name, updated_at) VALUES (?, ?, ?)",
                    stocks
                )
            logger.info(f"Saved {len(stocks)} stocks to repository.")
        except Exception as e:
            logger.error(f"Failed to save stocks: {e}")
            raise e

    def get_name_by_code(self, code: str) -> Optional[str]:
        """Get stock name by code."""
        try:
            result = self.execute_scalar(
                "SELECT name FROM stock_basic_info WHERE code = ?", 
                (code,)
            )
            return result
        except Exception as e:
            logger.error(f"Error querying stock name for {code}: {e}")
            return None

    def get_count(self) -> int:
        """Get total number of stocks."""
        return self.execute_scalar("SELECT COUNT(*) FROM stock_basic_info") or 0

    def get_last_updated(self) -> Optional[datetime]:
        """Get the last update timestamp."""
        ts_str = self.execute_scalar("SELECT updated_at FROM stock_basic_info LIMIT 1")
        if ts_str:
            try:
                # Handle possible formats
                if '.' in ts_str:
                    return datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S.%f")
                return datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                pass
        return None
