# -*- coding: utf-8 -*-
"""
===================================
板块选股功能 - 潜力板块与个股推荐
===================================

功能：
1. 排除创业板（代码300开头）和科创板（代码688开头）
2. 按照多维度策略分析板块潜力
3. 从潜力板块中筛选优质个股
4. 提供未来一个月的投资建议

策略维度：
- 板块层面：涨跌幅排名、资金流入、板块热度、行业增长趋势
- 个股层面：技术面、基本面、量能、趋势强度
"""

import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timedelta
from enum import Enum

import pandas as pd
import numpy as np

from data_provider import DataFetcherManager
from src.stock_analyzer import StockTrendAnalyzer, BuySignal
from src.search_service import SearchService
from src.strategies.strategies import MacdStrategy, RsiMeanReversionStrategy, MaTrendStrategy, BollingerStrategy, KDJStrategy
from src.strategies.backtester import StrategySelector
from .rps_ranker import RPSRanker
from .theme_hunter import ThemeHunter

logger = logging.getLogger(__name__)


class SectorPotential(Enum):
    """板块潜力评级"""
    VERY_HIGH = "极高潜力"
    HIGH = "高潜力"
    MEDIUM = "中等潜力"
    LOW = "低潜力"
    VERY_LOW = "极低潜力"


@dataclass
class SectorInfo:
    """板块信息"""
    name: str
    code: str
    change_pct: float = 0.0  # 涨跌幅
    change_pct_5d: float = 0.0  # 5日涨跌幅
    change_pct_10d: float = 0.0  # 10日涨跌幅
    volume_ratio: float = 0.0  # 量比
    money_flow: float = 0.0  # 资金流入（亿）
    stock_count: int = 0  # 板块内个股数量
    up_count: int = 0  # 上涨个股数
    down_count: int = 0  # 下跌个股数
    leading_stocks: List[str] = field(default_factory=list)  # 龙头股
    hot_score: float = 0.0  # 热度评分
    potential: SectorPotential = SectorPotential.MEDIUM
    potential_score: float = 0.0  # 潜力评分（0-100）
    reasons: List[str] = field(default_factory=list)  # 推荐理由
    
    def to_dict(self):
        return {
            'name': self.name,
            'code': self.code,
            'change_pct': self.change_pct,
            'change_pct_5d': self.change_pct_5d,
            'change_pct_10d': self.change_pct_10d,
            'volume_ratio': self.volume_ratio,
            'money_flow': self.money_flow,
            'stock_count': self.stock_count,
            'up_count': self.up_count,
            'down_count': self.down_count,
            'leading_stocks': self.leading_stocks,
            'hot_score': self.hot_score,
            'potential': self.potential.value,
            'potential_score': self.potential_score,
            'reasons': self.reasons
        }


@dataclass
class StockRecommendation:
    """个股推荐"""
    code: str
    name: str
    sector: str  # 所属板块
    current_price: float = 0.0
    change_pct: float = 0.0
    buy_signal: str = ""
    signal_score: int = 0
    trend_status: str = ""
    ma_alignment: str = ""
    macd_status: str = ""
    volume_status: str = ""
    bias_ma5: float = 0.0
    support_level: float = 0.0
    resistance_level: float = 0.0
    reasons: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    operation_advice: str = ""
    target_price: float = 0.0  # 目标价位
    stop_loss: float = 0.0  # 止损价位
    strategy_name: str = "默认趋势策略"  # 使用的策略名称
    backtest_info: str = ""  # 回测表现信息
    
    def to_dict(self):
        return {
            'code': self.code,
            'name': self.name,
            'sector': self.sector,
            'current_price': self.current_price,
            'change_pct': self.change_pct,
            'buy_signal': self.buy_signal,
            'signal_score': self.signal_score,
            'trend_status': self.trend_status,
            'ma_alignment': self.ma_alignment,
            'macd_status': self.macd_status,
            'volume_status': self.volume_status,
            'bias_ma5': self.bias_ma5,
            'support_level': self.support_level,
            'resistance_level': self.resistance_level,
            'reasons': self.reasons,
            'risks': self.risks,
            'operation_advice': self.operation_advice,
            'target_price': self.target_price,
            'stop_loss': self.stop_loss,
            'strategy_name': self.strategy_name,
            'backtest_info': self.backtest_info
        }


