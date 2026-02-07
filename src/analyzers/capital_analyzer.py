# -*- coding: utf-8 -*-
"""
===================================
资金流向分析器
===================================

职责：
1. 分析个股资金流向（主力、散户）
2. 计算资金净流入趋势
3. 识别主力吸筹/出货行为
"""

import logging
import pandas as pd
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from data_provider import DataFetcherManager

logger = logging.getLogger(__name__)

@dataclass
class CapitalAnalysisResult:
    """资金流向分析结果"""
    code: str
    date: str = ""
    
    # 资金净流入（万元）
    main_net_inflow_today: float = 0.0      # 今日主力净流入
    main_net_inflow_3d: float = 0.0         # 3日主力净流入
    main_net_inflow_5d: float = 0.0         # 5日主力净流入
    main_net_inflow_10d: float = 0.0        # 10日主力净流入
    
    # 连续买入分析
    consecutive_inflow_days: int = 0        # 连续净流入天数
    
    # 主力行为判断
    capital_status: str = "中性"             # 资金状态：主力大幅流入/小幅流入/流出
    flow_trend: str = "无明显趋势"           # 趋势描述
    
    # 详细数据（用于图表展示）
    daily_flows: List[Dict[str, Any]] = field(default_factory=list) # 近期每日资金流向

    def to_dict(self) -> Dict[str, Any]:
        return {
            'code': self.code,
            'date': self.date,
            'main_net_inflow_today': self.main_net_inflow_today,
            'main_net_inflow_3d': self.main_net_inflow_3d,
            'main_net_inflow_5d': self.main_net_inflow_5d,
            'main_net_inflow_10d': self.main_net_inflow_10d,
            'consecutive_inflow_days': self.consecutive_inflow_days,
            'capital_status': self.capital_status,
            'flow_trend': self.flow_trend,
            'daily_flows': self.daily_flows
        }

class CapitalAnalyzer:
    """
    资金面分析器
    
    核心逻辑：
    1. 跟随主力：重点关注主力资金（超大单+大单）的动向
    2. 趋势确认：单日流入可能不仅是骗线，连续流入更可靠
    3. 量价配合：资金流入配合股价上涨是最佳状态
    """
    
    def __init__(self):
        self.fetcher_manager = DataFetcherManager()
        
    def analyze(self, code: str) -> Optional[CapitalAnalysisResult]:
        """
        分析资金流向
        
        Args:
            code: 股票代码
            
        Returns:
            CapitalAnalysisResult 或 None
        """
        try:
            # 1. 获取资金流向数据 (优先使用 efinance)
            # 目前只有 EfinanceFetcher 实现了 get_history_money_flow
            # 我们通过 fetcher_manager 遍历查找支持该方法的 fetcher
            
            df_flow = None
            for fetcher in self.fetcher_manager._fetchers:
                if hasattr(fetcher, 'get_history_money_flow'):
                    try:
                        df_flow = fetcher.get_history_money_flow(code)
                        if df_flow is not None and not df_flow.empty:
                            break
                    except Exception as e:
                        logger.warning(f"[{fetcher.name}] 获取资金流向失败: {e}")
                        continue
            
            if df_flow is None or df_flow.empty:
                logger.warning(f"[{code}] 未获取到资金流向数据")
                return None
            
            # 按日期降序排列（最新的在最前）
            df_flow = df_flow.sort_values(by='date', ascending=False).reset_index(drop=True)
            
            # 2. 构建分析结果
            latest = df_flow.iloc[0]
            result = CapitalAnalysisResult(code=code, date=latest['date'])
            
            # 转换单位：原始数据通常是元，转换为万元便于阅读
            unit_converter = 10000 
            
            # 今日流入
            main_inflow = float(latest.get('main_net_inflow', 0) or 0)
            result.main_net_inflow_today = main_inflow / unit_converter
            
            # 3. 计算多日累计净流入
            # 注意：取前N行求和
            periods = [3, 5, 10]
            for p in periods:
                if len(df_flow) >= p:
                    sub_df = df_flow.iloc[:p]
                    # sum()可能会有精度问题，但对资金流分析影响不大
                    total_inflow = sub_df['main_net_inflow'].sum()
                    setattr(result, f'main_net_inflow_{p}d', total_inflow / unit_converter)
                else:
                    # 数据不足时，计算现有数据的和
                    total_inflow = df_flow['main_net_inflow'].sum()
                    setattr(result, f'main_net_inflow_{p}d', total_inflow / unit_converter)

            # 4. 计算连续净流入天数
            consecutive = 0
            for i in range(len(df_flow)):
                val = df_flow.iloc[i].get('main_net_inflow', 0)
                if val > 0:
                    consecutive += 1
                else:
                    break
            result.consecutive_inflow_days = consecutive
            
            # 5. 状态判断
            self._judge_status(result)
            
            # 6. 保存部分历史数据用于前端展示 (最近10天)
            display_days = min(10, len(df_flow))
            for i in range(display_days):
                row = df_flow.iloc[i]
                result.daily_flows.append({
                    'date': row['date'],
                    'close': row['close'],
                    'pct_chg': row['pct_chg'],
                    'main_net_inflow': float(row.get('main_net_inflow', 0) or 0) / unit_converter,
                    'super_large_inflow': float(row.get('super_large_net_inflow', 0) or 0) / unit_converter,
                })
            
            # 保持 daily_flows 按日期升序（方便图表）
            result.daily_flows.reverse()
            
            return result
            
        except Exception as e:
            logger.error(f"[{code}] 资金流向分析异常: {e}")
            return None

    def _judge_status(self, result: CapitalAnalysisResult) -> None:
        """判断资金状态"""
        
        # 阈值 (万元)
        HUGE_INFLOW = 10000   # 1亿
        LARGE_INFLOW = 2000   # 2000万
        
        today_inflow = result.main_net_inflow_today
        data_5d = result.main_net_inflow_5d
        
        # 单日状态
        status = "中性"
        if today_inflow > HUGE_INFLOW:
            status = "主力大幅流入"
        elif today_inflow > LARGE_INFLOW:
            status = "主力明显流入"
        elif today_inflow > 0:
            status = "主力小幅流入"
        elif today_inflow < -HUGE_INFLOW:
            status = "主力大幅流出"
        elif today_inflow < -LARGE_INFLOW:
            status = "主力明显流出"
        else:
            status = "主力小幅流出"
            
        result.capital_status = status
        
        # 趋势判断
        trend = []
        if result.consecutive_inflow_days >= 3:
            trend.append(f"连续{result.consecutive_inflow_days}日净流入")
        
        if data_5d > HUGE_INFLOW * 2: # 5日累计超2亿
            trend.append("5日资金抢筹")
        elif data_5d > 0:
             trend.append("短期资金回补")
        elif data_5d < -HUGE_INFLOW * 2:
             trend.append("资金持续出逃")
             
        if not trend:
            result.flow_trend = "资金博弈胶着"
        else:
            result.flow_trend = "，".join(trend)
