# -*- coding: utf-8 -*-
"""
===================================
A股自选股智能分析系统 - 存储层 (兼容层)
===================================

职责：
1. 提供向后兼容的数据库接口
2. 委托给新的 Repository 层处理实际逻辑
3. 保持原有 API 不变

注意：新增代码请直接使用 Repository 层
"""

import atexit
import json
import logging
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    数据库管理器 - 兼容层

    内部委托给新的 Repository 层
    保持原有 API 不变
    """

    _instance: Optional['DatabaseManager'] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, db_url: Optional[str] = None):
        if self._initialized:
            return

        from data_provider.database import get_connection_manager
        from data_provider.models import (
            StockDaily, WatchlistStock, StockBasicInfo,
            AnalysisHistory, SectorInfo, SectorComponent
        )
        from data_provider.database.session import Base

        conn_manager = get_connection_manager()

        self._engine = conn_manager.engine
        self._SessionLocal = sessionmaker(
            bind=self._engine,
            autocommit=False,
            autoflush=False,
        )

        Base.metadata.create_all(self._engine)

        self._initialized = True
        logger.info(f"数据库管理器初始化完成")

        atexit.register(self._cleanup_engine, self._engine)

    def _cleanup_engine(self, engine) -> None:
        """清理数据库引擎"""
        try:
            if engine is not None:
                engine.dispose()
                logger.debug("数据库引擎已清理")
        except Exception as e:
            logger.warning(f"清理数据库引擎时出错: {e}")

    @classmethod
    def get_instance(cls) -> 'DatabaseManager':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        if cls._instance is not None:
            cls._instance._engine.dispose()
            cls._instance = None

    def get_session(self) -> Session:
        """获取数据库 Session"""
        return self._SessionLocal()

    def has_today_data(self, code: str, target_date: Optional[date] = None) -> bool:
        """检查是否已有指定日期的数据"""
        from data_provider.repository import get_stock_daily_repo
        repo = get_stock_daily_repo()
        return repo.has_today_data(code, target_date)

    def get_latest_data(self, code: str, days: int = 2) -> List:
        """获取最近 N 天的数据"""
        from data_provider.repository import get_stock_daily_repo
        repo = get_stock_daily_repo()
        return repo.get_latest(code, days)

    def get_data_range(self, code: str, start_date: date, end_date: date) -> List:
        """获取指定日期范围的数据"""
        from data_provider.repository import get_stock_daily_repo
        repo = get_stock_daily_repo()
        return repo.get_data_range(code, start_date, end_date)

    def save_daily_data(self, df: pd.DataFrame, code: str, data_source: str = "Unknown") -> int:
        """保存日线数据"""
        from data_provider.repository import get_stock_daily_repo
        repo = get_stock_daily_repo()
        return repo.save_daily_data(df, code, data_source)

    def get_analysis_context(self, code: str, target_date: Optional[date] = None) -> Optional[Dict[str, Any]]:
        """获取分析上下文"""
        from data_provider.repository import get_stock_daily_repo
        repo = get_stock_daily_repo()
        return repo.get_analysis_context(code, target_date)

    def save_sector_info(self, sector_data: Dict[str, Any]) -> bool:
        """保存板块信息"""
        from data_provider.repository import get_sector_info_repo
        repo = get_sector_info_repo()
        return repo.save(sector_data)

    def save_sector_components(self, sector_code: str, components: List[Dict[str, Any]]) -> bool:
        """保存板块成分股"""
        from data_provider.repository import get_sector_component_repo
        repo = get_sector_component_repo()
        return repo.save_batch(sector_code, components)

    def get_sector_info(self, sector_code: str):
        """获取板块信息"""
        from data_provider.repository import get_sector_info_repo
        repo = get_sector_info_repo()
        return repo.get_by_code(sector_code)

    def get_all_sectors(self) -> List:
        """获取所有板块"""
        from data_provider.repository import get_sector_info_repo
        repo = get_sector_info_repo()
        return repo.get_all()

    def get_sector_components(self, sector_code: str) -> List:
        """获取板块成分股"""
        from data_provider.repository import get_sector_component_repo
        repo = get_sector_component_repo()
        return repo.get_by_sector(sector_code)

    def get_sector_stock_codes(self, sector_code: str) -> List[str]:
        """获取板块成分股代码"""
        from data_provider.repository import get_sector_component_repo
        repo = get_sector_component_repo()
        return repo.get_codes(sector_code)

    def is_sector_data_needs_update(self, sector_code: str) -> bool:
        """检查板块数据是否需要更新"""
        from data_provider.repository import get_sector_info_repo
        repo = get_sector_info_repo()
        return repo.needs_update(sector_code)

    def get_sectors_needing_update(self) -> List[str]:
        """获取需要更新的板块"""
        from data_provider.repository import get_sector_info_repo
        repo = get_sector_info_repo()
        return repo.get_needing_update()

    def save_watchlist_stock(self, stock_code: str, stock_name: str = "") -> bool:
        """保存自选股"""
        from data_provider.repository import get_watchlist_repo
        repo = get_watchlist_repo()
        return repo.add(stock_code, stock_name)

    def save_watchlist_stocks(self, stock_codes: List[str]) -> bool:
        """批量保存自选股"""
        from data_provider.repository import get_watchlist_repo
        repo = get_watchlist_repo()
        return repo.add_batch(stock_codes)

    def get_watchlist_stocks(self) -> List:
        """获取所有自选股"""
        from data_provider.repository import get_watchlist_repo
        repo = get_watchlist_repo()
        return repo.get_all()

    def get_watchlist_stock_codes(self) -> List[str]:
        """获取自选股代码"""
        from data_provider.repository import get_watchlist_repo
        repo = get_watchlist_repo()
        return repo.get_codes()

    def get_watchlist_stock_names(self) -> Dict[str, str]:
        """获取自选股名称映射"""
        from data_provider.repository import get_watchlist_repo
        repo = get_watchlist_repo()
        return repo.get_names_dict()

    def delete_watchlist_stock(self, stock_code: str) -> bool:
        """删除自选股"""
        from data_provider.repository import get_watchlist_repo
        repo = get_watchlist_repo()
        return repo.remove(stock_code)

    def clear_watchlist(self) -> bool:
        """清空自选股"""
        from data_provider.repository import get_watchlist_repo
        repo = get_watchlist_repo()
        return repo.clear()

    def update_watchlist_stock_name(self, stock_code: str, stock_name: str) -> bool:
        """更新自选股名称"""
        from data_provider.repository import get_watchlist_repo
        repo = get_watchlist_repo()
        success = repo.remove(stock_code)
        if success:
            return repo.add(stock_code, stock_name)
        return False

    def save_analysis_history(self, analysis_data: Dict[str, Any]) -> bool:
        """保存分析历史"""
        from data_provider.repository import get_analysis_repo
        repo = get_analysis_repo()
        return repo.save_analysis(analysis_data)

    def get_analysis_history(self, limit: int = 50, offset: int = 0, stock_code: Optional[str] = None) -> List:
        """获取分析历史"""
        from data_provider.repository import get_analysis_repo
        repo = get_analysis_repo()
        return repo.get_history(limit, offset, stock_code)

    def get_analysis_history_count(self, stock_code: Optional[str] = None) -> int:
        """获取分析历史总数"""
        from data_provider.repository import get_analysis_repo
        repo = get_analysis_repo()
        return repo.get_count(stock_code)

    def delete_analysis_history(self, history_id: int) -> bool:
        """删除分析历史"""
        from data_provider.repository import get_analysis_repo
        repo = get_analysis_repo()
        return repo.delete(history_id)

    def clear_database(self) -> bool:
        """清空所有表"""
        from data_provider.database import get_connection_manager
        conn_manager = get_connection_manager()

        tables = [
            'analysis_history',
            'watchlist_stocks',
            'sector_components',
            'sector_info',
            'stock_daily',
            'stock_basic_info',
        ]

        try:
            with conn_manager.get_connection() as conn:
                for table in tables:
                    conn.execute(f"DELETE FROM {table}")
                conn.commit()
            logger.info("所有数据库表已清空")
            return True
        except Exception as e:
            logger.error(f"清空数据库失败: {e}")
            return False


def get_db() -> DatabaseManager:
    """获取数据库管理器实例的便捷函数"""
    return DatabaseManager.get_instance()


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    db = get_db()
    print("=== 数据库测试 ===")
    print(f"数据库初始化成功")

    has_data = db.has_today_data('600519')
    print(f"茅台今日是否有数据: {has_data}")
