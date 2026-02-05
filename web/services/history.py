# -*- coding: utf-8 -*-
"""
分析历史加载器
从数据库加载分析历史记录供UI显示
"""

from typing import List, Dict, Any
from src.storage import get_db
import json


def load_history_page(page_num: int = 1, page_size: int = 10) -> tuple:
    """
    从数据库加载指定页的历史记录
    
    Args:
        page_num: 页码（从1开始）
        page_size: 每页数量
    
    Returns:
        (records, total_count) 元组
    """
    db = get_db()
    offset = (page_num - 1) * page_size
    
    history = db.get_analysis_history(limit=page_size, offset=offset)
    total_count = db.get_analysis_history_count()
    
    # 转换为表格显示格式
    records = []
    for h in history:
        # 解析信号类型
        signal_map = {
            '🟢买入信号': 'buy',
            '买入信号': 'buy',
            '🔴卖出信号': 'sell',
            '卖出信号': 'sell',
            '🟡持有观望': 'hold',
            '持有观望': 'hold',
            '持有': 'hold'
        }
        
        signal = signal_map.get(h.signal_type, 'hold')
        
        # 格式化查询时间
        query_time = ''
        if h.analyzed_at:
            from datetime import datetime as dt
            if isinstance(h.analyzed_at, str):
                query_time = h.analyzed_at[:10]
            else:
                query_time = h.analyzed_at.strftime('%Y-%m-%d')
        
        records.append({
            'code': h.stock_code,
            'name': h.stock_name,
            'price': f"{h.current_price:.2f}" if h.current_price else '0.00',
            'buy_point': f"{h.buy_point:.2f}" if h.buy_point else '0.00',
            'stop_loss': f"{h.stop_loss:.2f}" if h.stop_loss else '0.00',
            'target_price': f"{h.target_price:.2f}" if h.target_price else '0.00',
            'signal': signal,
            'sentiment_score': h.sentiment_score or 0,
            'core_conclusion': h.core_conclusion,
            'result_json': json.loads(h.result_json) if h.result_json else {},
            'change': '',  # 暂不显示涨跌幅
            'query_time': query_time
        })
    
    return records, total_count
