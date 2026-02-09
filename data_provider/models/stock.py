# -*- coding: utf-8 -*-
"""
===================================
股票数据模型
===================================

包含：StockDaily, WatchlistStock
"""

from datetime import datetime, date
from typing import Any, Dict

from sqlalchemy import (
    Column, String, Float, Date, DateTime, Integer,
    Index, UniqueConstraint,
)
from sqlalchemy.orm import declarative_base

from ..database.session import Base

Base = declarative_base()


class StockDaily(Base):
    """
    股票日线数据模型

    存储每日行情数据和计算的技术指标
    支持多股票、多日期的唯一约束
    """
    __tablename__ = 'stock_daily'

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(10), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    pre_close = Column(Float)
    change_amount = Column(Float)
    pct_chg = Column(Float)
    amplitude = Column(Float)
    volume = Column(Float)
    amount = Column(Float)
    volume_ratio = Column(Float)
    turnover_rate = Column(Float)
    ma5 = Column(Float)
    ma10 = Column(Float)
    ma20 = Column(Float)
    pe = Column(Float)
    pb = Column(Float)
    total_mv = Column(Float)
    circ_mv = Column(Float)
    change_60d = Column(Float)
    change_ytd = Column(Float)
    data_source = Column(String(50))
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        UniqueConstraint('code', 'date', name='uix_stock_daily_code_date'),
        Index('ix_stock_daily_code_date', 'code', 'date'),
    )

    def __repr__(self) -> str:
        return f"<StockDaily(code={self.code}, date={self.date}, close={self.close})>"

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'code': self.code,
            'date': self.date.isoformat() if self.date else None,
            'open': self.open,
            'high': self.high,
            'low': self.low,
            'close': self.close,
            'pre_close': self.pre_close,
            'change_amount': self.change_amount,
            'pct_chg': self.pct_chg,
            'amplitude': self.amplitude,
            'volume': self.volume,
            'amount': self.amount,
            'volume_ratio': self.volume_ratio,
            'turnover_rate': self.turnover_rate,
            'ma5': self.ma5,
            'ma10': self.ma10,
            'ma20': self.ma20,
            'pe': self.pe,
            'pb': self.pb,
            'total_mv': self.total_mv,
            'circ_mv': self.circ_mv,
            'change_60d': self.change_60d,
            'change_ytd': self.change_ytd,
            'data_source': self.data_source,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class WatchlistStock(Base):
    """
    自选股模型

    存储用户关注的股票列表
    """
    __tablename__ = 'watchlist_stocks'

    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_code = Column(String(10), nullable=False, unique=True, index=True)
    stock_name = Column(String(50), nullable=False, default='')
    display_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    def __repr__(self) -> str:
        return f"<WatchlistStock(code={self.stock_code}, name={self.stock_name})>"

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'stock_code': self.stock_code,
            'stock_name': self.stock_name or self.stock_code,
            'display_order': self.display_order,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class StockBasicInfo(Base):
    """
    股票基本信息模型

    存储股票代码和名称的简单映射
    """
    __tablename__ = 'stock_basic_info'

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(10), nullable=False, unique=True, index=True)
    name = Column(String(50))
    price = Column(Float)
    change_pct = Column(Float)
    change_amount = Column(Float)
    amplitude = Column(Float)
    volume = Column(Float)
    amount = Column(Float)
    volume_ratio = Column(Float)
    turnover_rate = Column(Float)
    pe = Column(Float)
    pb = Column(Float)
    total_mv = Column(Float)
    circ_mv = Column(Float)
    change_60d = Column(Float)
    change_ytd = Column(Float)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    def __repr__(self) -> str:
        return f"<StockBasicInfo(code={self.code}, name={self.name})>"

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'code': self.code,
            'name': self.name,
            'price': self.price,
            'change_pct': self.change_pct,
            'change_amount': self.change_amount,
            'amplitude': self.amplitude,
            'volume': self.volume,
            'amount': self.amount,
            'volume_ratio': self.volume_ratio,
            'turnover_rate': self.turnover_rate,
            'pe': self.pe,
            'pb': self.pb,
            'total_mv': self.total_mv,
            'circ_mv': self.circ_mv,
            'change_60d': self.change_60d,
            'change_ytd': self.change_ytd,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
