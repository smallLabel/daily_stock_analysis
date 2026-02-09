# -*- coding: utf-8 -*-
"""
===================================
数据库模块初始化
===================================

统一导出：
- ConnectionManager: 数据库连接管理
- SessionManager: Session 管理
- DatabaseManager: 完整的数据库管理器（兼容旧接口）
"""

from .connection import (
    ConnectionManager,
    DatabaseConfig,
    get_connection_manager,
    reset_connection_manager,
)
from .session import (
    SessionManager,
    Base,
    get_session_manager,
    get_session,
    get_scoped_session,
    remove_scoped_session,
)

__all__ = [
    # 连接管理
    'ConnectionManager',
    'DatabaseConfig',
    'get_connection_manager',
    'reset_connection_manager',
    # Session 管理
    'SessionManager',
    'Base',
    'get_session_manager',
    'get_session',
    'get_scoped_session',
    'remove_scoped_session',
]
