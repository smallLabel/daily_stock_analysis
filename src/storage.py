# -*- coding: utf-8 -*-
"""
===================================
A股自选股智能分析系统 - 存储层
===================================

职责：
1. 管理 SQLite 数据库连接（单例模式）
2. 定义 ORM 数据模型
3. 提供数据存取接口
4. 实现智能更新逻辑（断点续传）
"""

import atexit
import json
import logging
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any
from pathlib import Path

import pandas as pd
from sqlalchemy import (
    create_engine,
    Column,
    String,
    Float,
    Date,
    DateTime,
    Text, # Added
    Integer,
    Index,
    UniqueConstraint,
    select,
    and_,
    desc,
    text, # Added for raw sql
)
from sqlalchemy.orm import (
    declarative_base,
    sessionmaker,
    Session,
)
from sqlalchemy.exc import IntegrityError

from src.config import get_config

logger = logging.getLogger(__name__)

# SQLAlchemy ORM 基类
Base = declarative_base()


# === 数据模型定义 ===

class StockDaily(Base):
    """
    股票日线数据模型
    
    存储每日行情数据和计算的技术指标
    支持多股票、多日期的唯一约束
    """
    __tablename__ = 'stock_daily'
    
    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # 股票代码（如 600519, 000001）
    code = Column(String(10), nullable=False, index=True)
    
    # 交易日期
    date = Column(Date, nullable=False, index=True)
    
    # OHLC 数据
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    
    # 成交数据
    volume = Column(Float)  # 成交量（股）
    amount = Column(Float)  # 成交额（元）
    pct_chg = Column(Float)  # 涨跌幅（%）
    
    # 技术指标
    ma5 = Column(Float)
    ma10 = Column(Float)
    ma20 = Column(Float)
    volume_ratio = Column(Float)  # 量比
    
    # 数据来源
    data_source = Column(String(50))  # 记录数据来源（如 AkshareFetcher）
    
    # 更新时间
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # 唯一约束：同一股票同一日期只能有一条数据
    __table_args__ = (
        UniqueConstraint('code', 'date', name='uix_code_date'),
        Index('ix_code_date', 'code', 'date'),
    )
    
    def __repr__(self):
        return f"<StockDaily(code={self.code}, date={self.date}, close={self.close})>"
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'code': self.code,
            'date': self.date,
            'open': self.open,
            'high': self.high,
            'low': self.low,
            'close': self.close,
            'volume': self.volume,
            'amount': self.amount,
            'pct_chg': self.pct_chg,
            'ma5': self.ma5,
            'ma10': self.ma10,
            'ma20': self.ma20,
            'volume_ratio': self.volume_ratio,
            'data_source': self.data_source,
        }


class SectorInfo(Base):
    """
    板块信息模型
    
    存储板块基本信息，每月更新一次
    """
    __tablename__ = 'sector_info'
    
    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # 板块名称
    name = Column(String(100), nullable=False, index=True)
    
    # 板块代码
    code = Column(String(50), nullable=False, unique=True, index=True)
    
    # 板块涨跌幅
    change_pct = Column(Float, default=0.0)
    
    # 板块成分股数量
    stock_count = Column(Integer, default=0)
    
    # 板块潜力评分
    potential_score = Column(Float, default=0.0)
    
    # 更新时间
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    def __repr__(self):
        return f"<SectorInfo(name={self.name}, code={self.code}, stock_count={self.stock_count})>"
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'code': self.code,
            'name': self.name,
            'change_pct': self.change_pct,
            'stock_count': self.stock_count,
            'potential_score': self.potential_score,
            'updated_at': self.updated_at
        }


class SectorComponent(Base):
    """
    板块成分股模型
    
    存储板块与成分股的对应关系，每月更新一次
    """
    __tablename__ = 'sector_components'
    
    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # 板块代码
    sector_code = Column(String(50), nullable=False, index=True)
    
    # 股票代码
    stock_code = Column(String(10), nullable=False, index=True)
    
    # 股票名称
    stock_name = Column(String(50), nullable=False)
    
    # 权重（可选）
    weight = Column(Float, default=0.0)
    
    # 更新时间
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # 唯一约束：一个板块中的一只股票只能有一条记录
    __table_args__ = (
        UniqueConstraint('sector_code', 'stock_code', name='uix_sector_stock'),
        Index('ix_sector_stock', 'sector_code', 'stock_code'),
    )
    
    def __repr__(self):
        return f"<SectorComponent(sector={self.sector_code}, stock={self.stock_code})>"
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'sector_code': self.sector_code,
            'stock_code': self.stock_code,
            'stock_name': self.stock_name,
            'weight': self.weight,
            'updated_at': self.updated_at
        }


