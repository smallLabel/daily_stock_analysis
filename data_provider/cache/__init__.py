# -*- coding: utf-8 -*-
"""
===================================
缓存模块
===================================

导出缓存相关类
"""

from .memory import (
    CacheBackend,
    MemoryCache,
    NullCache,
    get_cache_backend,
)

__all__ = [
    'CacheBackend',
    'MemoryCache',
    'NullCache',
    'get_cache_backend',
]
