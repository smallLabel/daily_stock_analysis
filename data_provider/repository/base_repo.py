# -*- coding: utf-8 -*-
"""
===================================
Repository 基类
===================================

提供通用的数据库操作方法
"""

import logging
from typing import TypeVar, Generic, Type, Optional, List, Any, Dict
from datetime import datetime

from sqlalchemy.orm import Session, Query

from ..database.session import get_session_manager
from ..database.connection import get_connection_manager

logger = logging.getLogger(__name__)

T = TypeVar('T')


class BaseRepository(Generic[T]):
    """
    Repository 基类

    职责：
    1. 提供通用的 CRUD 操作
    2. 管理数据库 Session
    3. 提供查询构建器

    使用示例：
        class UserRepository(BaseRepository[User]):
            pass

        user_repo = UserRepository(User)
        users = user_repo.find_all()
    """

    def __init__(self, model_class: Type[T]):
        """
        初始化 Repository

        Args:
            model_class: ORM 模型类
        """
        self._model_class = model_class
        self._session_manager = get_session_manager()
        self._connection_manager = get_connection_manager()

    @property
    def model_class(self) -> Type[T]:
        """获取模型类"""
        return self._model_class

    def _get_session(self) -> Session:
        """获取数据库 Session"""
        return self._session_manager.get_session_factory()()

    def _get_query(self, session: Session) -> Query:
        """获取基础查询"""
        return session.query(self._model_class)

    def find_by_id(self, id: int) -> Optional[T]:
        """根据 ID 查找"""
        with self._session_manager.get_session() as session:
            return session.query(self._model_class).get(id)

    def find_all(self, limit: int = 100, offset: int = 0) -> List[T]:
        """查询所有"""
        with self._session_manager.get_session() as session:
            return session.query(self._model_class).limit(limit).offset(offset).all()

    def count(self) -> int:
        """统计数量"""
        with self._session_manager.get_session() as session:
            return session.query(self._model_class).count()

    def exists_by_id(self, id: int) -> bool:
        """检查是否存在"""
        return self.find_by_id(id) is not None

    def save(self, instance: T) -> T:
        """保存实例"""
        with self._session_manager.get_session() as session:
            session.add(instance)
            session.flush()
            return instance

    def update(self, instance: T) -> T:
        """更新实例"""
        with self._session_manager.get_session() as session:
            session.add(instance)
            session.flush()
            return instance

    def delete(self, instance: T) -> bool:
        """删除实例"""
        try:
            with self._session_manager.get_session() as session:
                session.delete(instance)
                return True
        except Exception as e:
            logger.error(f"删除实例失败: {e}")
            return False

    def delete_by_id(self, id: int) -> bool:
        """根据 ID 删除"""
        instance = self.find_by_id(id)
        if instance:
            return self.delete(instance)
        return False

    def bulk_insert(self, instances: List[T], batch_size: int = 100) -> int:
        """批量插入"""
        if not instances:
            return 0

        count = 0
        with self._session_manager.get_session() as session:
            try:
                for instance in instances:
                    session.add(instance)
                    count += 1
                    if count % batch_size == 0:
                        session.flush()
                session.commit()
                logger.info(f"批量插入完成: {count} 条")
            except Exception as e:
                session.rollback()
                logger.error(f"批量插入失败: {e}")
                raise
        return count

    def execute_raw_sql(self, sql: str, params: tuple = ()) -> List[tuple]:
        """执行原生 SQL 查询"""
        with self._connection_manager.get_cursor() as cursor:
            cursor.execute(sql, params)
            return cursor.fetchall()

    def execute_raw_sql_update(self, sql: str, params: tuple = ()) -> int:
        """执行原生 SQL 更新"""
        with self._connection_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            conn.commit()
            return cursor.rowcount