class WatchlistStock(Base):
    """
    自选股模型
    
    存储用户关注的股票列表，支持手动输入和持久化
    """
    __tablename__ = 'watchlist_stocks'
    
    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # 股票代码（唯一）
    stock_code = Column(String(10), nullable=False, unique=True, index=True)
    
    # 股票名称（可为空，获取数据后填充）
    stock_name = Column(String(50), nullable=False, default='')
    
    # 显示顺序
    display_order = Column(Integer, default=0)
    
    # 添加时间
    created_at = Column(DateTime, default=datetime.now)
    
    # 更新时间
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    def __repr__(self):
        return f"<WatchlistStock(code={self.stock_code}, name={self.stock_name})>"
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'id': self.id,
            'stock_code': self.stock_code,
            'stock_name': self.stock_name or self.stock_code,
            'display_order': self.display_order,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class AnalysisHistory(Base):
    """
    分析历史记录模型
    
    存储用户分析过的股票历史记录，包括分析结果摘要
    """
    __tablename__ = 'analysis_history'
    
    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # 股票代码
    stock_code = Column(String(10), nullable=False, index=True)
    
    # 股票名称
    stock_name = Column(String(50), nullable=False)
    
    # 当前价格
    current_price = Column(Float, default=0.0)
    
    # 理想买入价
    buy_point = Column(Float, default=0.0)
    
    # 止损位
    stop_loss = Column(Float, default=0.0)
    
    # 目标价
    target_price = Column(Float, default=0.0)
    
    # 信号类型 (买入/卖出/持有)
    signal_type = Column(String(20), default='持有')
    
    # 情绪分数
    sentiment_score = Column(Integer, default=0)
    
    # 次选买入点
    secondary_buy_point = Column(Float, default=0.0)
    
    # 综合评分
    score = Column(Integer, default=0)
    
    # 信心等级
    confidence_level = Column(String(10), default='中')
    
    # 报告类型 (simple/full)
    report_type = Column(String(10), default='simple')
    
    # 核心结论
    core_conclusion = Column(String(500), default='')
    
    # 完整分析结果 JSON
    result_json = Column(Text, default="{}")
    
    # 分析时间
    analyzed_at = Column(DateTime, default=datetime.now, index=True)
    
    # 更新时间
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    def __repr__(self):
        return f"<AnalysisHistory(code={self.stock_code}, name={self.stock_name}, analyzed_at={self.analyzed_at})>"
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'id': self.id,
            'code': self.stock_code,
            'name': self.stock_name,
            'price': self.current_price,
            'buy_point': self.buy_point,
            'secondary_buy_point': self.secondary_buy_point,
            'stop_loss': self.stop_loss,
            'target_price': self.target_price,
            'signal': self.signal_type,
            'sentiment_score': self.sentiment_score,
            'score': self.score,
            'confidence_level': self.confidence_level,
            'report_type': self.report_type,
            'core_conclusion': self.core_conclusion,
            'result_json': json.loads(self.result_json) if self.result_json else {},
            'query_time': self.analyzed_at.isoformat() if self.analyzed_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class DatabaseManager:
    """
    数据库管理器 - 单例模式
    
    职责：
    1. 管理数据库连接池
    2. 提供 Session 上下文管理
    3. 封装数据存取操作
    """
    
    _instance: Optional['DatabaseManager'] = None
    
    def __new__(cls, *args, **kwargs):
        """单例模式实现"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, db_url: Optional[str] = None):
        """
        初始化数据库管理器
        
        Args:
            db_url: 数据库连接 URL（可选，默认从配置读取）
        """
        if self._initialized:
            return
        
        if db_url is None:
            config = get_config()
            db_url = config.get_db_url()
        
        # 创建数据库引擎
        self._engine = create_engine(
            db_url,
            echo=False,  # 设为 True 可查看 SQL 语句
            pool_pre_ping=True,  # 连接健康检查
        )
        
        # 创建 Session 工厂
        self._SessionLocal = sessionmaker(
            bind=self._engine,
            autocommit=False,
            autoflush=False,
        )
        
        # 创建所有表
        Base.metadata.create_all(self._engine)
        
        # 尝试添加 result_json 列 (Schema Migration)
        try:
            with self._engine.connect() as conn:
                conn.execute(text("ALTER TABLE analysis_history ADD COLUMN result_json TEXT DEFAULT '{}'"))
                conn.commit()
                logger.info("已添加 result_json 列到 analysis_history 表")
        except Exception:
            # 列已存在或其他错误，忽略
            pass
        
        # 尝试添加 secondary_buy_point 列 (Schema Migration)
        try:
            with self._engine.connect() as conn:
                conn.execute(text("ALTER TABLE analysis_history ADD COLUMN secondary_buy_point FLOAT DEFAULT 0.0"))
                conn.commit()
                logger.info("已添加 secondary_buy_point 列到 analysis_history 表")
        except Exception:
            # 列已存在或其他错误，忽略
            pass
        
        # 尝试添加 score 列 (Schema Migration)
        try:
            with self._engine.connect() as conn:
                conn.execute(text("ALTER TABLE analysis_history ADD COLUMN score INTEGER DEFAULT 0"))
                conn.commit()
                logger.info("已添加 score 列到 analysis_history 表")
        except Exception:
            # 列已存在或其他错误，忽略
            pass

        self._initialized = True
        logger.info(f"数据库初始化完成: {db_url}")

        # 注册退出钩子，确保程序退出时关闭数据库连接
        atexit.register(DatabaseManager._cleanup_engine, self._engine)
    
    @classmethod
    def get_instance(cls) -> 'DatabaseManager':
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    @classmethod
    def reset_instance(cls) -> None:
        """重置单例（用于测试）"""
        if cls._instance is not None:
            cls._instance._engine.dispose()
            cls._instance = None

    @classmethod
    def _cleanup_engine(cls, engine) -> None:
        """
        清理数据库引擎（atexit 钩子）

        确保程序退出时关闭所有数据库连接，避免 ResourceWarning

        Args:
            engine: SQLAlchemy 引擎对象
        """
        try:
            if engine is not None:
                engine.dispose()
                logger.debug("数据库引擎已清理")
        except Exception as e:
            logger.warning(f"清理数据库引擎时出错: {e}")
    
    def get_session(self) -> Session:
        """
        获取数据库 Session
        
        使用示例:
            with db.get_session() as session:
                # 执行查询
                session.commit()  # 如果需要
        """
        session = self._SessionLocal()
        try:
            return session
        except Exception:
            session.close()
            raise
    
    def has_today_data(self, code: str, target_date: Optional[date] = None) -> bool:
        """
        检查是否已有指定日期的数据
        
        用于断点续传逻辑：如果已有数据则跳过网络请求
        
        Args:
            code: 股票代码
            target_date: 目标日期（默认今天）
            
        Returns:
            是否存在数据
        """
        if target_date is None:
            target_date = date.today()
        
        with self.get_session() as session:
            result = session.execute(
                select(StockDaily).where(
                    and_(
                        StockDaily.code == code,
                        StockDaily.date == target_date
                    )
                )
            ).scalar_one_or_none()
            
            return result is not None
    
    def get_latest_data(
        self, 
        code: str, 
        days: int = 2
    ) -> List[StockDaily]:
        """
        获取最近 N 天的数据
        
        用于计算"相比昨日"的变化
        
        Args:
            code: 股票代码
            days: 获取天数
            
        Returns:
            StockDaily 对象列表（按日期降序）
        """
        with self.get_session() as session:
            results = session.execute(
                select(StockDaily)
                .where(StockDaily.code == code)
                .order_by(desc(StockDaily.date))
                .limit(days)
            ).scalars().all()
            
            return list(results)
    
    def get_data_range(
        self, 
        code: str, 
        start_date: date, 
        end_date: date
    ) -> List[StockDaily]:
        """
        获取指定日期范围的数据
        
        Args:
            code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            StockDaily 对象列表
        """
        with self.get_session() as session:
            results = session.execute(
                select(StockDaily)
                .where(
                    and_(
                        StockDaily.code == code,
                        StockDaily.date >= start_date,
                        StockDaily.date <= end_date
                    )
                )
                .order_by(StockDaily.date)
            ).scalars().all()
            
            return list(results)
    
    def save_daily_data(
        self, 
        df: pd.DataFrame, 
        code: str,
        data_source: str = "Unknown"
    ) -> int:
        """
        保存日线数据到数据库
        
        策略：
        - 使用 UPSERT 逻辑（存在则更新，不存在则插入）
        - 跳过已存在的数据，避免重复
        
        Args:
            df: 包含日线数据的 DataFrame
            code: 股票代码
            data_source: 数据来源名称
            
        Returns:
            新增/更新的记录数
        """
        if df is None or df.empty:
            logger.warning(f"保存数据为空，跳过 {code}")
            return 0
        
        saved_count = 0
        
        with self.get_session() as session:
            try:
                for _, row in df.iterrows():
                    # 解析日期
                    row_date = row.get('date')
                    if isinstance(row_date, str):
                        row_date = datetime.strptime(row_date, '%Y-%m-%d').date()
                    elif isinstance(row_date, datetime):
                        row_date = row_date.date()
                    elif isinstance(row_date, pd.Timestamp):
                        row_date = row_date.date()
                    
                    # 检查是否已存在
                    existing = session.execute(
                        select(StockDaily).where(
                            and_(
                                StockDaily.code == code,
                                StockDaily.date == row_date
                            )
                        )
                    ).scalar_one_or_none()
                    
                    if existing:
                        # 更新现有记录
                        existing.open = row.get('open')
                        existing.high = row.get('high')
                        existing.low = row.get('low')
                        existing.close = row.get('close')
                        existing.volume = row.get('volume')
                        existing.amount = row.get('amount')
                        existing.pct_chg = row.get('pct_chg')
                        existing.ma5 = row.get('ma5')
                        existing.ma10 = row.get('ma10')
                        existing.ma20 = row.get('ma20')
                        existing.volume_ratio = row.get('volume_ratio')
                        existing.data_source = data_source
                        existing.updated_at = datetime.now()
                    else:
                        # 创建新记录
                        record = StockDaily(
                            code=code,
                            date=row_date,
                            open=row.get('open'),
                            high=row.get('high'),
                            low=row.get('low'),
                            close=row.get('close'),
                            volume=row.get('volume'),
                            amount=row.get('amount'),
                            pct_chg=row.get('pct_chg'),
                            ma5=row.get('ma5'),
                            ma10=row.get('ma10'),
                            ma20=row.get('ma20'),
                            volume_ratio=row.get('volume_ratio'),
                            data_source=data_source,
                        )
                        session.add(record)
                        saved_count += 1
                
                session.commit()
                logger.info(f"保存 {code} 数据成功，新增 {saved_count} 条")
                
            except Exception as e:
                session.rollback()
                logger.error(f"保存 {code} 数据失败: {e}")
                raise
        
        return saved_count
    
    def get_analysis_context(
        self, 
        code: str,
        target_date: Optional[date] = None
    ) -> Optional[Dict[str, Any]]:
        """
        获取分析所需的上下文数据
        
        返回今日数据 + 昨日数据的对比信息
        
        Args:
            code: 股票代码
            target_date: 目标日期（默认今天）
            
        Returns:
            包含今日数据、昨日对比等信息的字典
        """
        if target_date is None:
            target_date = date.today()
        
        # 获取最近2天数据
        recent_data = self.get_latest_data(code, days=2)
        
        if not recent_data:
            logger.warning(f"未找到 {code} 的数据")
            return None
        
        today_data = recent_data[0]
        yesterday_data = recent_data[1] if len(recent_data) > 1 else None
        
        context = {
            'code': code,
            'date': today_data.date.isoformat(),
            'today': today_data.to_dict(),
        }
        
        if yesterday_data:
            context['yesterday'] = yesterday_data.to_dict()
            
            # 计算相比昨日的变化
            if yesterday_data.volume and yesterday_data.volume > 0:
                context['volume_change_ratio'] = round(
                    today_data.volume / yesterday_data.volume, 2
                )
            
            if yesterday_data.close and yesterday_data.close > 0:
                context['price_change_ratio'] = round(
                    (today_data.close - yesterday_data.close) / yesterday_data.close * 100, 2
                )
            
            # 均线形态判断
            context['ma_status'] = self._analyze_ma_status(today_data)
        
        return context
    
    def _analyze_ma_status(self, data: StockDaily) -> str:
        """
        分析均线形态
        
        判断条件：
        - 多头排列：close > ma5 > ma10 > ma20
        - 空头排列：close < ma5 < ma10 < ma20
        - 震荡整理：其他情况
        """
        close = data.close or 0
        ma5 = data.ma5 or 0
        ma10 = data.ma10 or 0
        ma20 = data.ma20 or 0
        
        if close > ma5 > ma10 > ma20 > 0:
            return "多头排列 📈"
        elif close < ma5 < ma10 < ma20 and ma20 > 0:
            return "空头排列 📉"
        elif close > ma5 and ma5 > ma10:
            return "短期向好 🔼"
        elif close < ma5 and ma5 < ma10:
            return "短期走弱 🔽"
        else:
            return "震荡整理 ↔️"
    
    def save_sector_info(self, sector_data: Dict[str, Any]) -> bool:
        """
        保存板块信息
        
        Args:
            sector_data: 板块数据字典，包含name, code, change_pct, stock_count, potential_score等字段
            
        Returns:
            是否保存成功
        """
        try:
            with self.get_session() as session:
                # 检查是否已存在
                existing = session.execute(
                    select(SectorInfo).where(SectorInfo.code == sector_data.get('code'))
                ).scalar_one_or_none()
                
                if existing:
                    # 更新现有记录
                    existing.name = sector_data.get('name', existing.name)
                    existing.change_pct = sector_data.get('change_pct', existing.change_pct)
                    existing.stock_count = sector_data.get('stock_count', existing.stock_count)
                    existing.potential_score = sector_data.get('potential_score', existing.potential_score)
                    existing.updated_at = datetime.now()
                else:
                    # 创建新记录
                    sector = SectorInfo(
                        name=sector_data.get('name', ''),
                        code=sector_data.get('code', ''),
                        change_pct=sector_data.get('change_pct', 0.0),
                        stock_count=sector_data.get('stock_count', 0),
                        potential_score=sector_data.get('potential_score', 0.0)
                    )
                    session.add(sector)
                
                session.commit()
                logger.info(f"保存板块信息成功: {sector_data.get('name')}")
                return True
                
        except Exception as e:
            logger.error(f"保存板块信息失败: {e}")
            return False
    
    def save_sector_components(self, sector_code: str, components: List[Dict[str, Any]]) -> bool:
        """
        保存板块成分股
        
        Args:
            sector_code: 板块代码
            components: 成分股列表，每个元素包含code, name, weight等字段
            
        Returns:
            是否保存成功
        """
        try:
            with self.get_session() as session:
                # 先删除该板块的所有成分股记录
                session.execute(
                    SectorComponent.__table__.delete().where(
                        SectorComponent.sector_code == sector_code
                    )
                )
                
                # 添加新的成分股记录
                for comp in components:
                    component = SectorComponent(
                        sector_code=sector_code,
                        stock_code=comp.get('code', ''),
                        stock_name=comp.get('name', ''),
                        weight=comp.get('weight', 0.0)
                    )
                    session.add(component)
                
                session.commit()
                logger.info(f"保存板块成分股成功: {sector_code}, 共 {len(components)} 只")
                return True
                
        except Exception as e:
            logger.error(f"保存板块成分股失败: {e}")
            return False
    
    def get_sector_info(self, sector_code: str) -> Optional[SectorInfo]:
        """
        获取板块信息
        
        Args:
            sector_code: 板块代码
            
        Returns:
            板块信息对象，如果不存在则返回None
        """
        try:
            with self.get_session() as session:
                sector = session.execute(
                    select(SectorInfo).where(SectorInfo.code == sector_code)
                ).scalar_one_or_none()
                return sector
        except Exception as e:
            logger.error(f"获取板块信息失败: {e}")
            return None
    
    def get_all_sectors(self) -> List[SectorInfo]:
        """
        获取所有板块信息
        
        Returns:
            板块信息列表
        """
        try:
            with self.get_session() as session:
                sectors = session.execute(
                    select(SectorInfo).order_by(SectorInfo.potential_score.desc())
                ).scalars().all()
                return list(sectors)
        except Exception as e:
            logger.error(f"获取所有板块信息失败: {e}")
            return []
    
    def get_sector_components(self, sector_code: str) -> List[SectorComponent]:
        """
        获取板块成分股
        
        Args:
            sector_code: 板块代码
            
        Returns:
            成分股列表
        """
        try:
            with self.get_session() as session:
                components = session.execute(
                    select(SectorComponent).where(
                        SectorComponent.sector_code == sector_code
                    )
                ).scalars().all()
                return list(components)
        except Exception as e:
            logger.error(f"获取板块成分股失败: {e}")
            return []
    
    def get_sector_stock_codes(self, sector_code: str) -> List[str]:
        """
        获取板块成分股代码列表
        
        Args:
            sector_code: 板块代码
            
        Returns:
            股票代码列表
        """
        components = self.get_sector_components(sector_code)
        return [c.stock_code for c in components]
    
    def is_sector_data_needs_update(self, sector_code: str) -> bool:
        """
        检查板块数据是否需要更新（基于月度更新逻辑）
        
        Args:
            sector_code: 板块代码
            
        Returns:
            是否需要更新
        """
        sector = self.get_sector_info(sector_code)
        if not sector:
            return True
        
        # 检查更新时间是否超过一个月
        update_diff = datetime.now() - sector.updated_at.replace(tzinfo=None)
        if update_diff.days >= 30:
            return True
        
        return False
    
    def get_sectors_needing_update(self) -> List[str]:
        """
        获取需要更新的板块代码列表
        
        Returns:
            需要更新的板块代码列表
        """
        sectors = self.get_all_sectors()
        need_update = []
        
        for sector in sectors:
            if self.is_sector_data_needs_update(sector.code):
                need_update.append(sector.code)
        
        return need_update
    
    def save_watchlist_stock(self, stock_code: str, stock_name: str = "") -> bool:
        """
        保存自选股
        
        Args:
            stock_code: 股票代码
            stock_name: 股票名称（可选）
            
        Returns:
            是否保存成功
        """
        try:
            with self.get_session() as session:
                # 检查是否已存在
                existing = session.execute(
                    select(WatchlistStock).where(WatchlistStock.stock_code == stock_code)
                ).scalar_one_or_none()
                
                if existing:
                    # 更新名称
                    existing.stock_name = stock_name or stock_code
                    existing.updated_at = datetime.now()
                else:
                    # 获取当前最大排序
                    max_order = session.execute(
                        select(WatchlistStock.display_order)
                        .order_by(WatchlistStock.display_order.desc())
                        .limit(1)
                    ).scalar_one_or_none() or 0
                    
                    # 创建新记录
                    watchlist = WatchlistStock(
                        stock_code=stock_code,
                        stock_name=stock_name or stock_code,
                        display_order=max_order + 1
                    )
                    session.add(watchlist)
                
                session.commit()
                logger.info(f"保存自选股成功: {stock_code} {stock_name}")
                return True
                
        except Exception as e:
            logger.error(f"保存自选股失败: {e}")
            return False
    
    def save_watchlist_stocks(self, stock_codes: List[str]) -> bool:
        """
        批量保存自选股
        
        Args:
            stock_codes: 股票代码列表
            
        Returns:
            是否保存成功
        """
        try:
            with self.get_session() as session:
                # 获取当前最大排序
                max_order = session.execute(
                    select(WatchlistStock.display_order)
                    .order_by(WatchlistStock.display_order.desc())
                    .limit(1)
                ).scalar_one_or_none() or 0
                
                for i, code in enumerate(stock_codes):
                    code = code.strip()
                    if not code:
                        continue
                    
                    # 检查是否已存在
                    existing = session.execute(
                        select(WatchlistStock).where(WatchlistStock.stock_code == code)
                    ).scalar_one_or_none()
                    
                    if not existing:
                        watchlist = WatchlistStock(
                            stock_code=code,
                            stock_name=code,
                            display_order=max_order + i + 1
                        )
                        session.add(watchlist)
                
                session.commit()
                logger.info(f"批量保存自选股成功: {len(stock_codes)} 只")
                return True
                
        except Exception as e:
            logger.error(f"批量保存自选股失败: {e}")
            return False
    
    def get_watchlist_stocks(self) -> List[WatchlistStock]:
        """
        获取所有自选股
        
        Returns:
            自选股列表（按排序顺序）
        """
        try:
            with self.get_session() as session:
                stocks = session.execute(
                    select(WatchlistStock)
                    .order_by(WatchlistStock.display_order, WatchlistStock.stock_code)
                ).scalars().all()
                return list(stocks)
        except Exception as e:
            logger.error(f"获取自选股列表失败: {e}")
            return []
    
    def get_watchlist_stock_codes(self) -> List[str]:
        """
        获取自选股代码列表
        
        Returns:
            股票代码列表
        """
        stocks = self.get_watchlist_stocks()
        return [s.stock_code for s in stocks]
    
    def get_watchlist_stock_names(self) -> Dict[str, str]:
        """
        获取自选股名称映射
        
        Returns:
            {股票代码: 股票名称} 字典
        """
        stocks = self.get_watchlist_stocks()
        return {s.stock_code: s.stock_name or s.stock_code for s in stocks}
    
    def delete_watchlist_stock(self, stock_code: str) -> bool:
        """
        删除自选股
        
        Args:
            stock_code: 股票代码
            
        Returns:
            是否删除成功
        """
        try:
            with self.get_session() as session:
                session.execute(
                    WatchlistStock.__table__.delete().where(
                        WatchlistStock.stock_code == stock_code
                    )
                )
                session.commit()
                logger.info(f"删除自选股成功: {stock_code}")
                return True
        except Exception as e:
            logger.error(f"删除自选股失败: {e}")
            return False
    
    def clear_watchlist(self) -> bool:
        """
        清空自选股
        
        Returns:
            是否清空成功
        """
        try:
            with self.get_session() as session:
                session.execute(WatchlistStock.__table__.delete())
                session.commit()
                logger.info("清空自选股成功")
                return True
        except Exception as e:
            logger.error(f"清空自选股失败: {e}")
            return False
    
    def update_watchlist_stock_name(self, stock_code: str, stock_name: str) -> bool:
        """
        更新自选股名称
        
        Args:
            stock_code: 股票代码
            stock_name: 新的股票名称
            
        Returns:
            是否更新成功
        """
        try:
            with self.get_session() as session:
                existing = session.execute(
                    select(WatchlistStock).where(WatchlistStock.stock_code == stock_code)
                ).scalar_one_or_none()
                
                if existing:
                    existing.stock_name = stock_name
                    existing.updated_at = datetime.now()
                    session.commit()
                    logger.info(f"更新自选股名称成功: {stock_code} -> {stock_name}")
                    return True
                else:
                    logger.warning(f"未找到自选股: {stock_code}")
                    return False
        except Exception as e:
            logger.error(f"更新自选股名称失败: {e}")
            return False
    
    # === 分析历史记录管理 ===
    
    def save_analysis_history(self, analysis_data: Dict[str, Any]) -> bool:
        """
        保存分析历史记录
        
        策略：
        - 检查数据库中是否已存在该股票的分析记录
        - 如果存在，则更新最新的一条记录
        - 如果不存在，则创建新记录
        
        Args:
            analysis_data: 分析结果数据，包含code, name, price等字段
            
        Returns:
            是否保存成功
        """
        try:
            with self.get_session() as session:
                stock_code = analysis_data.get('code', '')
                
                # 提取数据
                dashboard = analysis_data.get('dashboard', {})
                price_position = dashboard.get('data_perspective', {}).get('price_position', {})
                core_conclusion = dashboard.get('core_conclusion', {})
                battle_plan = dashboard.get('battle_plan', {})
                
                # 提取次选买入点（从狙击点位中获取）
                secondary_buy = 0.0
                sniper_points = battle_plan.get('sniper_points', {})
                if sniper_points:
                    secondary_buy_str = sniper_points.get('secondary_buy', '')
                    if secondary_buy_str:
                        # 尝试提取数字，格式类似 "次选：1750元(短期回调支撑)"
                        import re
                        match = re.search(r'(\d+\.?\d*)', secondary_buy_str)
                        if match:
                            secondary_buy = float(match.group(1))
                
                # 提取评分（从情绪分数获取，范围0-100）
                score = analysis_data.get('sentiment_score', 0)
                
                # 准备数据字段 - 确保与前端弹窗显示逻辑一致（app.py 287行）
                # 止损位计算：跌破MA20+3% (即 MA20 * 0.97)
                ma20 = price_position.get('ma20', 0.0)
                stop_loss_price = ma20 * 0.97 if ma20 > 0 else price_position.get('support_level', 0.0) * 0.95
                
                update_data = {
                    'stock_name': analysis_data.get('name', ''),
                    'current_price': price_position.get('current_price', 0.0),
                    'buy_point': price_position.get('support_level', 0.0),  # MA5支撑位
                    'secondary_buy_point': secondary_buy,
                    'stop_loss': stop_loss_price,  # 与弹窗一致：MA20 * 0.97
                    'target_price': price_position.get('resistance_level', 0.0),
                    'signal_type': core_conclusion.get('signal_type', '持有'),
                    'sentiment_score': analysis_data.get('sentiment_score', 0),
                    'score': score,
                    'confidence_level': analysis_data.get('confidence_level', '中'),
                    'report_type': analysis_data.get('report_type', 'simple'),
                    'core_conclusion': core_conclusion.get('one_sentence', ''),
                    'result_json': json.dumps(analysis_data, ensure_ascii=False),
                    'analyzed_at': datetime.now(),
                    'updated_at': datetime.now()
                }
                
                # 检查是否存在
                existing = session.execute(
                    select(AnalysisHistory)
                    .where(AnalysisHistory.stock_code == stock_code)
                    .order_by(desc(AnalysisHistory.analyzed_at))
                    .limit(1)
                ).scalar_one_or_none()
                
                if existing:
                    # 更新现有记录
                    for key, value in update_data.items():
                        if hasattr(existing, key):
                            setattr(existing, key, value)
                    logger.info(f"更新分析历史成功: {stock_code}")
                else:
                    # 创建新记录
                    history = AnalysisHistory(
                        stock_code=stock_code,
                        **update_data
                    )
                    session.add(history)
                    logger.info(f"新增分析历史成功: {stock_code}")
                
                session.commit()
                return True
                
        except Exception as e:
            logger.error(f"保存分析历史失败: {e}")
            return False
    
    def get_analysis_history(
        self, 
        limit: int = 50,
        offset: int = 0,
        stock_code: Optional[str] = None
    ) -> List[AnalysisHistory]:
        """
        获取分析历史记录
        
        Args:
            limit: 返回记录数量限制
            offset: 偏移量（用于分页）
            stock_code: 可选的股票代码筛选
            
        Returns:
            分析历史记录列表
        """
        try:
            with self.get_session() as session:
                query = select(AnalysisHistory).order_by(desc(AnalysisHistory.analyzed_at))
                
                if stock_code:
                    query = query.where(AnalysisHistory.stock_code == stock_code)
                
                query = query.limit(limit).offset(offset)
                
                results = session.execute(query).scalars().all()
                return list(results)
        except Exception as e:
            logger.error(f"获取分析历史失败: {e}")
            return []
    
    def get_analysis_history_count(self, stock_code: Optional[str] = None) -> int:
        """
        获取分析历史记录总数
        
        Args:
            stock_code: 可选的股票代码筛选
            
        Returns:
            记录总数
        """
        try:
            with self.get_session() as session:
                from sqlalchemy import func
                query = select(func.count(AnalysisHistory.id))
                
                if stock_code:
                    query = query.where(AnalysisHistory.stock_code == stock_code)
                
                count = session.execute(query).scalar()
                return count or 0
        except Exception as e:
            logger.error(f"获取分析历史记录总数失败: {e}")
            return 0
    
    def delete_analysis_history(self, history_id: int) -> bool:
        """
        删除指定的分析历史记录
        
        Args:
            history_id: 历史记录ID
            
        Returns:
            是否删除成功
        """
        try:
            with self.get_session() as session:
                session.execute(
                    AnalysisHistory.__table__.delete().where(
                        AnalysisHistory.id == history_id
                    )
                )
                session.commit()
                logger.info(f"删除分析历史成功: {history_id}")
                return True
        except Exception as e:
            logger.error(f"删除分析历史失败: {e}")
            return False

    def clear_database(self) -> bool:
        """
        清空所有数据库表的数据
        
        Returns:
            是否清空成功
        """
        try:
            with self.get_session() as session:
                # 按依赖关系反向清除（如果有外键）
                # 目前模型间没有强外键约束，顺序不太重要，但保持良好的习惯
                session.execute(AnalysisHistory.__table__.delete())
                session.execute(WatchlistStock.__table__.delete())
                session.execute(SectorComponent.__table__.delete())
                session.execute(SectorInfo.__table__.delete())
                session.execute(StockDaily.__table__.delete())
                
                session.commit()
                logger.info("所有数据库表已清空")
                return True
        except Exception as e:
            session.rollback()
            logger.error(f"清空数据库失败: {e}")
            return False


# 便捷函数
def get_db() -> DatabaseManager:
    """获取数据库管理器实例的快捷方式"""
    return DatabaseManager.get_instance()


if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(level=logging.DEBUG)
    
    db = get_db()
    
    print("=== 数据库测试 ===")
    print(f"数据库初始化成功")
    
    # 测试检查今日数据
    has_data = db.has_today_data('600519')
    print(f"茅台今日是否有数据: {has_data}")
    
    # 测试保存数据
    test_df = pd.DataFrame({
        'date': [date.today()],
        'open': [1800.0],
        'high': [1850.0],
        'low': [1780.0],
        'close': [1820.0],
        'volume': [10000000],
        'amount': [18200000000],
        'pct_chg': [1.5],
        'ma5': [1810.0],
        'ma10': [1800.0],
        'ma20': [1790.0],
        'volume_ratio': [1.2],
    })
    
    saved = db.save_daily_data(test_df, '600519', 'TestSource')
    print(f"保存测试数据: {saved} 条")
    
    # 测试获取上下文
    context = db.get_analysis_context('600519')
    print(f"分析上下文: {context}")
