# -*- coding: utf-8 -*-
"""
===================================
分析历史数据模型
===================================

包含：AnalysisHistory
"""

import json
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import (
    Column, String, Float, DateTime, Integer,
    Index,
)
from sqlalchemy.orm import declarative_base

from ..database.session import Base

Base = declarative_base()


class AnalysisHistory(Base):
    """
    分析历史记录模型

    存储用户分析过的股票历史记录，包括分析结果摘要
    """
    __tablename__ = 'analysis_history'

    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_code = Column(String(10), nullable=False, index=True)
    stock_name = Column(String(50), nullable=False)
    current_price = Column(Float, default=0.0)
    buy_point = Column(Float, default=0.0)
    secondary_buy_point = Column(Float, default=0.0)
    stop_loss = Column(Float, default=0.0)
    target_price = Column(Float, default=0.0)
    signal_type = Column(String(20), default='持有')
    sentiment_score = Column(Integer, default=0)
    score = Column(Integer, default=0)
    confidence_level = Column(String(10), default='中')
    report_type = Column(String(10), default='simple')
    core_conclusion = Column(String(500), default='')
    result_json = Column(String, default='{}')
    analyzed_at = Column(DateTime, default=datetime.now, index=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        Index('ix_analysis_history_analyzed_at', 'analyzed_at'),
    )

    def __repr__(self) -> str:
        return f"<AnalysisHistory(code={self.stock_code}, name={self.stock_name}, analyzed_at={self.analyzed_at})>"

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'code': self.stock_code,
            'name': self.stock_name,
            'price': self.current_price,
            'buy_point': self.buy_point,
            'secondary_buy_point': self.secondary_buy_point,
            'stop_loss': self.stop_loss,
            'target_price': self.target_price,
            'signal': self.signal_type,
            'sentiment_score': self.sentiment_score,
            'score': self.score,
            'confidence_level': self.confidence_level,
            'report_type': self.report_type,
            'core_conclusion': self.core_conclusion,
            'result_json': json.loads(self.result_json) if self.result_json else {},
            'query_time': self.analyzed_at.isoformat() if self.analyzed_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def get_result_dict(self) -> Dict[str, Any]:
        """获取结果 JSON 字典"""
        if self.result_json:
            try:
                return json.loads(self.result_json)
            except json.JSONDecodeError:
                return {}
        return {}
