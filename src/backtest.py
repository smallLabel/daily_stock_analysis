# -*- coding: utf-8 -*-
"""
简单向量化回测引擎
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, List

class SimpleBacktester:
    def __init__(self):
        pass

    def run_strategy(self, df: pd.DataFrame, strategy_type: str = 'ma') -> Dict[str, Any]:
        """
        运行策略
        
        Args:
            df: 包含 open, close, high, low, volume 的 DataFrame，索引为日期
            strategy_type: 'ma' (双均线), 'rps' (相对强度), 'div' (底背离)
        """
        if df is None or df.empty:
            return {}
            
        df = df.copy()
        if 'close' not in df.columns:
            return {}
            
        # 排序
        df = df.sort_values('date')
        
        signals = pd.Series(0, index=df.index)
        
        if strategy_type == 'ma':
            # 双均线策略: MA5 > MA20
            df['MA5'] = df['close'].rolling(window=5).mean()
            df['MA20'] = df['close'].rolling(window=20).mean()
            # 简单的持有信号: 当 MA5 > MA20 时持有
            signals[df['MA5'] > df['MA20']] = 1
            
        elif strategy_type == 'rps':
            # 简化版 RPS: 当前价格 > 60日均线 * 1.05 (强势)
            df['MA60'] = df['close'].rolling(window=60).mean()
            signals[df['close'] > df['MA60']] = 1
            
        elif strategy_type == 'div':
            # 简化底背离: 价格创新低但 MACD 未创新低 (这里仅做简单 20日低点判断)
            # 仅作演示，实际需要完整 MACD
            df['min20'] = df['close'].rolling(20).min()
            signals[df['close'] > df['min20']] = 1 # 暂用简单突破代替复杂背离
            
        # 计算策略收益
        df['pch'] = df['close'].pct_change().fillna(0)
        df['strategy_ret'] = df['pch'] * signals.shift(1).fillna(0) # 滞后一期，因信号由当日收盘产生，次日生效
        
        # 累计净值
        df['equity_curve'] = (1 + df['strategy_ret']).cumprod()
        
        # 指标计算
        total_ret = df['equity_curve'].iloc[-1] - 1 if not df.empty else 0
        days = len(df)
        ann_ret = (1 + total_ret) ** (252/days) - 1 if days > 0 else 0
        
        # 最大回撤
        cummax = df['equity_curve'].cummax()
        drawdown = (df['equity_curve'] - cummax) / cummax
        max_dd = drawdown.min()
        
        # 夏普比率 (假设无风险利率 0.03)
        rf = 0.03 / 252
        std = df['strategy_ret'].std()
        sharpe = (df['strategy_ret'].mean() - rf) / std * np.sqrt(252) if std > 0 else 0
        
        return {
            'total_return': total_ret,
            'annualized_return': ann_ret,
            'max_drawdown': max_dd,
            'sharpe_ratio': sharpe,
            'latest_signal': int(signals.iloc[-1]) if not signals.empty else 0,
            'equity_curve': df['equity_curve'].tolist()
        }
