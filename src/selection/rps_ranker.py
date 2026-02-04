# -*- coding: utf-8 -*-
"""
===================================
欧奈尔 RPS (Relative Price Strength) 选股模型
===================================

功能：
1. 计算全市场股票的 RPS 分数 (0-100)
2. 识别市场中最强的头部股票
3. 基于 RPS 强度进行选股
4. 支持按自选股范围筛选，避免全量请求

RPS 定义：
股票在特定时间段（如60日、120日、250日）内的涨幅在全市场中的排名百分比。
RPS 90 意味着该股票的涨幅超过了市场 90% 的股票。

核心逻辑：
1. 获取全市场实时快照 (包含 60日涨跌幅 等数据) 或 指定股票列表
2. 过滤垃圾股 (ST, 流动性差)
3. 对涨跌幅进行排序并计算百分位
4. 筛选出 RPS > 90 (或自定义阈值) 的强势股
"""

import logging
import pandas as pd
import numpy as np
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

from data_provider import DataFetcherManager

logger = logging.getLogger(__name__)

@dataclass
class RPSResult:
    """RPS 分析结果"""
    code: str
    name: str
    current_price: float
    change_pct: float     # 今日涨跌
    change_60d: float    # 60日涨跌幅
    rps_60d: float       # 60日 RPS 分数 (0-100)
    change_ytd: float    # 年初至今涨跌幅
    total_mv: float      # 总市值
    
    def to_dict(self):
        return {
            'code': self.code,
            'name': self.name,
            'current_price': self.current_price,
            'change_pct': self.change_pct,
            'change_60d': self.change_60d,
            'rps_60d': self.rps_60d,
            'change_ytd': self.change_ytd,
            'total_mv': self.total_mv
        }

class RPSRanker:
    """RPS 排名计算器"""
    
    def __init__(self, 
                 data_manager: Optional[DataFetcherManager] = None,
                 stock_list: Optional[List[str]] = None):
        """
        初始化 RPS 排名计算器
        
        Args:
            data_manager: 数据管理器
            stock_list: 关注的股票列表（None表示分析全市场）
        """
        self.data_manager = data_manager or DataFetcherManager()
        self.stock_list = stock_list
        if stock_list:
            logger.info(f"[RPS] 初始化，自选股数量: {len(stock_list)}")
        
    def get_top_rps_stocks(self, 
                          top_n: int = 50, 
                          min_rps: int = 90, 
                          exclude_st: bool = True,
                          min_price: float = 3.0,
                          stock_list: Optional[List[str]] = None) -> List[RPSResult]:
        """
        获取 RPS 排名最高的股票
        
        Args:
            top_n: 返回前 N 只
            min_rps: 最小 RPS 分数 (默认90)
            exclude_st: 是否排除 ST 股
            min_price: 最低股价过滤
            stock_list: 股票列表（None则使用初始化时的自选股，优先使用参数）
        
        Returns:
            List[RPSResult]: 排序后的 RPS 结果列表
        """
        target_list = stock_list or self.stock_list
        
        if target_list:
            logger.info(f"开始计算 RPS 排名 (Top {top_n}, RPS>={min_rps}, 自选股模式: {len(target_list)}只)")
        else:
            logger.info(f"开始计算全市场 RPS 排名 (Top {top_n}, RPS>={min_rps})")
        
        try:
            if target_list:
                df = self._get_snapshot_for_stocks(target_list, min_price)
            else:
                df = self.data_manager.get_all_stocks_snapshot()
                
            if df is None or df.empty:
                logger.warning("未能获取股票快照数据，无法计算 RPS")
                return []
            
            if target_list:
                logger.info(f"[RPS] 获取到 {len(df)} 只股票的数据")
            
            if exclude_st:
                df = df[~df['name'].str.contains('ST', case=False, na=False)]
                
            df['change_60d'] = pd.to_numeric(df['change_60d'], errors='coerce').fillna(-999)
            
            if target_list:
                df['rps_60d'] = df['change_60d'].rank(pct=True, ascending=True) * 100
            else:
                df['rps_60d'] = df['change_60d'].rank(pct=True, ascending=True) * 100
            
            strong_stocks = df[df['rps_60d'] >= min_rps].copy()
            strong_stocks = strong_stocks.sort_values('rps_60d', ascending=False)
            
            results = []
            for _, row in strong_stocks.head(top_n).iterrows():
                results.append(RPSResult(
                    code=row['code'],
                    name=row['name'],
                    current_price=row.get('price', 0.0),
                    change_pct=row.get('change_pct', 0.0),
                    change_60d=row.get('change_60d', 0.0),
                    rps_60d=round(row['rps_60d'], 2),
                    change_ytd=row.get('change_ytd', 0.0),
                    total_mv=row.get('total_mv', 0.0)
                ))
                
            logger.info(f"RPS 计算完成，筛选出 {len(results)} 只强势股")
            return results
            
        except Exception as e:
            logger.error(f"RPS 计算失败: {e}", exc_info=True)
            return []
    
    def _get_snapshot_for_stocks(self, stock_codes: List[str], min_price: float = 3.0) -> Optional[pd.DataFrame]:
        """
        获取指定股票的快照数据（避免全量请求）
        
        Args:
            stock_codes: 股票代码列表
            min_price: 最低股价
            
        Returns:
            DataFrame: 股票快照数据
        """
        all_data = []
        
        for code in stock_codes:
            try:
                quote = self.data_manager.get_realtime_quote(code)
                if quote and quote.has_basic_data():
                    all_data.append({
                        'code': code,
                        'name': quote.name,
                        'price': quote.price,
                        'change_pct': quote.change_pct,
                        'change_60d': getattr(quote, 'change_60d', 0.0),
                        'change_ytd': getattr(quote, 'change_ytd', 0.0),
                        'total_mv': getattr(quote, 'total_mv', 0.0)
                    })
            except Exception as e:
                logger.debug(f"获取 {code} 快照失败: {e}")
                continue
        
        if all_data:
            df = pd.DataFrame(all_data)
            df = df[df['price'] >= min_price]
            return df
        
        return None

if __name__ == "__main__":
    import sys
    sys.path.insert(0, '.')
    logging.basicConfig(level=logging.INFO)
    
    ranker = RPSRanker()
    top_stocks = ranker.get_top_rps_stocks(top_n=10)
    for s in top_stocks:
        print(f"{s.code} {s.name} | RPS: {s.rps_60d} | 60日涨幅: {s.change_60d}%")
