# -*- coding: utf-8 -*-
"""
===================================
A股题材挖掘引擎 (Theme Hunter)
===================================

功能：
1. 每日挖掘市场热门题材
2. 解析题材对应的龙头股
3. 结合 RPS 强度进行过滤

流程：
1. 联网搜索 "A股热门题材", "市场热点"
2. 调用 LLM 提取题材和个股
3. 验证个股代码，输出题材池
"""

import logging
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from src.search_service import SearchService
from src.analyzer import GeminiAnalyzer, get_analyzer
from data_provider import DataFetcherManager

logger = logging.getLogger(__name__)

@dataclass
class ThemeInfo:
    """题材信息"""
    name: str
    description: str
    stocks: List[Dict[str, str]] # [{'code': '600000', 'name': 'PF Bank'}]
    
    def to_dict(self):
        return {
            'name': self.name,
            'description': self.description,
            'stocks': self.stocks
        }

class ThemeHunter:
    """题材挖掘器"""
    
    def __init__(self, 
                 search_service: Optional[SearchService] = None,
                 analyzer: Optional[GeminiAnalyzer] = None,
                 data_manager: Optional[DataFetcherManager] = None):
        self.search_service = search_service
        self.analyzer = analyzer or get_analyzer()
        self.data_manager = data_manager or DataFetcherManager()
        
    def hunt_themes(self, top_n: int = 3) -> List[ThemeInfo]:
        """
        挖掘热门题材
        """
        if not self.search_service or not self.search_service.is_available:
            logger.warning("搜索服务不可用，无法挖掘题材")
            return []
            
        logger.info("开始挖掘今日热门题材...")
        
        try:
            # 1. 搜索
            keywords = ["今日A股热门概念", "主要热点题材", "A股市场风口", "涨停板复盘 题材"]
            query = " ".join(keywords)
            search_resp = self.search_service.search_stock_news(
                stock_code="", stock_name="A股市场", focus_keywords=keywords, max_results=8
            )
            
            if not search_resp.success:
                logger.warning("搜索热门题材失败")
                return []
                
            search_context = search_resp.to_context()
            
            # 2. AI 分析提取
            raw_themes = self.analyzer.analyze_hot_themes(search_context)
            
            # 3. 结构化处理和验证
            themes = []
            for item in raw_themes[:top_n]:
                theme_name = item.get('name', '未知题材')
                clean_stocks = []
                
                for stock_str in item.get('related_stocks', []):
                    # 尝试提取代码和名称
                    # 格式可能是 "600xxx 某某股份" 或 "某某股份(600xxx)"
                    code = None
                    name = None
                    
                    # 提取6位数字
                    code_match = re.search(r'\d{6}', stock_str)
                    if code_match:
                        code = code_match.group(0)
                        # 提取名称 (去掉数字和特殊字符)
                        name = re.sub(r'[^\u4e00-\u9fa5]', '', stock_str)
                    
                    if code:
                        # 验证代码是否存在（可选，简单检查格式）
                        clean_stocks.append({'code': code, 'name': name or code})
                        
                if clean_stocks:
                   themes.append(ThemeInfo(
                       name=theme_name,
                       description=item.get('description', ''),
                       stocks=clean_stocks
                   ))
            
            logger.info(f"成功挖掘 {len(themes)} 个热门题材: {[t.name for t in themes]}")
            return themes
            
        except Exception as e:
            logger.error(f"题材挖掘失败: {e}", exc_info=True)
            return []

if __name__ == "__main__":
    # Test
    # set env vars for API keys first if real test needed
    print("ThemeHunter Test (Requires API Keys)")
