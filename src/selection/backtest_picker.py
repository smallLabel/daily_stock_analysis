# -*- coding: utf-8 -*-
"""
===================================
选股回测系统 - 增量更新 + 板块选股 + 历史回测
===================================

功能：
1. 增量更新股票数据（跳过周末、节假日、停牌日）
2. 潜力板块筛选
3. 板块内选股（每板块5只）
4. 一年期历史回测评分
5. 选出评分最高的5只股票
6. 数据持久化存储

核心流程：
1. 获取潜力板块列表
2. 从每个板块筛选5只候选股
3. 增量更新候选股的1年历史数据
4. 对每只股票进行多策略回测
5. 综合评分排序，选出Top 5
6. 保存结果到数据库
"""

import logging
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import numpy as np

from data_provider import DataFetcherManager
from src.storage import get_db, StockDaily
from src.strategies.backtester import Backtester, StrategySelector
from src.strategies.strategies import (
    MacdStrategy, RsiMeanReversionStrategy, 
    MaTrendStrategy, BollingerStrategy, KDJStrategy
)
from src.config import get_config

logger = logging.getLogger(__name__)

CHINA_HOLIDAYS = [
    '2024-01-01', '2024-02-09', '2024-02-10', '2024-02-11', '2024-02-12',
    '2024-02-13', '2024-02-14', '2024-02-15', '2024-02-16', '2024-02-17',
    '2024-04-04', '2024-04-05', '2024-04-06',
    '2024-05-01', '2024-05-02', '2024-05-03', '2024-05-04',
    '2024-06-08', '2024-06-09', '2024-06-10',
    '2024-09-15', '2024-09-16', '2024-09-17',
    '2024-10-01', '2024-10-02', '2024-10-03', '2024-10-04', '2024-10-05', '2024-10-06', '2024-10-07',
    '2025-01-01', '2025-01-28', '2025-01-29', '2025-01-30', '2025-01-31',
    '2025-02-01', '2025-02-02', '2025-02-03', '2025-02-04',
    '2025-04-04', '2025-04-05',
    '2025-05-01', '2025-05-02', '2025-05-03', '2025-05-04',
    '2025-05-31', '2025-06-01', '2025-06-02',
    '2025-10-01', '2025-10-02', '2025-10-03', '2025-10-04', '2025-10-05', '2025-10-06', '2025-10-07',
]

DEFAULT_CONCEPT_BOARDS = [
    '人工智能', '芯片概念', '新能源汽车', '光伏概念', '锂电池',
    '5G概念', '大数据', '云计算', '机器人概念', '军工概念',
    '医药概念', '消费电子', '半导体概念', '新能源车', '数字经济'
]


def is_trading_day(check_date: date) -> bool:
    """判断是否为交易日（排除周末和节假日）"""
    if check_date.weekday() >= 5:
        return False
    if check_date.strftime('%Y-%m-%d') in CHINA_HOLIDAYS:
        return False
    return True


def get_last_trading_day(target_date: date) -> date:
    """获取目标日期之前的最后一个交易日"""
    delta = 1
    while True:
        check = target_date - timedelta(days=delta)
        if is_trading_day(check):
            return check
        delta += 1


def get_next_trading_day(target_date: date) -> date:
    """获取目标日期之后的第一个交易日"""
    delta = 1
    while True:
        check = target_date + timedelta(days=delta)
        if is_trading_day(check):
            return check
        delta += 1


@dataclass
class BacktestResult:
    """单只股票回测结果"""
    code: str
    name: str
    sector: str
    total_return: float = 0.0
    win_rate: float = 0.0
    total_trades: int = 0
    max_drawdown: float = 0.0
    score: float = 0.0
    strategy_name: str = ""
    latest_price: float = 0.0
    change_pct: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'code': self.code,
            'name': self.name,
            'sector': self.sector,
            'total_return': self.total_return,
            'win_rate': self.win_rate,
            'total_trades': self.total_trades,
            'max_drawdown': self.max_drawdown,
            'score': self.score,
            'strategy_name': self.strategy_name,
            'latest_price': self.latest_price,
            'change_pct': self.change_pct
        }


@dataclass
class SectorCandidate:
    """板块候选股"""
    code: str
    name: str
    sector: str
    current_price: float = 0.0
    change_pct: float = 0.0
    rps_60d: float = 0.0
    volume_ratio: float = 0.0
    reason: str = ""


