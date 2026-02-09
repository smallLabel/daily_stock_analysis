# -*- coding: utf-8 -*-
"""
===================================
Repository 模块
===================================

导出所有 Repository 类
"""

from .base_repo import BaseRepository
from .stock_repo import (
    StockDailyRepository,
    WatchlistRepository,
    StockBasicRepository,
)
from .analysis_repo import AnalysisHistoryRepository
from .sector_repo import (
    SectorInfoRepository,
    SectorComponentRepository,
)

__all__ = [
    'BaseRepository',
    'StockDailyRepository',
    'WatchlistRepository',
    'StockBasicRepository',
    'AnalysisHistoryRepository',
    'SectorInfoRepository',
    'SectorComponentRepository',
]

# 便捷函数
def get_stock_daily_repo() -> StockDailyRepository:
    """获取股票日线数据 Repository"""
    return StockDailyRepository()


def get_watchlist_repo() -> WatchlistRepository:
    """获取自选股 Repository"""
    return WatchlistRepository()


def get_stock_basic_repo() -> StockBasicRepository:
    """获取股票基本信息 Repository"""
    return StockBasicRepository()


def get_analysis_repo() -> AnalysisHistoryRepository:
    """获取分析历史 Repository"""
    return AnalysisHistoryRepository()


def get_sector_info_repo() -> SectorInfoRepository:
    """获取板块信息 Repository"""
    return SectorInfoRepository()


def get_sector_component_repo() -> SectorComponentRepository:
    """获取板块成分股 Repository"""
    return SectorComponentRepository()
