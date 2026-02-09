# -*- coding: utf-8 -*-
"""
===================================
板块数据模型
===================================

包含：SectorInfo, SectorComponent
"""

from datetime import datetime
from typing import Any, Dict

from sqlalchemy import (
    Column, String, Float, DateTime, Integer,
    UniqueConstraint, Index,
)
from sqlalchemy.orm import declarative_base

from ..database.session import Base

Base = declarative_base()


class SectorInfo(Base):
    """
    板块信息模型

    存储板块基本信息，每月更新一次
    """
    __tablename__ = 'sector_info'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, index=True)
    code = Column(String(50), nullable=False, unique=True, index=True)
    change_pct = Column(Float, default=0.0)
    stock_count = Column(Integer, default=0)
    potential_score = Column(Float, default=0.0)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    def __repr__(self) -> str:
        return f"<SectorInfo(name={self.name}, code={self.code}, stock_count={self.stock_count})>"

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'code': self.code,
            'name': self.name,
            'change_pct': self.change_pct,
            'stock_count': self.stock_count,
            'potential_score': self.potential_score,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class SectorComponent(Base):
    """
    板块成分股模型

    存储板块与成分股的对应关系，每月更新一次
    """
    __tablename__ = 'sector_components'

    id = Column(Integer, primary_key=True, autoincrement=True)
    sector_code = Column(String(50), nullable=False, index=True)
    stock_code = Column(String(10), nullable=False, index=True)
    stock_name = Column(String(50), nullable=False)
    weight = Column(Float, default=0.0)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        UniqueConstraint('sector_code', 'stock_code', name='uix_sector_components_sector_stock'),
        Index('ix_sector_components_sector_stock', 'sector_code', 'stock_code'),
    )

    def __repr__(self) -> str:
        return f"<SectorComponent(sector={self.sector_code}, stock={self.stock_code})>"

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'sector_code': self.sector_code,
            'stock_code': self.stock_code,
            'stock_name': self.stock_name,
            'weight': self.weight,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
