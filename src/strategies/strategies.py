from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
import pandas as pd
import numpy as np

try:
    import pandas_ta as ta
    HAS_PANDAS_TA = True
except ImportError:
    HAS_PANDAS_TA = False
    # 简单的技术指标实现
    def calculate_sma(series, length):
        return series.rolling(window=length).mean()
        
    def calculate_macd(df, fast=12, slow=26, signal=9):
        # 使用EWM计算
        ema_fast = df['close'].ewm(span=fast, adjust=False).mean()
        ema_slow = df['close'].ewm(span=slow, adjust=False).mean()
        macd = ema_fast - ema_slow
        signal_line = macd.ewm(span=signal, adjust=False).mean()
        hist = macd - signal_line
        return pd.DataFrame({
            f'MACD_{fast}_{slow}_{signal}': macd,
            f'MACDs_{fast}_{slow}_{signal}': signal_line,
            f'MACDh_{fast}_{slow}_{signal}': hist
        })
        
    def calculate_rsi(series, length=14):
        delta = series.diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        
        avg_gain = gain.ewm(alpha=1/length, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/length, adjust=False).mean()
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def calculate_bollinger(series, length=20, std_dev=2):
        sma = series.rolling(window=length).mean()
        std = series.rolling(window=length).std()
        upper = sma + (std * std_dev)
        lower = sma - (std * std_dev)
        return pd.DataFrame({'BBM': sma, 'BBU': upper, 'BBL': lower})

    def calculate_kdj(df, k_period=9, d_period=3, j_period=3):
        low_min = df['low'].rolling(window=k_period).min()
        high_max = df['high'].rolling(window=k_period).max()
        
        rsv = (df['close'] - low_min) / (high_max - low_min) * 100
        # SMA for K and D using alpha=1/3 (period=3)
        # Note: Standard KDJ uses Wilder's Smoothing or similar, here effectively EMA
        # But commonly: K = 2/3*PrevK + 1/3*RSV
        
        k_values = []
        d_values = []
        k = 50
        d = 50
        
        for i in range(len(df)):
            if pd.isna(rsv.iloc[i]):
                k_values.append(np.nan)
                d_values.append(np.nan)
            else:
                k = (2/3) * k + (1/3) * rsv.iloc[i]
                d = (2/3) * d + (1/3) * k
                k_values.append(k)
                d_values.append(d)
                
        k_series = pd.Series(k_values, index=df.index)
        d_series = pd.Series(d_values, index=df.index)
        j_series = 3 * k_series - 2 * d_series
        return pd.DataFrame({'K': k_series, 'D': d_series, 'J': j_series})

@dataclass
class TradeSignal:
    """交易信号"""
    code: str
    signal_type: str  # 'BUY', 'SELL', 'HOLD'
    score: float      # 信号强度 0-100
    price: float      # 信号触发价格
    date: str         # 信号日期
    reasons: List[str] = field(default_factory=list)
    stop_loss: float = 0.0
    target_price: float = 0.0

class BaseStrategy(ABC):
    """策略基类"""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        
    @abstractmethod
    def analyze(self, df: pd.DataFrame, stock_code: str) -> Optional[TradeSignal]:
        """
        分析单只股票，返回最新的交易信号
        """
        pass
    
    @abstractmethod
    def get_all_signals(self, df: pd.DataFrame) -> pd.Series:
        """
        获取历史所有信号，用于回测
        返回: Series, 值为 1 (买入), -1 (卖出), 0 (持有)
        """
        pass

# ==========================================
# 具体策略实现
# ==========================================

