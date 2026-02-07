# -*- coding: utf-8 -*-
"""
===================================
分析器模块包
===================================

职责：
1. 提供模块化的股票分析组件
2. 包含技术面、基本面、筹码、舆情等分析器
3. 统一对外接口

模块结构：
- technical_analyzer.py: 技术面分析（均线、MACD、RSI等）
- fundamental_analyzer.py: 基本面分析（财务指标、估值等）
- chip_analyzer.py: 筹码分析（获利比例、集中度等）
- sentiment_analyzer.py: 舆情分析（新闻、风险、利好等）
"""

# AI分析器（原有）
from src.analyzer import GeminiAnalyzer, AnalysisResult

# 技术面分析器
from src.analyzers.technical_analyzer import (
    StockTrendAnalyzer,
    TrendAnalysisResult,
    TrendStatus,
    VolumeStatus,
    BuySignal,
    MACDStatus,
    RSIStatus,
)

# 基本面分析器
from src.analyzers.fundamental_analyzer import FundamentalAnalyzer


# 筹码分析器
from src.analyzers.chip_analyzer import (
    ChipAnalyzer,
    ChipAnalysisResult,
)

# 舆情分析器
from src.analyzers.sentiment_analyzer import (
    SentimentAnalyzer,
    SentimentAnalysisResult,
)

__all__ = [
    # AI分析器
    'GeminiAnalyzer',
    'AnalysisResult',
    
    # 技术面分析
    'StockTrendAnalyzer',
    'TrendAnalysisResult',
    'TrendStatus',
    'VolumeStatus',
    'BuySignal',
    'MACDStatus',
    'RSIStatus',
    
    # 基本面分析
    'FundamentalAnalyzer',
    
    # 筹码分析
    'ChipAnalyzer',
    'ChipAnalysisResult',
    
    # 舆情分析
    'SentimentAnalyzer',
    'SentimentAnalysisResult',
]
