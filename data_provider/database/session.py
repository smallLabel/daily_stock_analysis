# -*- coding: utf-8 -*-
"""
===================================
数据库 Session 管理模块
===================================

职责：
1. 提供 SQLAlchemy Session 上下文管理
2. 管理 Session 生命周期
3. 处理事务控制
"""

import logging
from contextlib import contextmanager
from typing import Optional, Generator

from sqlalchemy.orm import sessionmaker, Session, declarative_base

from .connection import get_connection_manager

logger = logging.getLogger(__name__)

Base = declarative_base()


class SessionManager:
    """
    Session 管理器

    职责：
    1. 创建和管理 SQLAlchemy Session 工厂
    2. 提供 Session 上下文管理器
    3. 处理 Session 生命周期

    线程安全：
    - 使用 threadlocal 或 scoped_session 实现线程安全
    - 对于 Web 应用，建议使用 scoped_session
    """

    _instance: Optional['SessionManager'] = None
    _initialized: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._SessionLocal = None
        self._setup_session()

        self._initialized = True
        logger.info("SessionManager 初始化完成")

    def _setup_session(self) -> None:
        """设置 Session 工厂"""
        conn_manager = get_connection_manager()
        engine = conn_manager.engine

        if engine is None:
            logger.warning("数据库引擎未初始化，Session 工厂创建失败")
            return

        self._SessionLocal = sessionmaker(
            bind=engine,
            autocommit=False,
            autoflush=False,
        )

    def get_session_factory(self):
        """获取 Session 工厂"""
        if self._SessionLocal is None:
            self._setup_session()
        return self._SessionLocal

    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """
        获取 Session 的上下文管理器

        用法：
            with session_manager.get_session() as session:
                results = session.query(Stock).all()
                # 自动提交或回滚
        """
        if self._SessionLocal is None:
            raise RuntimeError("Session 工厂未初始化，请确保数据库已连接")

        session = self._SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Session 事务失败: {e}")
            raise
        finally:
            session.close()

    @property
    def SessionLocal(self):
        """获取 Session 工厂类"""
        return self.get_session_factory()


def get_session_manager() -> SessionManager:
    """获取 Session 管理器单例"""
    return SessionManager()


def get_session() -> Session:
    """获取 Session 的便捷函数"""
    sm = get_session_manager()
    return sm.get_session_factory()()


def get_scoped_session() -> Session:
    """
    获取 scoped session（线程安全）

    适用于多线程环境，自动管理每个线程的 Session
    """
    from sqlalchemy.orm import scoped_session

    sm = get_session_manager()
    return scoped_session(sm.get_session_factory())


def remove_scoped_session() -> None:
    """移除 scoped session（线程结束时调用）"""
    from sqlalchemy.orm import scoped_session
    scoped_session(get_session_manager().get_session_factory()).remove()
