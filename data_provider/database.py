import sqlite3
import os
import logging
from contextlib import contextmanager

logger = logging.getLogger(__name__)

class DatabaseManager:
    _instance = None
    _db_path = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseManager, cls).__new__(cls)
            # Initialize default path
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            cls._instance._db_path = os.path.join(project_root, 'data', 'stock_analysis.db')
            os.makedirs(os.path.dirname(cls._instance._db_path), exist_ok=True)
            logger.info(f"DatabaseManager initialized with path: {cls._instance._db_path}")
        return cls._instance

    @property
    def db_path(self):
        return self._db_path

    @contextmanager
    def get_connection(self):
        """
        Context manager for SQLite connection.
        Automatically commits on success, rollbacks on exception, and closes connection.
        """
        conn = None
        try:
            conn = sqlite3.connect(self._db_path)
            yield conn
            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Database transaction failed: {e}")
            raise e
        finally:
            if conn:
                conn.close()

    @contextmanager
    def get_cursor(self):
        """
        Context manager for SQLite cursor.
        """
        with self.get_connection() as conn:
            yield conn.cursor()

def get_db_manager():
    return DatabaseManager()