class StockDataManager:
    """股票数据管理器 - 支持增量更新"""
    
    def __init__(self, data_manager: Optional[DataFetcherManager] = None):
        self.data_manager = data_manager or DataFetcherManager()
        self.db = get_db()
    
    def get_stock_data(
        self, 
        code: str, 
        days: int = 365,
        force_full: bool = False
    ) -> pd.DataFrame:
        """
        获取股票数据（支持增量更新）
        
        Args:
            code: 股票代码
            days: 需要的天数
            force_full: 强制全量获取（忽略数据库）
            
        Returns:
            DataFrame: 包含日线数据的DataFrame
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=days * 2)
        
        if not force_full:
            local_data = self.db.get_data_range(code, start_date, end_date)
            
            if len(local_data) >= days:
                df = self._convert_to_dataframe(local_data)
                logger.info(f"[{code}] 使用数据库数据: {len(df)} 条")
                return df.iloc[-days:]
            
            if local_data:
                last_date = local_data[-1].date
                logger.info(f"[{code}] 数据库有 {len(local_data)} 条，从 {last_date} 开始增量更新")
                return self._increment_update(code, last_date, end_date)
        
        return self._full_update(code, start_date, end_date)
    
    def _convert_to_dataframe(self, records: List[StockDaily]) -> pd.DataFrame:
        """将数据库记录转换为DataFrame"""
        if not records:
            return pd.DataFrame()
        
        data = [{
            'date': r.date,
            'open': r.open,
            'high': r.high,
            'low': r.low,
            'close': r.close,
            'volume': r.volume,
            'amount': r.amount,
            'pct_chg': r.pct_chg,
            'ma5': r.ma5,
            'ma10': r.ma10,
            'ma20': r.ma20,
            'volume_ratio': r.volume_ratio
        } for r in records]
        
        df = pd.DataFrame(data)
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        return df
    
    def _increment_update(
        self, 
        code: str, 
        last_db_date: date, 
        end_date: date
    ) -> pd.DataFrame:
        """增量更新数据"""
        next_day = get_next_trading_day(last_db_date)
        
        if next_day > end_date:
            return self._convert_to_dataframe(
                self.db.get_data_range(code, end_date - timedelta(days=365), end_date)
            )
        
        logger.info(f"[{code}] 增量更新: {next_day} -> {end_date}")
        
        try:
            df = self.data_manager.get_daily_data(code, start_date=next_day.strftime('%Y-%m-%d'))
            if df is not None and not df.empty:
                df = self._prepare_data(df)
                self.db.save_daily_data(df, code, self.data_manager.__class__.__name__)
                logger.info(f"[{code}] 增量更新成功，新增 {len(df)} 条")
        except Exception as e:
            logger.warning(f"[{code}] 增量更新失败: {e}")
        
        return self._convert_to_dataframe(
            self.db.get_data_range(code, end_date - timedelta(days=365), end_date)
        )
    
    def _full_update(self, code: str, start_date: date, end_date: date) -> pd.DataFrame:
        """全量更新数据"""
        logger.info(f"[{code}] 全量更新: {start_date} -> {end_date}")
        
        try:
            df = self.data_manager.get_daily_data(code, days=500)
            if df is not None and not df.empty:
                df = self._prepare_data(df)
                self.db.save_daily_data(df, code, self.data_manager.__class__.__name__)
                logger.info(f"[{code}] 全量更新成功，保存 {len(df)} 条")
                return df[df.index >= pd.Timestamp(start_date)]
        except Exception as e:
            logger.error(f"[{code}] 全量更新失败: {e}")
        
        return pd.DataFrame()
    
    def _prepare_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """准备数据，计算技术指标"""
        df = df.copy()
        
        if 'date' not in df.columns and df.index.dtype != 'datetime64[ns]':
            df.reset_index(inplace=True)
        
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)
        
        df = df[~df.index.duplicated(keep='first')]
        df.sort_index(inplace=True)
        
        if len(df) >= 5:
            df['ma5'] = df['close'].rolling(5).mean()
        if len(df) >= 10:
            df['ma10'] = df['close'].rolling(10).mean()
        if len(df) >= 20:
            df['ma20'] = df['close'].rolling(20).mean()
        
        if len(df) >= 2:
            vol_5d = df['volume'].iloc[-6:-1].mean()
            if vol_5d > 0:
                df['volume_ratio'] = df['volume'] / vol_5d
        
        return df


class PotentialSectorPicker:
    """潜力板块筛选器 - 使用Efinance概念板块数据"""
    
    def __init__(self, data_manager: Optional[DataFetcherManager] = None):
        self.data_manager = data_manager or DataFetcherManager()
        from src.storage import get_db
        self.db = get_db()
    
    def get_potential_sectors(self, top_n: int = 10) -> List[Dict[str, Any]]:
        """
        获取潜力板块（Efinance概念板块）
        
        Args:
            top_n: 返回前N个板块
            
        Returns:
            板块列表
        """
        try:
            # 1. 检查数据库中是否有板块数据且不需要更新
            db_sectors = self.db.get_all_sectors()
            if db_sectors and len(db_sectors) >= top_n:
                # 检查是否所有板块都不需要更新
                need_update = False
                for sector in db_sectors[:top_n]:
                    if self.db.is_sector_data_needs_update(sector.code):
                        need_update = True
                        break
                
                if not need_update:
                    logger.info(f"使用数据库中的板块数据，共 {len(db_sectors)} 个板块")
                    return [
                        {
                            'name': s.name,
                            'code': s.code,
                            'change_pct': s.change_pct,
                            'stock_count': s.stock_count,
                            'potential_score': s.potential_score
                        }
                        for s in db_sectors[:top_n]
                    ]
            
            # 2. 从API获取板块数据
            import efinance as ef
            
            concepts = ef.stock.get_belong_plate_stock()
            
            if concepts is not None and len(concepts) > 0:
                sector_stats = {}
                
                for _, row in concepts.iterrows():
                    code = row.get('代码', '')
                    name = row.get('名称', '')
                    plates = row.get('所属板块', '')
                    
                    if not plates or pd.isna(plates):
                        continue
                    
                    for plate in str(plates).split(','):
                        plate = plate.strip()
                        if not plate:
                            continue
                            
                        if plate not in sector_stats:
                            sector_stats[plate] = {'stocks': [], 'total_change': 0}
                        
                        sector_stats[plate]['stocks'].append({
                            'code': code,
                            'name': name
                        })
                
                scored_sectors = []
                for name, data in sector_stats.items():
                    sector_data = {
                        'name': name,
                        'code': name,
                        'change_pct': 0,
                        'stock_count': len(data['stocks']),
                        'potential_score': len(data['stocks'])
                    }
                    scored_sectors.append(sector_data)
                    
                    # 保存板块信息到数据库
                    self.db.save_sector_info(sector_data)
                    
                    # 保存成分股到数据库
                    components = [
                        {'code': stock['code'], 'name': stock['name']}
                        for stock in data['stocks']
                    ]
                    self.db.save_sector_components(name, components)
                
                scored_sectors.sort(key=lambda x: x.get('stock_count', 0), reverse=True)
                logger.info(f"筛选出 {len(scored_sectors)} 个概念板块，并保存到数据库")
                return scored_sectors[:top_n]
            
            logger.warning("未能获取概念板块数据")
            return []
            
        except Exception as e:
            logger.error(f"获取概念板块失败: {e}")
            
            logger.info("使用默认概念板块列表")
            sectors = []
            for name in DEFAULT_CONCEPT_BOARDS[:top_n]:
                sector_data = {
                    'name': name,
                    'code': name,
                    'change_pct': 0,
                    'stock_count': 50,
                    'potential_score': 0
                }
                sectors.append(sector_data)
                # 保存默认板块到数据库
                self.db.save_sector_info(sector_data)
            return sectors


class SectorStockSelector:
    """板块内选股器 - 使用Efinance概念板块"""
    
    def __init__(self, data_manager: Optional[DataFetcherManager] = None):
        self.data_manager = data_manager or DataFetcherManager()
        from src.storage import get_db
        self.db = get_db()
        self._concept_stocks_cache = {}
    
    def select_stocks_from_sector(
        self, 
        sector_name: str, 
        top_n: int = 5,
        stock_list: Optional[List[str]] = None
    ) -> List[SectorCandidate]:
        """
        从板块中筛选优质股票
        
        Args:
            sector_name: 板块名称
            top_n: 返回数量
            stock_list: 限定的股票列表（None则全市场选）
            
        Returns:
            候选股票列表
        """
        try:
            sector_stocks = self._get_concept_stocks(sector_name)
            
            if stock_list:
                sector_stocks = [s for s in sector_stocks if s in stock_list]
                logger.info(f"[{sector_name}] 限定自选股: {len(sector_stocks)} 只")
            
            if not sector_stocks:
                return []
            
            candidates = []
            batch_size = 20
            for i in range(0, min(len(sector_stocks), 50), batch_size):
                batch = sector_stocks[i:i+batch_size]
                
                try:
                    for code in batch:
                        quote = self.data_manager.get_realtime_quote(code)
                        if quote and quote.has_basic_data():
                            name = quote.name
                            if 'ST' in name.upper():
                                continue
                            
                            price = getattr(quote, 'price', 0)
                            if price < 3:
                                continue
                            
                            candidate = SectorCandidate(
                                code=code,
                                name=name,
                                sector=sector_name,
                                current_price=price,
                                change_pct=getattr(quote, 'change_pct', 0),
                                rps_60d=getattr(quote, 'change_60d', 0),
                                volume_ratio=getattr(quote, 'volume_ratio', 0)
                            )
                            candidates.append(candidate)
                except Exception as e:
                    logger.debug(f"获取 {batch} 行情失败: {e}")
                    continue
            
            candidates.sort(key=lambda x: x.rps_60d, reverse=True)
            logger.info(f"[{sector_name}] 筛选出 {len(candidates)} 只候选股")
            
            return candidates[:top_n]
            
        except Exception as e:
            logger.error(f"从板块 {sector_name} 选股失败: {e}")
            return []
    
    def _get_concept_stocks(self, sector_name: str) -> List[str]:
        """获取概念板块的成分股（优先从数据库获取）"""
        if sector_name in self._concept_stocks_cache:
            return self._concept_stocks_cache[sector_name]
        
        # 1. 优先从数据库获取成分股
        db_codes = self.db.get_sector_stock_codes(sector_name)
        if db_codes and len(db_codes) > 0:
            # 检查板块数据是否需要更新
            if not self.db.is_sector_data_needs_update(sector_name):
                self._concept_stocks_cache[sector_name] = db_codes
                logger.info(f"[{sector_name}] 从数据库获取到 {len(db_codes)} 只成分股")
                return db_codes
        
        # 2. 从Efinance获取成分股
        try:
            import efinance as ef
            
            concepts = ef.stock.get_belong_plate_stock()
            
            if concepts is not None and len(concepts) > 0:
                codes = []
                components = []
                
                for _, row in concepts.iterrows():
                    code = row.get('代码', '')
                    name = row.get('名称', '')
                    plates = row.get('所属板块', '')
                    
                    if plates and not pd.isna(plates):
                        if sector_name in str(plates):
                            if code:
                                stock_code = str(code).zfill(6)
                                codes.append(stock_code)
                                components.append({
                                    'code': stock_code,
                                    'name': name
                                })
                
                # 保存成分股到数据库
                if components:
                    self.db.save_sector_components(sector_name, components)
                    logger.info(f"[{sector_name}] 从Efinance获取到 {len(codes)} 只成分股并保存到数据库")
                else:
                    logger.info(f"[{sector_name}] 从Efinance获取到 {len(codes)} 只成分股")
                
                self._concept_stocks_cache[sector_name] = codes
                return codes
                
        except Exception as e:
            logger.warning(f"Efinance获取概念板块 {sector_name} 成分股失败: {e}")
        
        # 3. 如果数据库中有数据，即使需要更新也返回（避免完全失败）
        if db_codes:
            logger.info(f"[{sector_name}] 使用数据库中的成分股数据（需要更新）")
            self._concept_stocks_cache[sector_name] = db_codes
            return db_codes
        
        return []


class BacktestScorer:
    """回测评分器"""
    
    def __init__(self):
        self.backtester = Backtester()
        self.strategies = [
            MacdStrategy(),
            RsiMeanReversionStrategy(),
            MaTrendStrategy(),
            BollingerStrategy(),
            KDJStrategy()
        ]
        self.selector = StrategySelector(self.strategies)
    
    def backtest_stock(
        self, 
        code: str, 
        name: str, 
        sector: str,
        days: int = 250
    ) -> Optional[BacktestResult]:
        """
        对单只股票进行回测评分
        
        Args:
            code: 股票代码
            name: 股票名称
            sector: 所属板块
            days: 回测天数
            
        Returns:
            回测结果
        """
        data_manager = StockDataManager()
        df = data_manager.get_stock_data(code, days=days)
        
        if df is None or len(df) < 60:
            logger.warning(f"[{code}] 数据不足，无法回测")
            return None
        
        try:
            best_strategy, result = self.selector.pick_best_strategy(df)
            
            max_dd = self._calculate_max_drawdown(df)
            
            raw_score = result['total_return'] * 0.4 + result['win_rate'] * 0.3
            if result['total_trades'] >= 10:
                trade_bonus = min(result['total_trades'] / 30, 0.2)
            else:
                trade_bonus = result['total_trades'] / 50 * 0.1
            
            final_score = raw_score + trade_bonus - abs(max_dd) * 0.5
            
            quote = data_manager.data_manager.get_realtime_quote(code)
            latest_price = getattr(quote, 'price', df['close'].iloc[-1]) if quote else df['close'].iloc[-1]
            change_pct = getattr(quote, 'change_pct', 0) if quote else df['pct_chg'].iloc[-1] if 'pct_chg' in df.columns else 0
            
            return BacktestResult(
                code=code,
                name=name,
                sector=sector,
                total_return=result['total_return'],
                win_rate=result['win_rate'],
                total_trades=result['total_trades'],
                max_drawdown=max_dd,
                score=final_score,
                strategy_name=best_strategy.name,
                latest_price=latest_price,
                change_pct=change_pct
            )
            
        except Exception as e:
            logger.error(f"[{code}] 回测失败: {e}")
            return None
    
    def _calculate_max_drawdown(self, df: pd.DataFrame) -> float:
        """计算最大回撤"""
        if 'close' not in df.columns:
            return 0
        
        prices = df['close'].values
        if len(prices) < 2:
            return 0
        
        max_price = prices[0]
        max_dd = 0
        
        for price in prices:
            if price > max_price:
                max_price = price
            dd = (max_price - price) / max_price
            if dd > max_dd:
                max_dd = dd
        
        return max_dd
    
    def backtest_batch(
        self, 
        candidates: List[SectorCandidate],
        max_workers: int = 3
    ) -> List[BacktestResult]:
        """批量回测"""
        results = []
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(self.backtest_stock, c.code, c.name, c.sector): c 
                for c in candidates
            }
            
            for future in as_completed(futures):
                try:
                    result = future.result()
                    if result:
                        results.append(result)
                        logger.info(f"[{result.code}] 回测完成: 收益率{result.total_return:.1f}%, 胜率{result.win_rate:.0f}%, 综合{result.score:.1f}")
                except Exception as e:
                    logger.error(f"回测任务失败: {e}")
        
        return results


class StockPickerWithBacktest:
    """选股回测主类 - 整合所有功能"""
    
    def __init__(self, stock_list: Optional[List[str]] = None):
        self.data_manager = DataFetcherManager()
        self.db = get_db()
        
        if stock_list:
            self.stock_list = stock_list
        else:
            config = get_config()
            config.refresh_stock_list()
            self.stock_list = config.stock_list
        
        self.sector_picker = PotentialSectorPicker(self.data_manager)
        self.stock_selector = SectorStockSelector(self.data_manager)
        self.backtest_scorer = BacktestScorer()
        
        logger.info(f"[选股回测] 初始化，自选股: {len(self.stock_list)} 只")
    
    def run(
        self,
        sector_count: int = 5,
        stocks_per_sector: int = 5,
        backtest_days: int = 250,
        final_top_n: int = 5,
        use_watchlist: bool = True
    ) -> Dict[str, Any]:
        """
        执行完整的选股回测流程
        
        Args:
            sector_count: 分析的板块数量
            stocks_per_sector: 每个板块筛选的股票数
            backtest_days: 回测天数
            final_top_n: 最终选出股票数
            use_watchlist: 是否限定自选股
            
        Returns:
            结果字典
        """
        logger.info("="*60)
        logger.info("开始执行选股回测流程")
        logger.info(f"回测天数: {backtest_days}, 最终选出: {final_top_n} 只")
        logger.info("="*60)
        
        # 直接使用自选股进行回测（不尝试获取板块数据）
        target_list = self.stock_list if use_watchlist else None
        logger.info(f"使用自选股直接回测模式，待回测股票数: {len(target_list) if target_list else '全市场'}")
        
        return self._backtest_stock_list(
            target_list if target_list else self.stock_list,
            backtest_days,
            final_top_n
        )
    
    def _backtest_stock_list(
        self,
        stock_codes: List[str],
        backtest_days: int = 250,
        final_top_n: int = 5
    ) -> Dict[str, Any]:
        """
        直接对股票列表进行回测（当无法获取板块数据时使用）
        
        Args:
            stock_codes: 股票代码列表
            backtest_days: 回测天数
            final_top_n: 最终选出数量
            
        Returns:
            结果字典
        """
        logger.info("="*60)
        logger.info("使用自选股直接回测模式")
        logger.info(f"待回测股票数: {len(stock_codes)}")
        logger.info("="*60)
        
        candidates = []
        data_manager = DataFetcherManager()
        
        for code in stock_codes:
            try:
                quote = data_manager.get_realtime_quote(code)
                if quote and quote.has_basic_data():
                    name = getattr(quote, 'name', code)
                    candidates.append(SectorCandidate(
                        code=code,
                        name=name,
                        sector="自选股",
                        current_price=getattr(quote, 'price', 0),
                        change_pct=getattr(quote, 'change_pct', 0)
                    ))
            except Exception as e:
                logger.debug(f"获取 {code} 行情失败: {e}")
        
        logger.info(f"成功获取 {len(candidates)} 只股票的行情数据")
        
        if not candidates:
            return {'error': '无法获取股票数据'}
        
        logger.info("开始批量回测...")
        backtest_results = self.backtest_scorer.backtest_batch(candidates, max_workers=3)
        
        backtest_results.sort(key=lambda x: x.score, reverse=True)
        top_stocks = backtest_results[:final_top_n]
        
        result = {
            'analysis_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'mode': 'direct_stock_list',
            'stocks_tested': len(backtest_results),
            'top_stocks': [r.to_dict() for r in top_stocks],
            'backtest_days': backtest_days
        }
        
        self._save_result(result)
        
        logger.info("="*60)
        logger.info(f"回测完成！选出 {len(top_stocks)} 只最优股票:")
        for i, stock in enumerate(top_stocks, 1):
            logger.info(f"  {i}. {stock.code} {stock.name} | 评分:{stock.score:.1f} | 收益率:{stock.total_return:.1f}% | 胜率:{stock.win_rate:.0f}%")
        logger.info("="*60)
        
        return result
    
    def _save_result(self, result: Dict[str, Any]):
        """保存结果到数据库"""
        try:
            from sqlalchemy import Column, String, Float, DateTime, Text, Integer
            from sqlalchemy.orm import declarative_base, sessionmaker
            
            LocalBase = declarative_base()
            
            class BacktestResultRecord(LocalBase):
                __tablename__ = 'backtest_results'
                
                id = Column(Integer, primary_key=True, autoincrement=True)
                code = Column(String(10), nullable=False, index=True)
                name = Column(String(50))
                sector = Column(String(50))
                total_return = Column(Float)
                win_rate = Column(Float)
                max_drawdown = Column(Float)
                score = Column(Float, index=True)
                strategy_name = Column(String(50))
                latest_price = Column(Float)
                change_pct = Column(Float)
                analysis_time = Column(DateTime)
                parameters = Column(Text)
            
            engine = self.db._engine
            BacktestResultRecord.__table__.create(engine, checkfirst=True)
            
            with self.db.get_session() as session:
                for stock in result['top_stocks']:
                    record = BacktestResultRecord(
                        code=stock['code'],
                        name=stock['name'],
                        sector=stock['sector'],
                        total_return=stock['total_return'],
                        win_rate=stock['win_rate'],
                        max_drawdown=stock['max_drawdown'],
                        score=stock['score'],
                        strategy_name=stock['strategy_name'],
                        latest_price=stock['latest_price'],
                        change_pct=stock['change_pct'],
                        analysis_time=datetime.now(),
                        parameters=str(result['parameters'])
                    )
                    session.add(record)
                
                session.commit()
                logger.info(f"回测结果已保存到数据库")
                
        except Exception as e:
            logger.warning(f"保存回测结果失败: {e}")


if __name__ == "__main__":
    import sys
    sys.path.insert(0, '.')
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)-8s | %(message)s'
    )
    
    picker = StockPickerWithBacktest()
    
    result = picker.run(
        sector_count=5,
        stocks_per_sector=5,
        backtest_days=250,
        final_top_n=5,
        use_watchlist=False
    )
    
    if 'top_stocks' in result:
        print("\n" + "="*60)
        print("🏆 最终推荐股票:")
        print("="*60)
        for i, stock in enumerate(result['top_stocks'], 1):
            print(f"{i}. {stock['code']} {stock['name']}")
            print(f"   板块: {stock['sector']}")
            print(f"   评分: {stock['score']:.1f} | 收益率: {stock['total_return']:.1f}% | 胜率: {stock['win_rate']:.0f}%")
            print(f"   策略: {stock['strategy_name']}")
            print()
