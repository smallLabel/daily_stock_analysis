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
