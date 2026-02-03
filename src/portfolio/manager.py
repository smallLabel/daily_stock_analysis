# -*- coding: utf-8 -*-
"""
持仓管理 - 业务逻辑

提供持仓的增删改查、盈亏计算、风险管理等功能
"""

import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Enum as SqlEnum, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

from src.config import get_config
from .models import Position, Transaction, PositionStatus, TransactionType

logger = logging.getLogger(__name__)

Base = declarative_base()


class PositionTable(Base):
    """持仓表"""
    __tablename__ = 'positions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_code = Column(String(20), nullable=False, index=True)
    stock_name = Column(String(100))
    quantity = Column(Float, default=0.0)
    avg_cost = Column(Float, default=0.0)
    current_price = Column(Float, default=0.0)
    market_value = Column(Float, default=0.0)
    profit_loss = Column(Float, default=0.0)
    profit_loss_pct = Column(Float, default=0.0)
    status = Column(SqlEnum(PositionStatus), default=PositionStatus.ACTIVE)
    stop_loss_price = Column(Float, nullable=True)
    take_profit_price = Column(Float, nullable=True)
    first_buy_date = Column(DateTime, nullable=True)
    last_update = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    created_at = Column(DateTime, default=datetime.now)


class TransactionTable(Base):
    """交易记录表"""
    __tablename__ = 'transactions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_code = Column(String(20), nullable=False, index=True)
    stock_name = Column(String(100))
    transaction_type = Column(SqlEnum(TransactionType), nullable=False)
    quantity = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    amount = Column(Float, nullable=False)
    commission = Column(Float, default=0.0)
    tax = Column(Float, default=0.0)
    transaction_date = Column(DateTime, default=datetime.now, index=True)
    notes = Column(Text, default='')
    created_at = Column(DateTime, default=datetime.now)