class MacdStrategy(BaseStrategy):
    """MACD趋势策略：金叉买入，死叉卖出，结合零轴判断强弱"""
    
    def __init__(self):
        super().__init__("MACD趋势策略", "利用MACD指标捕捉中线趋势，适合单边行情")
        
    def analyze(self, df: pd.DataFrame, stock_code: str) -> Optional[TradeSignal]:
        if len(df) < 30:
            return None
            
        # 计算MACD
        if HAS_PANDAS_TA:
            macd = df.ta.macd(close='close', fast=12, slow=26, signal=9)
        else:
            macd = calculate_macd(df, fast=12, slow=26, signal=9)
            
        if macd is None:
            return None
            
        # 提取列 (pandas_ta默认列名: MACD_12_26_9, MACDh_12_26_9, MACDs_12_26_9)
        macd_line = macd['MACD_12_26_9']
        signal_line = macd['MACDs_12_26_9']
        hist = macd['MACDh_12_26_9']
        
        curr_hist = hist.iloc[-1]
        prev_hist = hist.iloc[-2]
        curr_macd = macd_line.iloc[-1]
        curr_price = df['close'].iloc[-1]
        
        reasons = []
        score = 50
        signal_type = "HOLD"
        
        # 金叉逻辑
        if prev_hist < 0 and curr_hist > 0:
            signal_type = "BUY"
            score = 70
            reasons.append("MACD金叉形成")
            
            # 零轴上方金叉更强
            if curr_macd > 0:
                score += 15
                reasons.append("零轴上方强势金叉")
            else:
                reasons.append("零轴下方反弹金叉")
                
        # 强势持仓逻辑
        elif curr_macd > signal_line.iloc[-1] and curr_macd > 0:
            signal_type = "BUY" # 依旧看多
            score = 60
            reasons.append("MACD多头排列中")
            
        return TradeSignal(
            code=stock_code,
            signal_type=signal_type,
            score=score,
            price=curr_price,
            date=str(df.index[-1]),
            reasons=reasons,
            stop_loss=curr_price * 0.95,
            target_price=curr_price * 1.10
        )

    def get_all_signals(self, df: pd.DataFrame) -> pd.Series:
        if len(df) < 30:
            return pd.Series(0, index=df.index)
        
        if HAS_PANDAS_TA:
            macd = df.ta.macd(close='close', fast=12, slow=26, signal=9)
        else:
            macd = calculate_macd(df, fast=12, slow=26, signal=9)
            
        if macd is None:
            return pd.Series(0, index=df.index)
            
        hist = macd['MACDh_12_26_9']
        
        signals = pd.Series(0, index=df.index)
        # 简单的金叉买入(1)，死叉卖出(-1)
        # shift(1) 是上一天，hist > 0 且 prev_hist < 0 为金叉
        buy_signal = (hist > 0) & (hist.shift(1) <= 0)
        sell_signal = (hist < 0) & (hist.shift(1) >= 0)
        
        signals[buy_signal] = 1
        signals[sell_signal] = -1
        
        return signals

class RsiMeanReversionStrategy(BaseStrategy):
    """RSI均值回归策略：超卖反弹买入，超买卖出"""
    
    def __init__(self):
        super().__init__("RSI超跌反弹策略", "捕捉股价超卖后的反弹机会，适合震荡行情")
        
    def analyze(self, df: pd.DataFrame, stock_code: str) -> Optional[TradeSignal]:
        if len(df) < 20: 
            return None
        
        if HAS_PANDAS_TA:
            rsi = df.ta.rsi(close='close', length=14)
        else:
            rsi = calculate_rsi(df['close'], length=14)
            
        if rsi is None:
            return None
            
        curr_rsi = rsi.iloc[-1]
        curr_price = df['close'].iloc[-1]
        
        reasons = []
        score = 50
        signal_type = "HOLD"
        
        if curr_rsi < 30:
            signal_type = "BUY"
            score = 80 + (30 - curr_rsi) # RSI越低分越高
            reasons.append(f"RSI({curr_rsi:.1f})进入超卖区，存在反弹需求")
        elif curr_rsi < 40 and curr_rsi > rsi.iloc[-2]:
            signal_type = "BUY"
            score = 65
            reasons.append("RSI低位回升")
            
        return TradeSignal(
            code=stock_code,
            signal_type=signal_type,
            score=min(score, 100),
            price=curr_price,
            date=str(df.index[-1]),
            reasons=reasons,
            stop_loss=curr_price * 0.97, # 反弹策略止损要严
            target_price=curr_price * 1.05
        )

    def get_all_signals(self, df: pd.DataFrame) -> pd.Series:
        if len(df) < 20: return pd.Series(0, index=df.index)
        
        if HAS_PANDAS_TA:
            rsi = df.ta.rsi(close='close', length=14)
        else:
            rsi = calculate_rsi(df['close'], length=14)
            
        if rsi is None: return pd.Series(0, index=df.index)
        
        signals = pd.Series(0, index=df.index)
        # RSI < 30 买入，RSI > 70 卖出
        signals[rsi < 30] = 1
        signals[rsi > 70] = -1
        return signals

