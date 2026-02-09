# -*- coding: utf-8 -*-
"""
===================================
数据库连接管理模块
===================================

职责：
1. 管理 SQLite 数据库连接
2. 提供连接上下文管理器
3. 实现连接池管理
"""

import os
import logging
import atexit
from contextlib import contextmanager
from typing import Optional

logger = logging.getLogger(__name__)


class DatabaseConfig:
    """数据库配置"""

    def __init__(
        self,
        db_path: Optional[str] = None,
        echo: bool = False,
        pool_size: int = 5,
        max_overflow: int = 10
    ):
        self.db_path = db_path
        self.echo = echo
        self.pool_size = pool_size
        self.max_overflow = max_overflow

    @classmethod
    def default(cls) -> 'DatabaseConfig':
        """创建默认配置"""
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        db_path = os.path.join(project_root, 'data', 'stock_analysis.db')
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        return cls(db_path=db_path)


class ConnectionManager:
    """
    数据库连接管理器

    职责：
    1. 管理 SQLite 数据库连接
    2. 提供线程安全的连接上下文
    3. 处理连接生命周期

    设计要点：
    - 使用上下文管理器确保连接正确关闭
    - 支持事务自动回滚
    - 单例模式确保全局唯一连接池
    """

    _instance: Optional['ConnectionManager'] = None
    _initialized: bool = False

    def __new__(cls, config: Optional[DatabaseConfig] = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, config: Optional[DatabaseConfig] = None):
        if self._initialized:
            return

        if config is None:
            config = DatabaseConfig.default()

        self._config = config
        self._engine = None
        self._setup_engine()

        self._initialized = True
        logger.info(f"ConnectionManager 初始化完成: {self._config.db_path}")

        atexit.register(self._cleanup)

    def _setup_engine(self) -> None:
        """设置 SQLAlchemy 引擎"""
        try:
            from sqlalchemy import create_engine

            db_url = f"sqlite:///{self._config.db_path}"
            self._engine = create_engine(
                db_url,
                echo=self._config.echo,
                pool_pre_ping=True,
                pool_recycle=3600,
            )
            logger.info(f"数据库引擎创建成功: {db_url}")

        except ImportError as e:
            logger.error(f"SQLAlchemy 未安装: {e}")
            raise

    def _cleanup(self) -> None:
        """清理资源（atexit 钩子）"""
        try:
            if self._engine:
                self._engine.dispose()
                logger.debug("数据库引擎已清理")
        except Exception as e:
            logger.warning(f"清理数据库引擎时出错: {e}")

    @property
    def engine(self):
        """获取数据库引擎"""
        return self._engine

    @property
    def db_path(self) -> str:
        """获取数据库路径"""
        return self._config.db_path

    @classmethod
    def reset_instance(cls) -> None:
        """重置单例（用于测试）"""
        if cls._instance is not None:
            cls._instance._cleanup()
            cls._instance = None
            cls._initialized = False

    @contextmanager
    def get_connection(self):
        """
        获取数据库连接的上下文管理器

        用法：
            with db.get_connection() as conn:
                cursor = conn.cursor()
                # 执行操作...
            # 自动提交或回滚
        """
        import sqlite3
        conn = None
        try:
            conn = sqlite3.connect(self._config.db_path)
            yield conn
            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"数据库事务失败: {e}")
            raise
        finally:
            if conn:
                conn.close()

    @contextmanager
    def get_cursor(self):
        """
        获取数据库游标的上下文管理器

        用法：
            with db.get_cursor() as cursor:
                cursor.execute("SELECT * FROM stocks")
        """
        with self.get_connection() as conn:
            yield conn.cursor()


def get_connection_manager() -> ConnectionManager:
    """获取连接管理器单例"""
    return ConnectionManager()


def reset_connection_manager() -> None:
    """重置连接管理器"""
    ConnectionManager.reset_instance()
