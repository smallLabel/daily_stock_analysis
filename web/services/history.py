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

    signal_map = {
        '🟢买入信号': 'buy',
        '买入信号': 'buy',
        '🔴卖出信号': 'sell',
        '卖出信号': 'sell',
        '🟡持有观望': 'hold',
        '持有观望': 'hold',
        '持有': 'hold'
    }

    records = []
    for h in history:
        if isinstance(h, dict):
            signal_type = h.get('signal_type', '持有')
            analyzed_at = h.get('analyzed_at')
            result_json = h.get('result_json', '{}')
        else:
            signal_type = h.signal_type
            analyzed_at = h.analyzed_at
            result_json = h.result_json

        signal = signal_map.get(signal_type, 'hold')

        query_time = ''
        if analyzed_at:
            from datetime import datetime as dt
            if isinstance(analyzed_at, str):
                query_time = analyzed_at[:10]
            else:
                query_time = analyzed_at.strftime('%Y-%m-%d')

        secondary_buy_point = h.get('secondary_buy_point', 0) if isinstance(h, dict) else h.secondary_buy_point

        extracted_secondary_buy = '-'
        res_data = {}
        try:
            if isinstance(result_json, str):
                res_data = json.loads(result_json)
            elif result_json:
                res_data = result_json

            if res_data and 'dashboard' in res_data:
                secondary_buy_raw = res_data.get('dashboard', {}).get('battle_plan', {}).get('sniper_points', {}).get('secondary_buy', '')
                if secondary_buy_raw:
                    import re
                    match = re.search(r'(\d+\.?\d*)', secondary_buy_raw)
                    if match:
                        extracted_secondary_buy = match.group(1)
        except:
            pass

        final_secondary_buy = '-'
        if secondary_buy_point and secondary_buy_point > 0:
            final_secondary_buy = f"{secondary_buy_point:.2f}"
        elif extracted_secondary_buy != '-':
            final_secondary_buy = extracted_secondary_buy

        if isinstance(h, dict):
            current_price = h.get('current_price', 0) or 0
            buy_point = h.get('buy_point', 0) or 0
            stop_loss = h.get('stop_loss', 0) or 0
            target_price = h.get('target_price', 0) or 0
            sentiment_score = h.get('sentiment_score', 0) or 0
            score = h.get('score', 0) or 0
            core_conclusion = h.get('core_conclusion', '')
            stock_code = h.get('stock_code', '')
            stock_name = h.get('stock_name', '')
        else:
            current_price = h.current_price or 0
            buy_point = h.buy_point or 0
            stop_loss = h.stop_loss or 0
            target_price = h.target_price or 0
            sentiment_score = h.sentiment_score or 0
            score = h.score or 0
            core_conclusion = h.core_conclusion
            stock_code = h.stock_code
            stock_name = h.stock_name

        records.append({
            'code': stock_code,
            'name': stock_name,
            'price': f"{current_price:.2f}" if current_price else '0.00',
            'buy_point': f"{buy_point:.2f}" if buy_point else '0.00',
            'secondary_buy': final_secondary_buy,
            'stop_loss': f"{stop_loss:.2f}" if stop_loss else '0.00',
            'target_price': f"{target_price:.2f}" if target_price else '0.00',
            'signal': signal,
            'sentiment_score': sentiment_score,
            'score': score,
            'core_conclusion': core_conclusion,
            'result_json': res_data,
            'change': '',
            'query_time': query_time
        })

    return records, total_count