class MaTrendStrategy(BaseStrategy):
    """双均线策略：短期均线上穿长期均线"""
    
    def __init__(self):
        super().__init__("双均线趋势策略", "利用5日和20日均线判断趋势，稳健性较好")
        
    def analyze(self, df: pd.DataFrame, stock_code: str) -> Optional[TradeSignal]:
        if len(df) < 30: return None
        
        if HAS_PANDAS_TA:
            ma5 = df.ta.sma(close='close', length=5)
            ma20 = df.ta.sma(close='close', length=20)
        else:
            ma5 = calculate_sma(df['close'], length=5)
            ma20 = calculate_sma(df['close'], length=20)
        
        curr_ma5 = ma5.iloc[-1]
        curr_ma20 = ma20.iloc[-1]
        prev_ma5 = ma5.iloc[-2]
        prev_ma20 = ma20.iloc[-2]
        curr_price = df['close'].iloc[-1]
        
        reasons = []
        score = 50
        signal_type = "HOLD"
        
        # 金叉
        if curr_ma5 > curr_ma20 and prev_ma5 <= prev_ma20:
            signal_type = "BUY"
            score = 75
            reasons.append("5日均线上穿20日均线(金叉)")
        # 多头排列
        elif curr_ma5 > curr_ma20 and curr_price > curr_ma5:
            signal_type = "BUY"
            score = 65
            reasons.append("均线多头排列且股价在均线上方")
            
        return TradeSignal(
            code=stock_code,
            signal_type=signal_type,
            score=score,
            price=curr_price,
            date=str(df.index[-1]),
            reasons=reasons,
            stop_loss=curr_price * 0.96,
            target_price=curr_price * 1.08
        )
        
    def get_all_signals(self, df: pd.DataFrame) -> pd.Series:
        if len(df) < 30: return pd.Series(0, index=df.index)
        
        if HAS_PANDAS_TA:
            ma5 = df.ta.sma(close='close', length=5)
            ma20 = df.ta.sma(close='close', length=20)
        else:
            ma5 = calculate_sma(df['close'], length=5)
            ma20 = calculate_sma(df['close'], length=20)
        
        signals = pd.Series(0, index=df.index)
        crossover = (ma5 > ma20) & (ma5.shift(1) <= ma20.shift(1))
        crossunder = (ma5 < ma20) & (ma5.shift(1) >= ma20.shift(1))
        
        signals[crossover] = 1
        signals[crossunder] = -1
        return signals

class BollingerStrategy(BaseStrategy):
    """布林带策略：中轨趋势跟踪 + 上下轨支撑压力"""
    
    def __init__(self):
        super().__init__("布林带策略", "利用布林带上下轨捕捉支撑与压力，用中轨判断趋势")
        
    def analyze(self, df: pd.DataFrame, stock_code: str) -> Optional[TradeSignal]:
        if len(df) < 20: return None
        
        length = 20
        std = 2
        
        if HAS_PANDAS_TA:
            # columns: BBL_20_2.0, BBM_20_2.0, BBU_20_2.0
            bb = df.ta.bbands(close='close', length=length, std=std)
        else:
            bb = calculate_bollinger(df['close'], length=length, std_dev=std)
            
        if bb is None: return None
        
        # 兼容不同列名
        upper = bb[f'BBU_{length}_{std}.0'] if HAS_PANDAS_TA else bb['BBU']
        mid = bb[f'BBM_{length}_{std}.0'] if HAS_PANDAS_TA else bb['BBM']
        lower = bb[f'BBL_{length}_{std}.0'] if HAS_PANDAS_TA else bb['BBL']
        
        curr_price = df['close'].iloc[-1]
        prev_price = df['close'].iloc[-2]
        curr_lower = lower.iloc[-1]
        curr_upper = upper.iloc[-1]
        curr_mid = mid.iloc[-1]
        
        reasons = []
        score = 50
        signal_type = "HOLD"
        
        # 1. 回踩下轨反弹 (Mean Reversion)
        if prev_price <= curr_lower * 1.01 and curr_price > curr_lower:
            signal_type = "BUY"
            score = 75
            reasons.append("触及布林下轨后反弹")
        
        # 2. 突破上轨 (Breakout, 强势) - 需配合成交量，这里仅判断价格
        # 但通常突破上轨短期可能回调，所以作为强势信号，不直接建议买入，除非趋势刚启动
        elif curr_price > curr_upper and curr_mid > mid.iloc[-5]: # 中轨向上
            signal_type = "BUY"
            score = 65
            reasons.append("股价强势突破布林上轨，趋势向上")
            
        # 3. 回调中轨支撑
        elif prev_price > curr_mid and curr_price <= curr_mid * 1.01 and curr_mid > mid.iloc[-5]:
            signal_type = "BUY"
            score = 70
            reasons.append("回调布林中轨获得支撑")
            
        return TradeSignal(
            code=stock_code,
            signal_type=signal_type,
            score=score,
            price=curr_price,
            date=str(df.index[-1]),
            reasons=reasons,
            stop_loss=curr_lower * 0.98,
            target_price=curr_upper
        )
        
    def get_all_signals(self, df: pd.DataFrame) -> pd.Series:
        if len(df) < 20: return pd.Series(0, index=df.index)
        
        length = 20
        std = 2
        
        if HAS_PANDAS_TA:
            bb = df.ta.bbands(close='close', length=length, std=std)
        else:
            bb = calculate_bollinger(df['close'], length=length, std_dev=std)
            
        upper = bb[f'BBU_{length}_{std}.0'] if HAS_PANDAS_TA else bb['BBU']
        lower = bb[f'BBL_{length}_{std}.0'] if HAS_PANDAS_TA else bb['BBL']
        
        signals = pd.Series(0, index=df.index)
        prices = df['close']
        
        # 简单策略：跌破下轨买入，突破上轨卖出(回归)
        # 这里使用"下穿下轨回升"作为买点
        buy_signal = (prices.shift(1) <= lower.shift(1)) & (prices > lower)
        # 上穿上轨作为卖点
        sell_signal = (prices > upper)
        
        signals[buy_signal] = 1
        signals[sell_signal] = -1
        return signals

