from typing import List, Dict, Any, Optional
from data_provider.database import get_db_manager, DatabaseManager

class BaseRepository:
    def __init__(self):
        self.db: DatabaseManager = get_db_manager()

    def execute_query(self, query: str, params: tuple = ()) -> List[tuple]:
        """Execute a read query and return results."""
        with self.db.get_cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchall()

    def execute_scalar(self, query: str, params: tuple = ()) -> Any:
        """Execute a query returning a single value."""
        with self.db.get_cursor() as cursor:
            cursor.execute(query, params)
            result = cursor.fetchone()
            return result[0] if result else None
