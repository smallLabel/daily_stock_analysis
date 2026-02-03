import pandas as pd
import numpy as np
from typing import Dict, Any, List
from .strategies import BaseStrategy

class Backtester:
    """
    轻量级策略回测器
    功能：快速评估策略在某只股票上的近期表现
    """
    
    def __init__(self, initial_capital: float = 100000.0):
        self.initial_capital = initial_capital
        
    def run(self, strategy: BaseStrategy, df: pd.DataFrame, days: int = 120) -> Dict[str, Any]:
        """
        运行回测
        Args:
            strategy: 策略实例
            df: 股票历史数据
            days: 回测最近多少天
        Returns:
            回测结果字典 {return_rate, win_rate, total_trades, ...}
        """
        # 截取最近的数据
        if len(df) > days:
            test_df = df.iloc[-days:].copy()
        else:
            test_df = df.copy()
            
        if test_df.empty:
            return self._empty_result()
            
        # 获取策略信号 (1: Buy, -1: Sell, 0: Hold)
        signals = strategy.get_all_signals(test_df)
        
        # 模拟交易
        position = 0 # 0: 空仓, 1: 持仓
        entry_price = 0.0
        trades = [] # 记录每笔交易盈亏比例
        capital = self.initial_capital
        
        # 价格序列
        prices = test_df['close'].values
        dates = test_df.index
        signal_values = signals.values
        
        for i in range(len(test_df) - 1): # 最后一天强制平仓计算
            price = prices[i]
            signal = signal_values[i]
            
            # 买入逻辑
            if signal == 1 and position == 0:
                position = 1
                entry_price = price
            
            # 卖出逻辑
            elif (signal == -1 and position == 1):
                position = 0
                profit_pct = (price - entry_price) / entry_price
                trades.append(profit_pct)
                capital *= (1 + profit_pct)
        
        # 如果最后还持仓，按现价平仓计算
        if position == 1:
            last_price = prices[-1]
            profit_pct = (last_price - entry_price) / entry_price
            trades.append(profit_pct)
            capital *= (1 + profit_pct)
            
        # 计算统计指标
        total_return = (capital - self.initial_capital) / self.initial_capital
        win_trades = [t for t in trades if t > 0]
        win_rate = len(win_trades) / len(trades) if trades else 0.0
        
        return {
            "strategy_name": strategy.name,
            "total_return": total_return * 100, # 百分比
            "win_rate": win_rate * 100,         # 百分比
            "total_trades": len(trades),
            "days_tested": len(test_df)
        }

    def _empty_result(self):
        return {
            "strategy_name": "Unknown",
            "total_return": 0.0,
            "win_rate": 0.0,
            "total_trades": 0,
            "days_tested": 0
        }

class StrategySelector:
    """
    策略优选器
    功能：针对特定股票或板块，挑选表现最好的策略
    """
    
    def __init__(self, strategies: List[BaseStrategy]):
        self.strategies = strategies
        self.backtester = Backtester()
        
    def pick_best_strategy(self, df: pd.DataFrame) -> tuple[BaseStrategy, Dict]:
        """
        挑选最佳策略
        """
        best_score = -999.0
        best_strategy = self.strategies[0]
        best_result = {}
        
        for strategy in self.strategies:
            result = self.backtester.run(strategy, df)
            
            # 评分逻辑：收益率为主，交易次数过少(偶然性)扣分
            score = result['total_return']
            if result['total_trades'] < 2:
                score *= 0.5 # 交易太少，样本不足，降权
            
            if score > best_score:
                best_score = score
                best_strategy = strategy
                best_result = result
                
        return best_strategy, best_result
