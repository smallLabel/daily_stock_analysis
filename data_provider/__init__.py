# -*- coding: utf-8 -*-
"""
数据获取层 - 统一入口
已重构为模块化结构

原始导入依然有效:
    from data_provider.base import BaseFetcher, DataFetcherManager
    from data_provider.akshare_fetcher import AkshareFetcher
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
)

# 保持向后兼容 - 导出所有类到包级别
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
]
