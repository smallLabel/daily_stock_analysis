
import logging
from datetime import datetime, date, timedelta
from typing import Optional, List, Any
import pandas as pd
from sqlalchemy import create_engine, Column, String, Float, Date, Index, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.sql import func
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from src.config import get_config

logger = logging.getLogger(__name__)

Base = declarative_base()

class StockDailyData(Base):
    __tablename__ = 'stock_daily_data'
    
    code = Column(String(20), primary_key=True)
    date = Column(Date, primary_key=True)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Float)
    amount = Column(Float)
    pct_chg = Column(Float)
    
    # Extra columns for technical indicators that might be cached
    ma5 = Column(Float, nullable=True)
    ma10 = Column(Float, nullable=True)
    ma20 = Column(Float, nullable=True)
    volume_ratio = Column(Float, nullable=True)
    
    # Ensure unique index on code and date
    __table_args__ = (
        Index('idx_code_date', 'code', 'date', unique=True),
    )

class StockDataCache:
    def __init__(self, db_url: Optional[str] = None):
        if db_url is None:
            db_url = get_config().get_db_url()
            
        self.engine = create_engine(db_url)
        self.Session = sessionmaker(bind=self.engine)
        self._init_db()

    def _init_db(self):
        try:
            Base.metadata.create_all(self.engine)
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")

    def get_latest_date(self, stock_code: str) -> Optional[date]:
        """Get the latest date for a specific stock in the cache."""
        session = self.Session()
        try:
            result = session.query(func.max(StockDailyData.date)).filter(StockDailyData.code == stock_code).scalar()
            return result
        except Exception as e:
            logger.error(f"Error getting latest date for {stock_code}: {e}")
            return None
        finally:
            session.close()

    def get_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        Query data from cache.
        Returns DataFrame with 'date' as datetime64[ns]
        """
        session = self.Session()
        try:
            s_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            e_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            
            query = session.query(StockDailyData).filter(
                StockDailyData.code == stock_code,
                StockDailyData.date >= s_date,
                StockDailyData.date <= e_date
            ).order_by(StockDailyData.date)
            
            df = pd.read_sql(query.statement, session.bind)
            
            # If empty, return empty DataFrame with expected columns to avoid errors
            if df.empty:
                return pd.DataFrame(columns=[
                    'code', 'date', 'open', 'high', 'low', 'close', 
                    'volume', 'amount', 'pct_chg', 'ma5', 'ma10', 'ma20', 'volume_ratio'
                ])
                
            # Convert date to datetime64[ns] to match pandas convention
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'])
                
            return df
        except Exception as e:
            logger.error(f"Error reading from cache for {stock_code}: {e}")
            return pd.DataFrame()
        finally:
            session.close()

    def save_data(self, df: pd.DataFrame, stock_code: str):
        """
        Save dataframe to cache with upsert handling.
        """
        if df is None or df.empty:
            return
            
        session = self.Session()
        try:
            # Prepare data
            records = []
            for _, row in df.iterrows():
                # Handling date: ensure it's a python date object
                row_date = row.get('date')
                if isinstance(row_date, (pd.Timestamp, datetime)):
                    row_date = row_date.date()
                elif isinstance(row_date, str):
                    row_date = datetime.strptime(row_date, '%Y-%m-%d').date()
                
                # Skip if no valid date
                if not row_date:
                    continue

                record = {
                    'code': stock_code,
                    'date': row_date,
                    'open': row.get('open'),
                    'high': row.get('high'),
                    'low': row.get('low'),
                    'close': row.get('close'),
                    'volume': row.get('volume'),
                    'amount': row.get('amount'),
                    'pct_chg': row.get('pct_chg'),
                    'ma5': row.get('ma5'),
                    'ma10': row.get('ma10'),
                    'ma20': row.get('ma20'),
                    'volume_ratio': row.get('volume_ratio')
                }
                
                # Filter out None/NaN values so defaults or NULLs are used? 
                # Actually SQLAlchemy handles None as NULL. 
                # We should ensure NaNs are None for float columns if needed, 
                # but valid floats are fine.
                records.append(record)
            
            if not records:
                return
            
            # Upsert logic for SQLite
            stmt = sqlite_insert(StockDailyData).values(records)
            stmt = stmt.on_conflict_do_update(
                index_elements=['code', 'date'],
                set_={col: stmt.excluded[col] for col in [
                    'open', 'high', 'low', 'close', 'volume', 'amount', 'pct_chg',
                    'ma5', 'ma10', 'ma20', 'volume_ratio'
                ]}
            )
            
            session.execute(stmt)
            session.commit()
            logger.info(f"Saved {len(records)} records for {stock_code} to cache.")
            
        except Exception as e:
            logger.error(f"Error saving to cache for {stock_code}: {e}")
            session.rollback()
        finally:
            session.close()
