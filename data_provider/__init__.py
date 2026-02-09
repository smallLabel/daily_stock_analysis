# -*- coding: utf-8 -*-
"""
数据获取层 - 统一入口
已重构为模块化结构

原始导入依然有效:
    from data_provider.base import BaseFetcher, DataFetcherManager
    from data_provider.akshare_fetcher import AkshareFetcher

新增模块:
    from data_provider.database import get_connection_manager, get_session
    from data_provider.models import StockDaily, AnalysisHistory
    from data_provider.repository import StockDailyRepository, AnalysisHistoryRepository
"""

# 从core模块导出
from .core import (
    BaseFetcher,
    DataFetcherManager,
    DataFetchError,
    RateLimitError,
    DataSourceUnavailableError,
    STANDARD_COLUMNS,
)

# 从fetchers模块导出
from .fetchers import (
    AkshareFetcher,
    EfinanceFetcher,
    TushareFetcher,
    BaostockFetcher,
    PytdxFetcher,
    YfinanceFetcher,
)

# 从database模块导出
from .database import (
    ConnectionManager,
    DatabaseConfig,
    SessionManager,
    Base,
    get_connection_manager,
    get_session_manager,
    get_session,
)

# 从models模块导出
from .models import (
    StockDaily,
    WatchlistStock,
    StockBasicInfo,
    AnalysisHistory,
    SectorInfo,
    SectorComponent,
)

# 从repository模块导出
from .repository import (
    BaseRepository,
    StockDailyRepository,
    WatchlistRepository,
    StockBasicRepository,
    AnalysisHistoryRepository,
    SectorInfoRepository,
    SectorComponentRepository,
    get_stock_daily_repo,
    get_watchlist_repo,
    get_analysis_repo,
)

# 从cache模块导出
from .cache import (
    CacheBackend,
    MemoryCache,
    NullCache,
    get_cache_backend,
)

__all__ = [
    # 核心类
    'BaseFetcher',
    'DataFetcherManager',

    # 异常类
    'DataFetchError',
    'RateLimitError',
    'DataSourceUnavailableError',

    # 常量
    'STANDARD_COLUMNS',

    # 具体实现
    'AkshareFetcher',
    'EfinanceFetcher',
    'TushareFetcher',
    'BaostockFetcher',
    'PytdxFetcher',
    'YfinanceFetcher',

    # 数据库
    'ConnectionManager',
    'DatabaseConfig',
    'SessionManager',
    'Base',
    'get_connection_manager',
    'get_session_manager',
    'get_session',

    # 模型
    'StockDaily',
    'WatchlistStock',
    'StockBasicInfo',
    'AnalysisHistory',
    'SectorInfo',
    'SectorComponent',

    # Repository
    'BaseRepository',
    'StockDailyRepository',
    'WatchlistRepository',
    'StockBasicRepository',
    'AnalysisHistoryRepository',
    'SectorInfoRepository',
    'SectorComponentRepository',
    'get_stock_daily_repo',
    'get_watchlist_repo',
    'get_analysis_repo',

    # 缓存
    'CacheBackend',
    'MemoryCache',
    'NullCache',
    'get_cache_backend',
]
