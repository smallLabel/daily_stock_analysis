# -*- coding: utf-8 -*-
"""
持仓管理 - 数据模型

定义持仓和交易记录的数据结构
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List


class PositionStatus(Enum):
    """持仓状态"""
    ACTIVE = "active"      # 持仓中
    CLOSED = "closed"      # 已平仓
    PARTIAL = "partial"    # 部分平仓


class TransactionType(Enum):
    """交易类型"""
    BUY = "buy"           # 买入
    SELL = "sell"         # 卖出
    DIVIDEND = "dividend" # 分红


@dataclass
class Transaction:
    """交易记录"""
    id: Optional[int] = None
    stock_code: str = ""
    stock_name: str = ""
    transaction_type: TransactionType = TransactionType.BUY
    quantity: float = 0.0          # 数量(股)
    price: float = 0.0             # 成交价格
    amount: float = 0.0            # 成交金额
    commission: float = 0.0        # 手续费
    tax: float = 0.0               # 印花税
    transaction_date: datetime = field(default_factory=datetime.now)
    notes: str = ""                # 备注
    created_at: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self):
        """初始化后计算成交金额"""
        if self.amount == 0 and self.quantity and self.price:
            self.amount = self.quantity * self.price
    
    def get_total_cost(self) -> float:
        """获取总成本(含手续费)"""
        return self.amount + self.commission + self.tax


@dataclass
class Position:
    """持仓记录"""
    id: Optional[int] = None
    stock_code: str = ""
    stock_name: str = ""
    quantity: float = 0.0            # 持仓数量
    avg_cost: float = 0.0            # 平均成本
    current_price: float = 0.0       # 当前价格
    market_value: float = 0.0        # 市值
    profit_loss: float = 0.0         # 浮动盈亏
    profit_loss_pct: float = 0.0     # 盈亏比例
    status: PositionStatus = PositionStatus.ACTIVE
    
    # 风控参数
    stop_loss_price: Optional[float] = None    # 止损价
    take_profit_price: Optional[float] = None  # 止盈价
    
    # 时间信息
    first_buy_date: Optional[datetime] = None
    last_update: datetime = field(default_factory=datetime.now)
    created_at: datetime = field(default_factory=datetime.now)
    
    # 关联交易
    transactions: List[Transaction] = field(default_factory=list)
    
    def update_current_price(self, price: float):
        """更新当前价格并重新计算盈亏"""
        self.current_price = price
        self.market_value = self.quantity * price
        self.profit_loss = self.market_value - (self.quantity * self.avg_cost)
        self.profit_loss_pct = (self.profit_loss / (self.quantity * self.avg_cost) * 100) if self.avg_cost > 0 else 0
        self.last_update = datetime.now()
    
    def check_risk_alerts(self) -> List[str]:
        """检查风险提醒"""
        alerts = []
        
        if self.stop_loss_price and self.current_price <= self.stop_loss_price:
            alerts.append(f"⚠️ 触发止损: 当前价{self.current_price:.2f} <= 止损价{self.stop_loss_price:.2f}")
        
        if self.take_profit_price and self.current_price >= self.take_profit_price:
            alerts.append(f"✅ 触发止盈: 当前价{self.current_price:.2f} >= 止盈价{self.take_profit_price:.2f}")
        
        if self.profit_loss_pct < -10:
            alerts.append(f"🚨 亏损超10%: 当前亏损{self.profit_loss_pct:.2f}%")
        
        return alerts
    
    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'stock_code': self.stock_code,
            'stock_name': self.stock_name,
            'quantity': self.quantity,
            'avg_cost': self.avg_cost,
            'current_price': self.current_price,
            'market_value': self.market_value,
            'profit_loss': self.profit_loss,
            'profit_loss_pct': self.profit_loss_pct,
            'status': self.status.value,
            'stop_loss_price': self.stop_loss_price,
            'take_profit_price': self.take_profit_price,
            'first_buy_date': self.first_buy_date.isoformat() if self.first_buy_date else None,
            'last_update': self.last_update.isoformat(),
            'created_at': self.created_at.isoformat(),
        }
