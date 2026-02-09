# -*- coding: utf-8 -*-
"""
===================================
分析历史 Repository
===================================

提供分析历史相关的数据库操作
"""

import json
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

from sqlalchemy import select, and_, desc, func
from sqlalchemy.orm import Session

from .base_repo import BaseRepository
from ..models.analysis import AnalysisHistory

logger = logging.getLogger(__name__)


class AnalysisHistoryRepository(BaseRepository[AnalysisHistory]):
    """
    分析历史 Repository

    提供分析历史记录的 CRUD 操作
    """

    def __init__(self):
        super().__init__(AnalysisHistory)

    def get_history(
        self,
        limit: int = 50,
        offset: int = 0,
        stock_code: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """获取分析历史（返回字典列表，避免 Session 问题）"""
        with self._session_manager.get_session() as session:
            query = session.query(AnalysisHistory)

            if stock_code:
                query = query.filter(AnalysisHistory.stock_code == stock_code)

            results = query.order_by(
                desc(AnalysisHistory.analyzed_at)
            ).limit(limit).offset(offset).all()

            return [self._to_dict(h) for h in results]

    def _to_dict(self, obj: AnalysisHistory) -> Dict[str, Any]:
        """将 ORM 对象转换为字典"""
        return {
            'id': obj.id,
            'stock_code': obj.stock_code,
            'stock_name': obj.stock_name,
            'current_price': obj.current_price,
            'buy_point': obj.buy_point,
            'secondary_buy_point': obj.secondary_buy_point,
            'stop_loss': obj.stop_loss,
            'target_price': obj.target_price,
            'signal_type': obj.signal_type,
            'sentiment_score': obj.sentiment_score,
            'score': obj.score,
            'confidence_level': obj.confidence_level,
            'report_type': obj.report_type,
            'core_conclusion': obj.core_conclusion,
            'result_json': obj.result_json,
            'analyzed_at': obj.analyzed_at,
            'updated_at': obj.updated_at,
        }

    def get_count(self, stock_code: Optional[str] = None) -> int:
        """获取总数"""
        with self._session_manager.get_session() as session:
            query = session.query(func.count(AnalysisHistory.id))
            if stock_code:
                query = query.filter(AnalysisHistory.stock_code == stock_code)
            return query.scalar() or 0

    def get_latest(self, code: str) -> Optional[Dict[str, Any]]:
        """获取最新分析记录"""
        with self._session_manager.get_session() as session:
            result = session.query(AnalysisHistory).filter(
                AnalysisHistory.stock_code == code
            ).order_by(
                desc(AnalysisHistory.analyzed_at)
            ).first()
            return self._to_dict(result) if result else None

    def save_analysis(self, analysis_data: Dict[str, Any]) -> bool:
        """保存分析结果"""
        try:
            stock_code = analysis_data.get('code', '')
            dashboard = analysis_data.get('dashboard', {})
            price_position = dashboard.get('data_perspective', {})
            core_conclusion = dashboard.get('core_conclusion', {})
            battle_plan = dashboard.get('battle_plan', {})

            sniper_points = battle_plan.get('sniper_points', {})
            secondary_buy = 0.0
            if sniper_points:
                import re
                match = re.search(r'(\d+\.?\d*)', sniper_points.get('secondary_buy', ''))
                if match:
                    secondary_buy = float(match.group(1))

            ma20 = price_position.get('ma20', 0.0)
            stop_loss_price = ma20 * 0.97 if ma20 > 0 else price_position.get('support_level', 0.0) * 0.95

            update_data = {
                'stock_name': analysis_data.get('name', ''),
                'current_price': price_position.get('current_price', 0.0),
                'buy_point': price_position.get('support_level', 0.0),
                'secondary_buy_point': secondary_buy,
                'stop_loss': stop_loss_price,
                'target_price': price_position.get('resistance_level', 0.0),
                'signal_type': core_conclusion.get('signal_type', '持有'),
                'sentiment_score': analysis_data.get('sentiment_score', 0),
                'score': analysis_data.get('sentiment_score', 0),
                'confidence_level': analysis_data.get('confidence_level', '中'),
                'report_type': analysis_data.get('report_type', 'simple'),
                'core_conclusion': core_conclusion.get('one_sentence', ''),
                'result_json': json.dumps(analysis_data, ensure_ascii=False),
                'analyzed_at': datetime.now(),
                'updated_at': datetime.now()
            }

            with self._session_manager.get_session() as session:
                existing = session.query(AnalysisHistory).filter(
                    AnalysisHistory.stock_code == stock_code
                ).order_by(
                    desc(AnalysisHistory.analyzed_at)
                ).first()

                if existing:
                    for key, value in update_data.items():
                        if hasattr(existing, key):
                            setattr(existing, key, value)
                    logger.info(f"更新分析历史成功: {stock_code}")
                else:
                    history = AnalysisHistory(stock_code=stock_code, **update_data)
                    session.add(history)
                    logger.info(f"新增分析历史成功: {stock_code}")

            return True

        except Exception as e:
            logger.error(f"保存分析历史失败: {e}")
            return False

    def delete(self, history_id: int) -> bool:
        """删除记录"""
        try:
            with self._session_manager.get_session() as session:
                session.query(AnalysisHistory).filter(
                    AnalysisHistory.id == history_id
                ).delete()
                return True
        except Exception as e:
            logger.error(f"删除分析历史失败: {e}")
            return False

    def clear_all(self) -> bool:
        """清空所有记录"""
        try:
            with self._session_manager.get_session() as session:
                session.query(AnalysisHistory).delete()
                return True
        except Exception as e:
            logger.error(f"清空分析历史失败: {e}")
            return False
