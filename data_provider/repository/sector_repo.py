# -*- coding: utf-8 -*-
"""
===================================
板块 Repository
===================================

提供板块相关的数据库操作
"""

import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from .base_repo import BaseRepository
from ..models.sector import SectorInfo, SectorComponent

logger = logging.getLogger(__name__)


class SectorInfoRepository(BaseRepository[SectorInfo]):
    """
    板块信息 Repository
    """

    def __init__(self):
        super().__init__(SectorInfo)

    def get_all(self) -> List[SectorInfo]:
        """获取所有板块（按评分排序）"""
        with self._session_manager.get_session() as session:
            return session.query(SectorInfo).order_by(
                SectorInfo.potential_score.desc()
            ).all()

    def get_by_code(self, code: str) -> Optional[SectorInfo]:
        """根据代码获取板块"""
        with self._session_manager.get_session() as session:
            return session.query(SectorInfo).filter(
                SectorInfo.code == code
            ).first()

    def save(self, sector_data: Dict[str, Any]) -> bool:
        """保存板块信息"""
        try:
            with self._session_manager.get_session() as session:
                existing = session.query(SectorInfo).filter(
                    SectorInfo.code == sector_data.get('code')
                ).first()

                if existing:
                    existing.name = sector_data.get('name', existing.name)
                    existing.change_pct = sector_data.get('change_pct', existing.change_pct)
                    existing.stock_count = sector_data.get('stock_count', existing.stock_count)
                    existing.potential_score = sector_data.get('potential_score', existing.potential_score)
                    existing.updated_at = datetime.now()
                else:
                    sector = SectorInfo(
                        name=sector_data.get('name', ''),
                        code=sector_data.get('code', ''),
                        change_pct=sector_data.get('change_pct', 0.0),
                        stock_count=sector_data.get('stock_count', 0),
                        potential_score=sector_data.get('potential_score', 0.0)
                    )
                    session.add(sector)

                return True
        except Exception as e:
            logger.error(f"保存板块信息失败: {e}")
            return False

    def needs_update(self, code: str, days_threshold: int = 30) -> bool:
        """检查是否需要更新"""
        sector = self.get_by_code(code)
        if not sector:
            return True

        update_diff = datetime.now() - sector.updated_at.replace(tzinfo=None)
        return update_diff.days >= days_threshold

    def get_needing_update(self, days_threshold: int = 30) -> List[str]:
        """获取需要更新的板块代码"""
        sectors = self.get_all()
        return [s.code for s in sectors if self.needs_update(s.code, days_threshold)]


class SectorComponentRepository(BaseRepository[SectorComponent]):
    """
    板块成分股 Repository
    """

    def __init__(self):
        super().__init__(SectorComponent)

    def get_by_sector(self, sector_code: str) -> List[SectorComponent]:
        """获取板块成分股"""
        with self._session_manager.get_session() as session:
            return session.query(SectorComponent).filter(
                SectorComponent.sector_code == sector_code
            ).all()

    def get_codes(self, sector_code: str) -> List[str]:
        """获取成分股代码列表"""
        components = self.get_by_sector(sector_code)
        return [c.stock_code for c in components]

    def save_batch(self, sector_code: str, components: List[Dict[str, Any]]) -> bool:
        """批量保存成分股"""
        try:
            with self._session_manager.get_session() as session:
                session.query(SectorComponent).filter(
                    SectorComponent.sector_code == sector_code
                ).delete()

                for comp in components:
                    component = SectorComponent(
                        sector_code=sector_code,
                        stock_code=comp.get('code', ''),
                        stock_name=comp.get('name', ''),
                        weight=comp.get('weight', 0.0)
                    )
                    session.add(component)

                return True
        except Exception as e:
            logger.error(f"保存板块成分股失败: {e}")
            return False

    def clear(self, sector_code: str) -> bool:
        """清空板块成分股"""
        try:
            with self._session_manager.get_session() as session:
                session.query(SectorComponent).filter(
                    SectorComponent.sector_code == sector_code
                ).delete()
                return True
        except Exception as e:
            logger.error(f"清空板块成分股失败: {e}")
            return False