class SectorStockPicker:
    """
    板块选股器
    
    功能：
    1. 分析所有板块的潜力（可指定板块范围）
    2. 筛选出最具潜力的板块
    3. 从潜力板块中推荐优质个股 (智能策略优选)
    4. 支持按自选股范围选股，避免全量请求
    """
    
    def __init__(self, 
                 data_manager: Optional[DataFetcherManager] = None,
                 search_service: Optional[SearchService] = None,
                 stock_list: Optional[List[str]] = None):
        """
        初始化选股器
        
        Args:
            data_manager: 数据管理器
            search_service: 搜索服务（用于获取新闻和热度信息）
            stock_list: 关注的股票列表（默认从配置读取自选股）
        """
        from src.config import get_config
        
        self.data_manager = data_manager or DataFetcherManager()
        self.search_service = search_service
        self.trend_analyzer = StockTrendAnalyzer()
        
        if stock_list:
            self.stock_list = stock_list
        else:
            config = get_config()
            config.refresh_stock_list()
            self.stock_list = config.stock_list
        
        logger.info(f"[选股器] 初始化，自选股数量: {len(self.stock_list)}")
        
        # 初始化策略库
        self.strategies = [
            MacdStrategy(),
            RsiMeanReversionStrategy(),
            MaTrendStrategy(),
            BollingerStrategy(),
            KDJStrategy()
        ]
        self.strategy_selector = StrategySelector(self.strategies)
        
        # 初始化高级选股组件
        self.rps_ranker = RPSRanker(self.data_manager)
        self.theme_hunter = ThemeHunter(self.search_service, data_manager=self.data_manager)
        
    def analyze_sectors(self, top_n: int = 10, sector_codes: Optional[List[str]] = None) -> List[SectorInfo]:
        """
        分析板块潜力
        
        Args:
            top_n: 返回前N个板块
            sector_codes: 限定分析的板块代码列表（None表示分析全部）
            
        Returns:
            潜力板块列表
        """
        logger.info(f"开始分析板块潜力... 限定板块: {sector_codes if sector_codes else '全部'}")
        
        try:
            # 1. 获取所有板块数据
            sectors_data = self._get_all_sectors()
            if not sectors_data:
                logger.warning("未能获取板块数据")
                return []
            
            # 2. 计算每个板块的潜力评分
            sector_infos = []
            for sector_data in sectors_data:
                sector_info = self._analyze_sector(sector_data)
                if sector_info:
                    sector_infos.append(sector_info)
            
            # 3. 按潜力评分排序
            sector_infos.sort(key=lambda x: x.potential_score, reverse=True)
            
            # 4. 返回前N个
            top_sectors = sector_infos[:top_n]
            
            logger.info(f"分析完成，找到 {len(top_sectors)} 个潜力板块")
            for i, sector in enumerate(top_sectors[:5], 1):
                logger.info(f"{i}. {sector.name} - 潜力评分: {sector.potential_score:.1f}")
            
            return top_sectors
            
        except Exception as e:
            logger.error(f"分析板块时出错: {e}", exc_info=True)
            return []
    
    def _get_all_sectors(self, sector_codes: Optional[List[str]] = None) -> List[Dict]:
        """
        获取板块数据
        
        Args:
            sector_codes: 限定分析的板块代码列表（None表示获取全部）
            
        Returns:
            板块数据列表
        """
        try:
            if sector_codes:
                logger.info(f"[板块筛选] 只分析指定板块: {sector_codes}")
                return [{'code': code, 'name': code} for code in sector_codes]
            
            sectors = self.data_manager.get_sector_rankings(n=100)
            if sectors and len(sectors) == 2:
                top_sectors, bottom_sectors = sectors
                all_sectors = top_sectors + bottom_sectors
                
                unique_sectors = {}
                for sector in all_sectors:
                    key = sector.get('code') or sector.get('name')
                    if key and key not in unique_sectors:
                        unique_sectors[key] = sector
                
                logger.info(f"获取到 {len(all_sectors)} 个板块，去重后 {len(unique_sectors)} 个")
                return list(unique_sectors.values())
            
            logger.warning("未能从数据源获取板块数据")
            return []
            
        except Exception as e:
            logger.error(f"获取板块数据失败: {e}")
            return []
    
    def _analyze_sector(self, sector_data: Dict) -> Optional[SectorInfo]:
        """
        分析单个板块
        
        Args:
            sector_data: 板块原始数据
            
        Returns:
            板块信息对象
        """
        try:
            sector_info = SectorInfo(
                name=sector_data.get('name', ''),
                code=sector_data.get('code', ''),
                change_pct=sector_data.get('change_pct', 0.0),
                money_flow=sector_data.get('money_flow', 0.0),
                stock_count=sector_data.get('stock_count', 0),
                up_count=sector_data.get('up_count', 0),
                down_count=sector_data.get('down_count', 0)
            )
            
            # 计算潜力评分
            score = 0
            reasons = []
            
            # 1. 涨跌幅评分（权重30%）
            if sector_info.change_pct > 5:
                score += 30
                reasons.append(f"今日涨幅{sector_info.change_pct:.2f}%，强势上涨")
            elif sector_info.change_pct > 3:
                score += 25
                reasons.append(f"今日涨幅{sector_info.change_pct:.2f}%，表现良好")
            elif sector_info.change_pct > 0:
                score += 15
                reasons.append(f"今日上涨{sector_info.change_pct:.2f}%")
            elif sector_info.change_pct > -2:
                score += 10
            
            # 2. 资金流入评分（权重25%）
            if sector_info.money_flow > 10:
                score += 25
                reasons.append(f"资金大幅流入{sector_info.money_flow:.1f}亿")
            elif sector_info.money_flow > 5:
                score += 20
                reasons.append(f"资金流入{sector_info.money_flow:.1f}亿")
            elif sector_info.money_flow > 0:
                score += 10
                reasons.append(f"资金净流入{sector_info.money_flow:.1f}亿")
            
            # 3. 板块内个股表现（权重20%）
            if sector_info.stock_count > 0:
                up_ratio = sector_info.up_count / sector_info.stock_count
                if up_ratio > 0.8:
                    score += 20
                    reasons.append(f"板块内{up_ratio*100:.1f}%个股上涨，整体强势")
                elif up_ratio > 0.6:
                    score += 15
                    reasons.append(f"板块内{up_ratio*100:.1f}%个股上涨")
                elif up_ratio > 0.5:
                    score += 10
            
            # 4. 板块热度评分（权重25%）- 如果有搜索服务
            if self.search_service:
                hot_score = self._calculate_sector_hot_score(sector_info.name)
                sector_info.hot_score = hot_score
                if hot_score > 80:
                    score += 25
                    reasons.append("板块热度极高，市场关注度高")
                elif hot_score > 60:
                    score += 20
                    reasons.append("板块热度较高")
                elif hot_score > 40:
                    score += 15
            else:
                # 没有搜索服务时，给予基础分
                score += 12
            
            sector_info.potential_score = score
            sector_info.reasons = reasons
            
            # 设置潜力等级
            if score >= 80:
                sector_info.potential = SectorPotential.VERY_HIGH
            elif score >= 65:
                sector_info.potential = SectorPotential.HIGH
            elif score >= 50:
                sector_info.potential = SectorPotential.MEDIUM
            elif score >= 35:
                sector_info.potential = SectorPotential.LOW
            else:
                sector_info.potential = SectorPotential.VERY_LOW
            
            return sector_info
            
        except Exception as e:
            logger.error(f"分析板块 {sector_data.get('name', 'Unknown')} 时出错: {e}")
            return None
    
    def _calculate_sector_hot_score(self, sector_name: str) -> float:
        """
        计算板块热度评分
        
        Args:
            sector_name: 板块名称
            
        Returns:
            热度评分（0-100）
        """
        try:
            # 搜索板块相关新闻
            query = f"{sector_name} 行业 投资机会"
            results = self.search_service.search(query, max_results=5)
            
            # 根据新闻数量和时效性计算热度
            if not results:
                return 30
            
            score = 30  # 基础分
            
            # 最近3天的新闻权重更高
            recent_count = 0
            for result in results:
                # 假设搜索结果有发布时间
                if hasattr(result, 'published_date'):
                    # 这里简化处理，实际应该解析日期
                    recent_count += 1
            
            score += min(recent_count * 15, 50)  # 新闻热度最多50分
            score += min(len(results) * 4, 20)  # 新闻数量最多20分
            
            return min(score, 100)
            
        except Exception as e:
            logger.warning(f"计算板块热度失败: {e}")
            return 30
    
    def _get_sector_stocks_from_watchlist(self, sector_info: SectorInfo) -> List[str]:
        """
        从自选股中获取属于指定板块的股票
        
        Args:
            sector_info: 板块信息
            
        Returns:
            股票代码列表（仅自选股中属于该板块的）
        """
        try:
            all_stocks = self._get_sector_stocks_raw(sector_info)
            if not all_stocks:
                return []
            
            if not self.stock_list:
                return all_stocks
            
            filtered = [code for code in all_stocks if code in self.stock_list]
            logger.info(f"[板块筛选] 板块 {sector_info.name}: 全量{len(all_stocks)}只 -> 自选{len(filtered)}只")
            return filtered
            
        except Exception as e:
            logger.warning(f"获取板块 {sector_info.name} 自选股失败: {e}")
            return []
    
    def _get_sector_stocks_raw(self, sector_info: SectorInfo) -> List[str]:
        """
        获取板块内的所有股票（原始方法）
        
        Args:
            sector_info: 板块信息
            
        Returns:
            股票代码列表
        """
        try:
            stocks = self.data_manager.get_sector_stocks(sector_info.name)
            if stocks:
                return stocks
        except Exception as e:
            logger.debug(f"获取板块 {sector_info.name} 成分股失败: {e}")
        
        return []
    
    def recommend_stocks_from_sector(self, 
                                     sector_info: SectorInfo, 
                                     top_n: int = 5,
                                     use_watchlist_only: bool = True) -> List[StockRecommendation]:
        """
        从板块中推荐个股 (集成智能策略优选 + 风控过滤)
        
        Args:
            sector_info: 板块信息
            top_n: 返回前N只
            use_watchlist_only: 是否只从自选股中筛选（避免全量请求）
        """
        logger.info(f"开始从板块 {sector_info.name} 筛选个股...")
        
        try:
            if use_watchlist_only:
                stocks = self._get_sector_stocks_from_watchlist(sector_info)
                logger.info(f"[选股策略] 使用自选股模式，从 {sector_info.name} 获取到 {len(stocks)} 只股票")
            else:
                stocks = self._get_sector_stocks_raw(sector_info)
                logger.info(f"[选股策略] 使用全量模式，从 {sector_info.name} 获取到 {len(stocks)} 只股票")
            
            if not stocks:
                logger.warning(f"未能获取板块 {sector_info.name} 的个股列表")
                return []
            
            # 2. 初步过滤 (创业板/科创板/黑名单)
            candidates = []
            for stock_code in stocks:
                if stock_code.startswith('300') or stock_code.startswith('688') or stock_code.startswith('689') or stock_code.startswith('8'):
                    continue
                candidates.append(stock_code)
            
            logger.info(f"板块 {sector_info.name} 基础过滤后剩余 {len(candidates)} 只，开始风控筛选...")

            # 3. 风控过滤 (新功能)
            # 批量获取行情进行过滤，提高效率
            safe_stocks = self._filter_risky_stocks(candidates)
            logger.info(f"板块 {sector_info.name} 风控过滤后剩余 {len(safe_stocks)} 只")
            
            if not safe_stocks:
                return []

            # ==========================================
            # 4. 智能策略优选
            # ==========================================
            best_strategy = self.strategies[0] # 默认
            best_strategy_info = "默认策略"
            
            # 使用风控后的第一只股票作为样本
            if safe_stocks:
                sample_stock = safe_stocks[0]
                try:
                    sample_df = self.data_manager.get_daily_data(sample_stock, days=120)
                    if sample_df is not None and not sample_df.empty:
                        best_strategy, result = self.strategy_selector.pick_best_strategy(sample_df)
                        best_strategy_info = f"收益{result['total_return']:.0f}%/胜率{result['win_rate']:.0f}%"
                        logger.info(f"板块 {sector_info.name} 优选策略: {best_strategy.name} (120天{best_strategy_info})")
                except Exception as e:
                    logger.warning(f"策略优选失败: {e}")

            # 5. 分析每只个股
            recommendations = []
            for stock_code in safe_stocks[:30]:  # 风控后质量较高，取前30只分析即可
                try:
                    # 先尝试用优选策略分析
                    rec = self._analyze_stock_with_strategy(stock_code, sector_info.name, best_strategy)
                    
                    if rec:
                        rec.backtest_info = best_strategy_info
                        recommendations.append(rec)
                    else:
                        # 如果优选策略没出信号，回退到默认趋势分析
                        rec_default = self._analyze_stock(stock_code, sector_info.name)
                        if rec_default and rec_default.signal_score >= 60:
                            recommendations.append(rec_default)
                            
                except Exception as e:
                    logger.warning(f"分析个股 {stock_code} 失败: {e}")
                    continue
            
            # 6. 按信号评分排序
            recommendations.sort(key=lambda x: x.signal_score, reverse=True)
            
            return recommendations[:top_n]
            
        except Exception as e:
            logger.error(f"从板块推荐个股时出错: {e}", exc_info=True)
            return []

    def _filter_risky_stocks(self, stock_codes: List[str]) -> List[str]:
        """
        风控过滤：剔除ST股、低价股、小盘股
        """
        safe_list = []
        # 分批处理，避免一次请求过多
        batch_size = 20
        for i in range(0, len(stock_codes), batch_size):
            batch = stock_codes[i:i+batch_size]
            try:
                quotes = self.data_manager.get_realtime_quotes(batch)
                if not quotes: continue
                
                for code in batch:
                    if code not in quotes: continue
                    info = quotes[code]
                    name = info.get('name', '')
                    price = info.get('current', 0.0)
                    volume = info.get('turnover', 0.0) # 成交额(元)
                    # 有些接口可以是 volume(手) 和 amount(元)，这里假设 data_manager 做了归一化
                    # 如果不确定，可以用 amount
                    
                    # 1. 过滤ST
                    if 'ST' in name.upper():
                        continue
                        
                    # 2. 过滤低价股 (低于3元)
                    if price < 3.0 and price > 0:
                        continue
                        
                    # 3. 过滤流动性枯竭 (这里拿的是实时/当日成交额)
                    # 如果是开盘初期，这个过滤可能不准，所以如果是收盘后分析比较准
                    # 也可以放宽条件，或者检查 ayer_amount 如果有的话
                    # 简单起见，过滤掉成交额极低的（如停牌或僵尸股，假设分析时已有交易）
                    if volume > 0 and volume < 10000000: # 1000万以下暂定为高危
                        continue
                        
                    safe_list.append(code)
            except Exception as e:
                logger.warning(f"风控检查批次失败: {e}")
                # 失败的话暂时保留，避免误杀所有
                safe_list.extend(batch)
                
        return safe_list

    def get_rps_gold_stocks(self, top_n: int = 10, stock_list: Optional[List[str]] = None) -> List[StockRecommendation]:
        """获取 RPS 强势股 (RPS > 90)"""
        target_list = stock_list or self.stock_list
        if target_list:
            logger.info(f"正在筛选 RPS 强势股 (自选股模式: {len(target_list)}只)...")
        else:
            logger.info("正在筛选 RPS 强势股 (全市场模式)...")
        
        rps_results = self.rps_ranker.get_top_rps_stocks(
            top_n=top_n * 2, 
            min_rps=90,
            stock_list=target_list
        )
        
        recommendations = []
        for rps_res in rps_results[:top_n]:
             rec = StockRecommendation(
                 code=rps_res.code,
                 name=rps_res.name,
                 sector="RPS强势",
                 current_price=rps_res.current_price,
                 change_pct=rps_res.change_pct,
                 signal_score=int(rps_res.rps_60d),
                 reasons=[f"RPS:{rps_res.rps_60d:.1f}, 60日涨幅:{rps_res.change_60d:.1f}%", "市场领先者"],
                 operation_advice="关注回调买点",
                 buy_signal="关注"
             )
             recommendations.append(rec)
        return recommendations

    def get_hot_theme_stocks(self, top_n: int = 5) -> Dict[str, List[StockRecommendation]]:
        """获取热门题材股"""
        logger.info("正在挖掘热门题材股...")
        themes = self.theme_hunter.hunt_themes(top_n=3)
        
        theme_stocks = {}
        for theme in themes:
            recs = []
            for stock in theme.stocks[:top_n]:
                 rec = StockRecommendation(
                     code=stock['code'],
                     name=stock['name'],
                     sector=theme.name,
                     reasons=[f"题材:{theme.name}", theme.description[:10]+"..."],
                     operation_advice="题材概念",
                     buy_signal="关注"
                 )
                 recs.append(rec)
            if recs:
                theme_stocks[theme.name] = recs
        return theme_stocks

    def run_full_analysis(self, 
                         sector_top_n: int = 10, 
                         stock_top_n: int = 5,
                         stock_list: Optional[List[str]] = None,
                         use_watchlist_only: bool = True) -> Dict[str, Any]:
        """
        执行完整的板块选股分析
        
        Args:
            sector_top_n: 分析的板块数量
            stock_top_n: 每个板块推荐的股票数量
            stock_list: 关注的股票列表（None使用默认自选股）
            use_watchlist_only: 是否只从自选股中筛选（避免全量请求）
        """
        target_list = stock_list or self.stock_list
        logger.info("=" * 60)
        logger.info(f"开始执行完整的板块选股分析 (模式: {'自选股' if use_watchlist_only and target_list else '全市场'})")
        logger.info(f"关注股票数量: {len(target_list) if target_list else '全市场'}")
        logger.info("=" * 60)
        
        # 1. 分析板块
        sectors = self.analyze_sectors(top_n=sector_top_n)
        
        # 1.1 RPS 选股 (支持自选股模式)
        rps_stocks = self.get_rps_gold_stocks(top_n=5, stock_list=target_list)
        
        # 1.2 题材选股 (保持全市场模式，因为题材需要热点)
        theme_stocks_map = self.get_hot_theme_stocks(top_n=3)
        
        # 2. 从每个板块推荐个股（支持自选股模式）
        recommendations_by_sector = {}
        all_recommendations = []
        
        for sector in sectors[:5]:
            stocks = self.recommend_stocks_from_sector(
                sector, 
                top_n=stock_top_n,
                use_watchlist_only=use_watchlist_only
            )
            if stocks:
                recommendations_by_sector[sector.name] = stocks
                all_recommendations.extend(stocks)
        
        # 合并 RPS 和 题材股 到结果中
        if rps_stocks:
            recommendations_by_sector['★全市场RPS精选'] = rps_stocks
            all_recommendations.extend(rps_stocks)
            
        for theme, stocks in theme_stocks_map.items():
            recommendations_by_sector[f'🔥题材:{theme}'] = stocks
            all_recommendations.extend(stocks)
        
        # 3. 生成摘要
        summary = self._generate_summary(sectors, all_recommendations)
        
        result = {
            'sectors': [s.to_dict() for s in sectors],
            'recommendations_by_sector': {
                sector_name: [s.to_dict() for s in stocks]
                for sector_name, stocks in recommendations_by_sector.items()
            },
            'all_recommendations': [s.to_dict() for s in all_recommendations],
            'summary': summary,
            'analysis_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # 4. 自动保存结果 (新功能)
        self._save_analysis_result(result)
        
        logger.info("=" * 60)
        logger.info("板块选股分析完成")
        logger.info("=" * 60)
        
        return result

    def _save_analysis_result(self, result: Dict[str, Any]):
        """保存分析结果到文件系统"""
        import os
        import json
        try:
            # 确保目录存在
            save_dir = os.path.join(os.getcwd(), 'data', 'history')
            os.makedirs(save_dir, exist_ok=True)
            
            # 文件名: recommendation_YYYYMMDD.json
            filename = f"recommendation_{datetime.now().strftime('%Y%m%d')}.json"
            filepath = os.path.join(save_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
                
            logger.info(f"分析结果已自动归档: {filepath}")
        except Exception as e:
            logger.error(f"保存分析结果失败: {e}")
    
    def _generate_summary(self, 
                         sectors: List[SectorInfo], 
                         recommendations: List[StockRecommendation]) -> Dict[str, Any]:
        """
        生成分析摘要
        
        Args:
            sectors: 板块列表
            recommendations: 个股推荐列表
            
        Returns:
            摘要字典
        """
        # 统计信息
        strong_buy_count = sum(1 for r in recommendations if r.buy_signal == BuySignal.STRONG_BUY.value)
        buy_count = sum(1 for r in recommendations if r.buy_signal == BuySignal.BUY.value)
        avg_score = np.mean([r.signal_score for r in recommendations]) if recommendations else 0
        
        # 最佳板块
        best_sector = sectors[0] if sectors else None
        
        summary = {
            'total_sectors_analyzed': len(sectors),
            'total_stocks_recommended': len(recommendations),
            'strong_buy_count': strong_buy_count,
            'buy_count': buy_count,
            'average_score': round(avg_score, 1),
            'best_sector': best_sector.name if best_sector else None,
            'best_sector_score': best_sector.potential_score if best_sector else 0
        }
        
        return summary
    
    def format_report(self, result: Dict[str, Any]) -> str:
        """
        格式化分析报告为文本
        
        Args:
            result: 分析结果
            
        Returns:
            格式化的报告文本
        """
        lines = []
        lines.append("=" * 80)
        lines.append("📊 板块选股分析报告")
        lines.append("=" * 80)
        lines.append(f"分析时间: {result['analysis_time']}")
        lines.append("")
        
        # 摘要
        summary = result['summary']
        lines.append("📈 分析摘要")
        lines.append("-" * 80)
        lines.append(f"分析板块数: {summary['total_sectors_analyzed']}")
        lines.append(f"推荐个股数: {summary['total_stocks_recommended']}")
        lines.append(f"强烈买入: {summary['strong_buy_count']} 只")
        lines.append(f"建议买入: {summary['buy_count']} 只")
        lines.append(f"平均评分: {summary['average_score']}")
        lines.append(f"最佳板块: {summary['best_sector']} (评分: {summary['best_sector_score']:.1f})")
        lines.append("")
        
        # 潜力板块
        lines.append("🎯 潜力板块 TOP 5")
        lines.append("-" * 80)
        for i, sector in enumerate(result['sectors'][:5], 1):
            lines.append(f"{i}. {sector['name']}")
            lines.append(f"   潜力评级: {sector['potential']} | 评分: {sector['potential_score']:.1f}")
            lines.append(f"   今日涨幅: {sector['change_pct']:.2f}% | 资金流入: {sector['money_flow']:.1f}亿")
            lines.append(f"   推荐理由: {', '.join(sector['reasons'][:3])}")
            lines.append("")
        
        # 个股推荐
        lines.append("💎 优质个股推荐")
        lines.append("-" * 80)
        
        for sector_name, stocks in result['recommendations_by_sector'].items():
            lines.append(f"\n【{sector_name}】")
            for i, stock in enumerate(stocks, 1):
                lines.append(f"{i}. {stock['code']} {stock['name']}")
                lines.append(f"   买入信号: {stock['buy_signal']} | 评分: {stock['signal_score']}")
                lines.append(f"   当前价格: {stock['current_price']:.2f} | 今日涨跌: {stock['change_pct']:.2f}%")
                lines.append(f"   趋势状态: {stock['trend_status']} | MACD: {stock['macd_status']}")
                lines.append(f"   操作建议: {stock['operation_advice']}")
                if stock['target_price'] > 0:
                    lines.append(f"   目标价位: {stock['target_price']:.2f} | 止损价位: {stock['stop_loss']:.2f}")
                lines.append(f"   推荐理由: {', '.join(stock['reasons'][:3])}")
                if stock['risks']:
                    lines.append(f"   ⚠️  风险提示: {', '.join(stock['risks'][:2])}")
                lines.append("")
        
        lines.append("=" * 80)
        lines.append("⚠️  免责声明：本报告仅供参考，不构成投资建议。投资有风险，入市需谨慎。")
        lines.append("=" * 80)
        
        return '\n'.join(lines)


# 测试入口
if __name__ == "__main__":
    import sys
    sys.path.insert(0, '.')
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s',
    )
    
    # 创建选股器
    picker = SectorStockPicker()
    
    # 执行完整分析
    result = picker.run_full_analysis(sector_top_n=10, stock_top_n=3)
    
    # 打印报告
    report = picker.format_report(result)
    print(report)
