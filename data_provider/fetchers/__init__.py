# -*- coding: utf-8 -*-
"""
数据获取层 - 具体实现
"""

from .akshare_fetcher import AkshareFetcher
from .efinance_fetcher import EfinanceFetcher
from .tushare_fetcher import TushareFetcher

__all__ = [
    'AkshareFetcher',
    'EfinanceFetcher',
    'TushareFetcher',
]