class PortfolioManager:
    """持仓管理器"""
    
    def __init__(self, db_path: Optional[str] = None):
        """
        初始化持仓管理器
        
        Args:
            db_path: 数据库路径(可选，默认使用配置)
        """
        config = get_config()
        if db_path is None:
            db_path = config.database_path.replace('stock_analysis.db', 'portfolio.db')
        
        self.db_url = f"sqlite:///{db_path}"
        self.engine = create_engine(self.db_url, echo=False)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        
        logger.info(f"持仓管理器初始化完成: {db_path}")
    
    def add_transaction(
        self,
        stock_code: str,
        stock_name: str,
        transaction_type: TransactionType,
        quantity: float,
        price: float,
        commission: float = 0.0,
        tax: float = 0.0,
        transaction_date: Optional[datetime] = None,
        notes: str = ""
    ) -> Transaction:
        """
        添加交易记录并更新持仓
        
        Args:
            stock_code: 股票代码
            stock_name: 股票名称
            transaction_type: 交易类型
            quantity: 数量
            price: 价格
            commission: 手续费
            tax: 印花税
            transaction_date: 交易日期
            notes: 备注
            
        Returns:
            Transaction对象
        """
        session: Session = self.SessionLocal()
        try:
            # 创建交易记录
            amount = quantity * price
            trans = TransactionTable(
                stock_code=stock_code,
                stock_name=stock_name,
                transaction_type=transaction_type,
                quantity=quantity,
                price=price,
                amount=amount,
                commission=commission,
                tax=tax,
                transaction_date=transaction_date or datetime.now(),
                notes=notes
            )
            session.add(trans)
            session.flush()
            
            # 更新持仓
            self._update_position(session, stock_code, stock_name, transaction_type, quantity, price, commission, tax)
            
            session.commit()
            
            logger.info(f"添加交易记录: {stock_code} {transaction_type.value} {quantity}股 @{price}")
            
            return Transaction(
                id=trans.id,
                stock_code=trans.stock_code,
                stock_name=trans.stock_name,
                transaction_type=trans.transaction_type,
                quantity=trans.quantity,
                price=trans.price,
                amount=trans.amount,
                commission=trans.commission,
                tax=trans.tax,
                transaction_date=trans.transaction_date,
                notes=trans.notes,
                created_at=trans.created_at
            )
        except Exception as e:
            session.rollback()
            logger.error(f"添加交易记录失败: {e}")
            raise
        finally:
            session.close()
    
    def _update_position(
        self,
        session: Session,
        stock_code: str,
        stock_name: str,
        transaction_type: TransactionType,
        quantity: float,
        price: float,
        commission: float,
        tax: float
    ):
        """
        更新持仓(内部方法)
        
        根据交易类型更新持仓数量和成本
        """
        position = session.query(PositionTable).filter_by(
            stock_code=stock_code,
            status=PositionStatus.ACTIVE
        ).first()
        
        if transaction_type == TransactionType.BUY:
            if position is None:
                # 首次买入，创建持仓
                total_cost = quantity * price + commission + tax
                position = PositionTable(
                    stock_code=stock_code,
                    stock_name=stock_name,
                    quantity=quantity,
                    avg_cost=total_cost / quantity,
                    current_price=price,
                    market_value=quantity * price,
                    profit_loss=quantity * price - total_cost,
                    profit_loss_pct=((quantity * price - total_cost) / total_cost * 100) if total_cost > 0 else 0,
                    first_buy_date=datetime.now(),
                    status=PositionStatus.ACTIVE
                )
                session.add(position)
            else:
                # 加仓
                old_total_cost = position.quantity * position.avg_cost
                new_cost = quantity * price + commission + tax
                total_cost = old_total_cost + new_cost
                new_quantity = position.quantity + quantity
                
                position.quantity = new_quantity
                position.avg_cost = total_cost / new_quantity
                position.current_price = price
                position.market_value = new_quantity * price
                position.profit_loss = position.market_value - total_cost
                position.profit_loss_pct = (position.profit_loss / total_cost * 100) if total_cost > 0 else 0
                position.last_update = datetime.now()
        
        elif transaction_type == TransactionType.SELL:
            if position is None:
                raise ValueError(f"没有找到{stock_code}的持仓记录")
            
            if quantity > position.quantity:
                raise ValueError(f"卖出数量({quantity})超过持仓数量({position.quantity})")
            
            # 卖出
            position.quantity -= quantity
            
            if position.quantity == 0:
                # 全部卖出，平仓
                position.status = PositionStatus.CLOSED
                position.market_value = 0
                position.profit_loss = 0
                position.profit_loss_pct = 0
            else:
                # 部分卖出
                position.status = PositionStatus.PARTIAL
                position.current_price = price
                position.market_value = position.quantity * price
                position.profit_loss = position.market_value - (position.quantity * position.avg_cost)
                position.profit_loss_pct = (position.profit_loss / (position.quantity * position.avg_cost) * 100) if position.avg_cost > 0 else 0
            
            position.last_update = datetime.now()
    
    def get_active_positions(self) -> List[Position]:
        """获取所有活跃持仓"""
        session: Session = self.SessionLocal()
        try:
            positions = session.query(PositionTable).filter_by(status=PositionStatus.ACTIVE).all()
            return [self._to_position(p) for p in positions]
        finally:
            session.close()
    
    def get_position(self, stock_code: str) -> Optional[Position]:
        """获取指定股票的持仓"""
        session: Session = self.SessionLocal()
        try:
            position = session.query(PositionTable).filter_by(
                stock_code=stock_code,
                status=PositionStatus.ACTIVE
            ).first()
            return self._to_position(position) if position else None
        finally:
            session.close()
    
    def get_transactions(self, stock_code: Optional[str] = None, limit: int = 100) -> List[Transaction]:
        """
        获取交易记录
        
        Args:
            stock_code: 股票代码(可选，为空则返回所有)
            limit: 最大记录数
            
        Returns:
            交易记录列表
        """
        session: Session = self.SessionLocal()
        try:
            query = session.query(TransactionTable)
            if stock_code:
                query = query.filter_by(stock_code=stock_code)
            
            transactions = query.order_by(TransactionTable.transaction_date.desc()).limit(limit).all()
            return [self._to_transaction(t) for t in transactions]
        finally:
            session.close()
    
    def update_prices(self, prices: Dict[str, float]):
        """
        批量更新持仓价格
        
        Args:
            prices: {股票代码: 当前价格}
        """
        session: Session = self.SessionLocal()
        try:
            positions = session.query(PositionTable).filter_by(status=PositionStatus.ACTIVE).all()
            
            for position in positions:
                if position.stock_code in prices:
                    price = prices[position.stock_code]
                    position.current_price = price
                    position.market_value = position.quantity * price
                    position.profit_loss = position.market_value - (position.quantity * position.avg_cost)
                    position.profit_loss_pct = (position.profit_loss / (position.quantity * position.avg_cost) * 100) if position.avg_cost > 0 else 0
                    position.last_update = datetime.now()
            
            session.commit()
            logger.info(f"更新了{len(positions)}个持仓的价格")
        except Exception as e:
            session.rollback()
            logger.error(f"更新价格失败: {e}")
            raise
        finally:
            session.close()
    
    def set_risk_params(
        self,
        stock_code: str,
        stop_loss_price: Optional[float] = None,
        take_profit_price: Optional[float] = None
    ):
        """
        设置风控参数
        
        Args:
            stock_code: 股票代码
            stop_loss_price: 止损价
            take_profit_price: 止盈价
        """
        session: Session = self.SessionLocal()
        try:
            position = session.query(PositionTable).filter_by(
                stock_code=stock_code,
                status=PositionStatus.ACTIVE
            ).first()
            
            if position is None:
                raise ValueError(f"没有找到{stock_code}的持仓记录")
            
            if stop_loss_price is not None:
                position.stop_loss_price = stop_loss_price
            if take_profit_price is not None:
                position.take_profit_price = take_profit_price
            
            position.last_update = datetime.now()
            session.commit()
            
            logger.info(f"设置{stock_code}风控参数: 止损={stop_loss_price}, 止盈={take_profit_price}")
        except Exception as e:
            session.rollback()
            logger.error(f"设置风控参数失败: {e}")
            raise
        finally:
            session.close()
    
    def get_portfolio_summary(self) -> Dict[str, Any]:
        """获取持仓组合摘要"""
        positions = self.get_active_positions()
        
        total_market_value = sum(p.market_value for p in positions)
        total_cost = sum(p.quantity * p.avg_cost for p in positions)
        total_profit_loss = sum(p.profit_loss for p in positions)
        total_profit_loss_pct = (total_profit_loss / total_cost * 100) if total_cost > 0 else 0
        
        return {
            'total_positions': len(positions),
            'total_market_value': total_market_value,
            'total_cost': total_cost,
            'total_profit_loss': total_profit_loss,
            'total_profit_loss_pct': total_profit_loss_pct,
            'positions': [p.to_dict() for p in positions]
        }
    
    def _to_position(self, p: PositionTable) -> Position:
        """ORM对象转换为Position"""
        return Position(
            id=p.id,
            stock_code=p.stock_code,
            stock_name=p.stock_name,
            quantity=p.quantity,
            avg_cost=p.avg_cost,
            current_price=p.current_price,
            market_value=p.market_value,
            profit_loss=p.profit_loss,
            profit_loss_pct=p.profit_loss_pct,
            status=p.status,
            stop_loss_price=p.stop_loss_price,
            take_profit_price=p.take_profit_price,
            first_buy_date=p.first_buy_date,
            last_update=p.last_update,
            created_at=p.created_at
        )
    
    def _to_transaction(self, t: TransactionTable) -> Transaction:
        """ORM对象转换为Transaction"""
        return Transaction(
            id=t.id,
            stock_code=t.stock_code,
            stock_name=t.stock_name,
            transaction_type=t.transaction_type,
            quantity=t.quantity,
            price=t.price,
            amount=t.amount,
            commission=t.commission,
            tax=t.tax,
            transaction_date=t.transaction_date,
            notes=t.notes,
            created_at=t.created_at
        )
