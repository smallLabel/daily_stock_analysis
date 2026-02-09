# -*- coding: utf-8 -*-
"""
===================================
缓存管理器抽象
===================================

定义缓存接口
"""

import hashlib
import json
import logging
from abc import ABC, abstractmethod
from typing import Optional, Any, Dict

logger = logging.getLogger(__name__)


class CacheBackend(ABC):
    """缓存后端抽象基类"""

    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        pass

    @abstractmethod
    def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        """设置缓存"""
        pass

    @abstractmethod
    def delete(self, key: str) -> bool:
        """删除缓存"""
        pass

    @abstractmethod
    def clear(self) -> bool:
        """清空缓存"""
        pass

    @abstractmethod
    def exists(self, key: str) -> bool:
        """检查键是否存在"""
        pass


class MemoryCache(CacheBackend):
    """
    内存缓存实现

    简单内存字典缓存，适用于单进程应用
    """

    def __init__(self, max_size: int = 1000):
        """
        初始化内存缓存

        Args:
            max_size: 最大缓存条目数
        """
        self._cache: Dict[str, Dict] = {}
        self._max_size = max_size
        self._default_ttl = 300

    def _generate_key(self, key: str) -> str:
        """生成缓存键"""
        return key

    def _is_expired(self, entry: Dict) -> bool:
        """检查是否过期"""
        import time
        return time.time() > entry.get('expire_at', 0)

    def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        entry = self._cache.get(key)
        if entry is None:
            return None

        if self._is_expired(entry):
            del self._cache[key]
            return None

        return entry.get('value')

    def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        """设置缓存"""
        import time

        if len(self._cache) >= self._max_size:
            self._evict_oldest()

        self._cache[key] = {
            'value': value,
            'expire_at': time.time() + ttl,
            'created_at': time.time(),
        }
        return True

    def delete(self, key: str) -> bool:
        """删除缓存"""
        if key in self._cache:
            del self._cache[key]
            return True
        return False

    def clear(self) -> bool:
        """清空缓存"""
        self._cache.clear()
        return True

    def exists(self, key: str) -> bool:
        """检查键是否存在"""
        entry = self._cache.get(key)
        if entry is None:
            return False
        if self._is_expired(entry):
            del self._cache[key]
            return False
        return True

    def _evict_oldest(self) -> None:
        """淘汰最旧的条目"""
        if not self._cache:
            return

        oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k].get('created_at', 0))
        del self._cache[oldest_key]

    def get_many(self, keys: list) -> Dict[str, Any]:
        """批量获取"""
        result = {}
        for key in keys:
            value = self.get(key)
            if value is not None:
                result[key] = value
        return result

    def set_many(self, mapping: Dict[str, Any], ttl: int = 300) -> bool:
        """批量设置"""
        for key, value in mapping.items():
            self.set(key, value, ttl)
        return True


class NullCache(CacheBackend):
    """
    空缓存实现

    所有操作都是空操作，适用于禁用缓存的场景
    """

    def get(self, key: str) -> Optional[Any]:
        return None

    def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        return True

    def delete(self, key: str) -> bool:
        return True

    def clear(self) -> bool:
        return True

    def exists(self, key: str) -> bool:
        return False


def get_cache_backend(backend_type: str = 'memory', **kwargs) -> CacheBackend:
    """
    获取缓存后端

    Args:
        backend_type: 后端类型 ('memory', 'null')
        **kwargs: 其他参数

    Returns:
        缓存后端实例
    """
    if backend_type == 'memory':
        return MemoryCache(**kwargs)
    elif backend_type == 'null':
        return NullCache()
    else:
        logger.warning(f"未知的缓存后端类型: {backend_type}，使用 MemoryCache")
        return MemoryCache()
