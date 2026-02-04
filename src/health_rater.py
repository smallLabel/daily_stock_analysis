# -*- coding: utf-8 -*-
"""
股性健康度评价系统 (Stock Health Rater)
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional
import matplotlib.pyplot as plt
import io
import logging

logger = logging.getLogger(__name__)

class StockHealthRater:
    def __init__(self):
        # 权重配置
        self.weights = {
            'strategy_fit': 0.40,
            'efficiency': 0.35,
            'vitality': 0.25
        }
        
    def evaluate(self, df: pd.DataFrame, strategy_type: str = 'ma') -> Dict[str, Any]:
        """
        全方位评估个股健康度
        """
        if df is None or df.empty or len(df) < 60:
            return None
            
        df = df.copy()
        df = df.sort_values('date').reset_index(drop=True)
        
        # 0. 数据预处理
        df = self._preprocess_data(df)
        
        # 1. 策略契合度 (40%)
        score_fit, metric_fit = self._calc_strategy_fit(df, strategy_type)
        
        # 2. 收益风险比 (35%)
        score_eff, metric_eff = self._calc_efficiency(df)
        
        # 3. 股性活跃度 (25%)
        score_vit, metric_vit = self._calc_vitality(df)
        
        # 总分
        total_score = (score_fit * self.weights['strategy_fit'] +
                       score_eff * self.weights['efficiency'] +
                       score_vit * self.weights['vitality'])
                       
        return {
            'total_score': round(total_score, 1),
            'scores': {
                'fitness': round(score_fit, 1),
                'efficiency': round(score_eff, 1),
                'vitality': round(score_vit, 1)
            },
            'metrics': {
                **metric_fit,
                **metric_eff,
                **metric_vit
            },
            'equity_curve': df['close'] / df['close'].iloc[0] # 简单的基准净值
        }

    def _preprocess_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """预处理：计算指标、识别异常值、计算时间权重"""
        # 识别一字涨停/跌停 (Open=Close=High=Low)
        # 严格来说还需要结合涨跌停幅度，这里简化处理
        df['is_flat_limit'] = (
            (df['open'] == df['close']) & 
            (df['high'] == df['low']) & 
            (np.abs(df['pct_chg']) > 9.0) # 假设 > 9% 且一字板为不可交易
        )
        
        # 识别长下影线 (下影线长度 > 实体 * 2 且 下影线 > 2%)
        df['body'] = np.abs(df['close'] - df['open'])
        df['lower_wick'] = np.minimum(df['open'], df['close']) - df['low']
        df['is_long_wick'] = (
            (df['lower_wick'] > df['body'] * 2) & 
            (df['lower_wick'] / df['close'] > 0.02)
        )
        
        # 时间权重 (近3个月=0.6, 远期=0.4)
        # 近3个月 approx 60 trading days
        df['time_weight'] = 0.4
        if len(df) > 60:
            df.loc[df.index[-60:], 'time_weight'] = 0.6
        else:
            df['time_weight'] = 0.6 # 数据不足全算近期
            
        return df

    def _calc_strategy_fit(self, df: pd.DataFrame, strategy_type: str) -> tuple:
        """计算策略契合度"""
        # 生成策略信号
        signals = pd.Series(0, index=df.index)
        
        if strategy_type == 'ma':
            df['MA5'] = df['close'].rolling(5).mean()
            df['MA20'] = df['close'].rolling(20).mean()
            signals[df['MA5'] > df['MA20']] = 1
        elif strategy_type == 'rps':
            df['MA60'] = df['close'].rolling(60).mean()
            signals[df['close'] > df['MA60']] = 1
            
        # 识别买入点 (0->1)
        buy_indices = signals[signals.diff() == 1].index
        
        # 1. 信号胜率 (5/10/20日)
        win_counts = 0
        total_signals = len(buy_indices)
        
        if total_signals == 0:
            return 50.0, {'win_rate': 0.0, 'profit_ratio': 0.0} # 无信号给中等分？或者0分
            
        valid_signals = 0
        for idx in buy_indices:
            if idx + 20 >= len(df): continue # 数据不够
            valid_signals += 1
            
            p_buy = df.loc[idx, 'close']
            p_5 = df.loc[idx+5, 'close']
            p_10 = df.loc[idx+10, 'close']
            p_20 = df.loc[idx+20, 'close']
            
            # 如果任意一个周期主要上涨 > 2%，算胜
            if (p_5/p_buy > 1.02) or (p_10/p_buy > 1.05) or (p_20/p_buy > 1.10):
                win_counts += 1
                
        win_rate = win_counts / valid_signals if valid_signals > 0 else 0
        
        # 2. 利润贡献度 (策略收益 / 总涨幅)
        # 策略净值
        df['pch'] = df['pct_chg'] / 100
        df['strat_ret'] = df['pch'] * signals.shift(1).fillna(0)
        strat_total = (1 + df['strat_ret']).prod() - 1
        stock_total = (1 + df['pch']).prod() - 1
        
        # 避免分母为0
        if abs(stock_total) < 0.01: stock_total = 0.01
        
        profit_ratio = strat_total / stock_total
        # 限制在 -1 到 2 之间评价
        profit_ratio = max(min(profit_ratio, 2.0), -1.0)
        
        # 评分公式
        # 胜率: 50% = 60分, 70% = 90分
        score_win = min(100, max(0, (win_rate - 0.3) * 200)) # 30%起步
        
        # 利润比: 0.8 = 80分
        score_profit = min(100, max(0, profit_ratio * 100))
        
        final_score = score_win * 0.6 + score_profit * 0.4
        
        return final_score, {
            'win_rate': round(win_rate, 2),
            'profit_contribution': round(profit_ratio, 2)
        }

    def _calc_efficiency(self, df: pd.DataFrame) -> tuple:
        """计算收益风险比"""
        # 计算 MAR (年化收益 / 最大回撤)
        
        # 先剔除一字板涨停的虚高收益 (将涨幅置为0，模拟买不进)
        df_adj = df.copy()
        df_adj.loc[df_adj['is_flat_limit'], 'pch'] = 0
        
        # 累计净值
        nav = (1 + df_adj['pch']).cumprod()
        
        # 年化
        days = len(df)
        total_ret = nav.iloc[-1] - 1
        ann_ret = (1 + total_ret) ** (252/days) - 1
        
        # 最大回撤
        cummax = nav.cummax()
        dd = (nav - cummax) / cummax
        max_dd = abs(dd.min())
        
        if max_dd < 0.01: max_dd = 0.01 # 避免除0
        
        mar = ann_ret / max_dd
        
        # MAR 评分: MAR=1 => 60分, MAR=2 => 80分, MAR>3 => 100分
        score_mar = min(100, max(0, mar * 30 + 30))
        
        # 波动调和 (剔除跳空后的夏普 - 简化版)
        return score_mar, {
            'mar_ratio': round(mar, 2),
            'max_dd_adj': round(max_dd, 2)
        }

    def _calc_vitality(self, df: pd.DataFrame) -> tuple:
        """计算股性活跃度"""
        # 1. 量价配合 (上涨日的量 > 下跌日的量)
        up_vol = df[df['pch'] > 0]['volume'].mean()
        down_vol = df[df['pch'] < 0]['volume'].mean()
        
        if np.isnan(up_vol): up_vol = 0
        if np.isnan(down_vol) or down_vol == 0: down_vol = 1
        
        vol_ratio = up_vol / down_vol
        score_vol = min(100, max(0, (vol_ratio - 0.8) * 100)) # Ratio 1.8 => 100分
        
        # 2. 均线回踩成功率 (Low 触及 MA20 但 Close > MA20)
        if 'MA20' not in df.columns:
            df['MA20'] = df['close'].rolling(20).mean()
            
        # 寻找回踩日: Low <= MA20 <= High (穿越) 或 Low <= MA20 * 1.01 (接近)
        # 且 Close > MA20 (获得支撑)
        # 且 前3天是跌势 (简单的回踩定义)
        
        support_days = df[
            (df['low'] <= df['MA20'] * 1.01) & 
            (df['close'] > df['MA20'])
        ].index
        
        success_count = 0
        total_support = 0
        
        for idx in support_days:
            if idx + 3 >= len(df): continue
            total_support += 1
            # 后3天不跌破 MA20 且 涨幅 > 0
            curr_ma20 = df.loc[idx, 'MA20']
            future_min = df.loc[idx+1:idx+3, 'close'].min()
            future_ret = df.loc[idx+3, 'close'] / df.loc[idx, 'close'] - 1
            
            if future_min > curr_ma20 * 0.98 and future_ret > 0:
                success_count += 1
                
        support_rate = success_count / total_support if total_support > 0 else 0.5
        score_support = support_rate * 100
        
        final_score = score_vol * 0.5 + score_support * 0.5
        
        return final_score, {
            'vol_ratio': round(vol_ratio, 2),
            'support_rate': round(support_rate, 2)
        }

    def generate_comparison_chart(self, results: List[Dict[str, Any]], filename="health_comparison.png") -> str:
        """生成净值对照图"""
        plt.figure(figsize=(10, 6))
        
        for res in results:
            code = res.get('code', 'Unknown')
            name = res.get('name', '')
            nav = res.get('equity_curve', [])
            
            if len(nav) > 0:
                # 归一化到 1.0 开始
                nav = np.array(nav) / nav.iloc[0]
                plt.plot(nav, label=f"{name}({code}) Score:{res['total_score']}")
                
        plt.title("Stock Trend Comparison (Normalized)")
        plt.xlabel("Trading Days")
        plt.ylabel("Normalized Price")
        plt.legend()
        plt.grid(True)
        
        # 保存
        try:
            plt.savefig(filename)
            plt.close()
            return filename
        except Exception as e:
            logger.error(f"绘图失败: {e}")
            return ""