class KDJStrategy(BaseStrategy):
    """KDJ随机指标策略：超卖金叉买入，超买死叉卖出"""
    
    def __init__(self):
        super().__init__("KDJ超短线策略", "利用KDJ指标捕捉超短线买卖点，灵敏度高")
        
    def analyze(self, df: pd.DataFrame, stock_code: str) -> Optional[TradeSignal]:
        if len(df) < 10: return None
        
        if HAS_PANDAS_TA:
            kdj = df.ta.kdj(high='high', low='low', close='close')
        else:
            kdj = calculate_kdj(df)
            
        if kdj is None: return None
        
        # columns: K_9_3, D_9_3, J_9_3
        k = kdj['K_9_3']
        d = kdj['D_9_3']
        j = kdj['J_9_3']
        
        curr_k, curr_d, curr_j = k.iloc[-1], d.iloc[-1], j.iloc[-1]
        prev_k, prev_d, prev_j = k.iloc[-2], d.iloc[-2], j.iloc[-2]
        curr_price = df['close'].iloc[-1]
        
        reasons = []
        score = 50
        signal_type = "HOLD"
        
        # 低位金叉 (K, D < 30)
        if prev_k < prev_d and curr_k > curr_d:
            if curr_k < 30:
                signal_type = "BUY"
                score = 85
                reasons.append(f"KDJ低位金叉(K={curr_k:.1f})，强力买入信号")
            elif curr_k < 50:
                signal_type = "BUY"
                score = 70
                reasons.append("KDJ中低位金叉")
        
        # J线触底反弹
        elif prev_j < 0 and curr_j > 0:
            signal_type = "BUY"
            score = 75
            reasons.append(f"J值({curr_j:.1f})触底反弹，超跌修复")
            
        return TradeSignal(
            code=stock_code,
            signal_type=signal_type,
            score=min(score, 100),
            price=curr_price,
            date=str(df.index[-1]),
            reasons=reasons,
            stop_loss=curr_price * 0.96,
            target_price=curr_price * 1.05
        )
        
    def get_all_signals(self, df: pd.DataFrame) -> pd.Series:
        if len(df) < 10: return pd.Series(0, index=df.index)
        
        if HAS_PANDAS_TA:
            kdj = df.ta.kdj(high='high', low='low', close='close')
        else:
            kdj = calculate_kdj(df)
            
        k, d = kdj['K_9_3'], kdj['D_9_3']
        
        signals = pd.Series(0, index=df.index)
        
        # 金叉
        buy_signal = (k.shift(1) < d.shift(1)) & (k > d) & (k < 40) # 限制在低位金叉才买入
        sell_signal = (k.shift(1) > d.shift(1)) & (k < d) & (k > 60) # 高位死叉卖出
        
        signals[buy_signal] = 1
        signals[sell_signal] = -1
        return signals
