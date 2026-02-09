# -*- coding: utf-8 -*-
"""
===================================
股票 Repository
===================================

提供股票相关的数据库操作
"""

import logging
import pandas as pd
from datetime import date, datetime
from typing import Optional, List, Dict, Any, Tuple

from sqlalchemy import select, and_, desc
from sqlalchemy.orm import Session

from .base_repo import BaseRepository
from ..models.stock import StockDaily, WatchlistStock, StockBasicInfo

logger = logging.getLogger(__name__)


class StockDailyRepository(BaseRepository[StockDaily]):
    """
    股票日线数据 Repository

    提供股票日线数据的 CRUD 操作
    """

    def __init__(self):
        super().__init__(StockDaily)

    def has_today_data(self, code: str, target_date: Optional[date] = None) -> bool:
        """检查是否已有指定日期的数据"""
        if target_date is None:
            target_date = date.today()

        with self._session_manager.get_session() as session:
            result = session.execute(
                select(StockDaily).where(
                    and_(
                        StockDaily.code == code,
                        StockDaily.date == target_date
                    )
                )
            ).scalar_one_or_none()
            return result is not None

    def get_latest(
        self,
        code: str,
        days: int = 2,
        ascending: bool = False
    ) -> List[StockDaily]:
        """获取最近 N 天的数据"""
        with self._session_manager.get_session() as session:
            order = StockDaily.date.asc() if ascending else StockDaily.date.desc()
            results = session.execute(
                select(StockDaily)
                .where(StockDaily.code == code)
                .order_by(order)
                .limit(days)
            ).scalars().all()
            return list(results)

    def get_data_range(
        self,
        code: str,
        start_date: date,
        end_date: date
    ) -> List[StockDaily]:
        """获取指定日期范围的数据"""
        with self._session_manager.get_session() as session:
            results = session.execute(
                select(StockDaily)
                .where(
                    and_(
                        StockDaily.code == code,
                        StockDaily.date >= start_date,
                        StockDaily.date <= end_date
                    )
                )
                .order_by(StockDaily.date)
            ).scalars().all()
            return list(results)

    def save_daily_data(
        self,
        df: pd.DataFrame,
        code: str,
        data_source: str = "Unknown"
    ) -> int:
        """保存日线数据（UPSERT 逻辑）"""
        if df is None or df.empty:
            logger.warning(f"保存数据为空，跳过 {code}")
            return 0

        saved_count = 0

        with self._session_manager.get_session() as session:
            try:
                for _, row in df.iterrows():
                    row_date = row.get('date')
                    if isinstance(row_date, str):
                        row_date = datetime.strptime(row_date, '%Y-%m-%d').date()
                    elif isinstance(row_date, datetime):
                        row_date = row_date.date()
                    elif isinstance(row_date, pd.Timestamp):
                        row_date = row_date.date()

                    existing = session.execute(
                        select(StockDaily).where(
                            and_(
                                StockDaily.code == code,
                                StockDaily.date == row_date
                            )
                        )
                    ).scalar_one_or_none()

                    if existing:
                        existing.open = row.get('open')
                        existing.high = row.get('high')
                        existing.low = row.get('low')
                        existing.close = row.get('close')
                        existing.volume = row.get('volume')
                        existing.amount = row.get('amount')
                        existing.pct_chg = row.get('pct_chg')
                        existing.ma5 = row.get('ma5')
                        existing.ma10 = row.get('ma10')
                        existing.ma20 = row.get('ma20')
                        existing.volume_ratio = row.get('volume_ratio')
                        existing.data_source = data_source
                        existing.updated_at = datetime.now()
                    else:
                        record = StockDaily(
                            code=code,
                            date=row_date,
                            open=row.get('open'),
                            high=row.get('high'),
                            low=row.get('low'),
                            close=row.get('close'),
                            volume=row.get('volume'),
                            amount=row.get('amount'),
                            pct_chg=row.get('pct_chg'),
                            ma5=row.get('ma5'),
                            ma10=row.get('ma10'),
                            ma20=row.get('ma20'),
                            volume_ratio=row.get('volume_ratio'),
                            data_source=data_source,
                        )
                        session.add(record)
                        saved_count += 1

                session.commit()
                logger.info(f"保存 {code} 数据成功，新增 {saved_count} 条")

            except Exception as e:
                session.rollback()
                logger.error(f"保存 {code} 数据失败: {e}")
                raise

        return saved_count

    def get_analysis_context(
        self,
        code: str,
        target_date: Optional[date] = None
    ) -> Optional[Dict[str, Any]]:
        """获取分析所需的上下文数据"""
        if target_date is None:
            target_date = date.today()

        recent_data = self.get_latest(code, days=2, ascending=True)

        if not recent_data:
            logger.warning(f"未找到 {code} 的数据")
            return None

        today_data = recent_data[-1]
        yesterday_data = recent_data[0] if len(recent_data) > 1 else None

        context = {
            'code': code,
            'date': today_data.date.isoformat(),
            'today': today_data.to_dict(),
        }

        if yesterday_data:
            context['yesterday'] = yesterday_data.to_dict()

            if yesterday_data.volume and yesterday_data.volume > 0:
                context['volume_change_ratio'] = round(
                    today_data.volume / yesterday_data.volume, 2
                )

            if yesterday_data.close and yesterday_data.close > 0:
                context['price_change_ratio'] = round(
                    (today_data.close - yesterday_data.close) / yesterday_data.close * 100, 2
                )

            context['ma_status'] = self._analyze_ma_status(today_data)

        return context

    def _analyze_ma_status(self, data: StockDaily) -> str:
        """分析均线形态"""
        close = data.close or 0
        ma5 = data.ma5 or 0
        ma10 = data.ma10 or 0
        ma20 = data.ma20 or 0

        if close > ma5 > ma10 > ma20 > 0:
            return "多头排列"
        elif close < ma5 < ma10 < ma20 and ma20 > 0:
            return "空头排列"
        elif close > ma5 and ma5 > ma10:
            return "短期向好"
        elif close < ma5 and ma5 < ma10:
            return "短期走弱"
        else:
            return "震荡整理"
    def save_daily_data_batch(
        self,
        df: pd.DataFrame,
        data_source: str = "Unknown"
    ) -> int:
        """
        批量保存多只股票的日线数据（支持快照保存）
        
        Args:
            df: DataFrame，必须包含 'code' 列
        """
        if df is None or df.empty:
            return 0
            
        if 'code' not in df.columns:
            logger.error("批量保存失败：DataFrame 缺少 'code' 列")
            return 0

        saved_count = 0
        
        # 预处理日期
        df = df.copy()
        if 'date' not in df.columns:
             df['date'] = datetime.now().date()
        else:
             df['date'] = pd.to_datetime(df['date']).dt.date

        with self._session_manager.get_session() as session:
            try:
                # 能够优化的点：先查出现有的 (code, date) 集合，然后决定 insert 还是 update
                # 但这里为了简单稳健，先循环处理
                # 对于 5000 条数据，循环 SQLAlchemy ORM 比较慢，最好是用 Core
                # 使用 Core 的 bulk upsert
                
                # 转换 DF 为字典列表
                records = df.to_dict('records')
                
                # Performance Optimization:
                # 1. Fetch all existing records for the given dates and codes in one query
                #    (Since we usually save for a single date (today), this is efficient)
                
                target_dates = list(set(r['date'] for r in records))
                target_codes = list(set(str(r.get('code')) for r in records))
                
                # If too many codes, we might need to chunk, but for 5000 it's usually fine for IN clause in many DBs
                # SQLite limit is default 999 variables, so we MUST chunk the select if we filter by code.
                # However, if we filter by DATE only (which is usually just today), it's much faster and safer.
                
                existing_map = {}
                
                # Chunking logic for safety (SQLite 999 limit)
                chunk_size = 500
                for i in range(0, len(target_codes), chunk_size):
                    chunk_codes = target_codes[i:i + chunk_size]
                    stmt = select(StockDaily).where(
                        and_(
                            StockDaily.date.in_(target_dates),
                            StockDaily.code.in_(chunk_codes)
                        )
                    )
                    chunk_results = session.execute(stmt).scalars().all()
                    for r in chunk_results:
                        existing_map[(r.code, r.date)] = r

                new_objects = []
                
                for row in records:
                    code = str(row.get('code'))
                    row_date = row.get('date')
                    key = (code, row_date)
                    
                    val_open = row.get('open')
                    val_high = row.get('high')
                    val_low = row.get('low')
                    val_close = row.get('close')
                    val_volume = row.get('volume')
                    val_amount = row.get('amount')
                    val_pct_chg = row.get('pct_chg')
                    
                    if key in existing_map:
                        # Update existing object
                        existing = existing_map[key]
                        existing.open = val_open
                        existing.high = val_high
                        existing.low = val_low
                        existing.close = val_close
                        existing.pre_close = row.get('pre_close')
                        existing.change_amount = row.get('change_amount')
                        existing.pct_chg = val_pct_chg
                        existing.amplitude = row.get('amplitude')
                        existing.volume = val_volume
                        existing.amount = val_amount
                        existing.volume_ratio = row.get('volume_ratio')
                        existing.turnover_rate = row.get('turnover_rate')
                        existing.ma5 = row.get('ma5')
                        existing.ma10 = row.get('ma10')
                        existing.ma20 = row.get('ma20')
                        existing.pe = row.get('pe')
                        existing.pb = row.get('pb')
                        existing.total_mv = row.get('total_mv')
                        existing.circ_mv = row.get('circ_mv')
                        existing.change_60d = row.get('change_60d')
                        existing.change_ytd = row.get('change_ytd')
                        existing.data_source = data_source
                        existing.updated_at = datetime.now()
                    else:
                        # Prepare for bulk insert
                        # Note: session.add_all is faster than add() loop, but bulk_save_objects is fastest (Core)
                        # Here use ORM object creation for simplicity with session.add later
                        record = StockDaily(
                            code=code,
                            date=row_date,
                            open=val_open,
                            high=val_high,
                            low=val_low,
                            close=val_close,
                            pre_close=row.get('pre_close'),
                            change_amount=row.get('change_amount'),
                            pct_chg=val_pct_chg,
                            amplitude=row.get('amplitude'),
                            volume=val_volume,
                            amount=val_amount,
                            volume_ratio=row.get('volume_ratio'),
                            turnover_rate=row.get('turnover_rate'),
                            ma5=row.get('ma5'),
                            ma10=row.get('ma10'),
                            ma20=row.get('ma20'),
                            pe=row.get('pe'),
                            pb=row.get('pb'),
                            total_mv=row.get('total_mv'),
                            circ_mv=row.get('circ_mv'),
                            change_60d=row.get('change_60d'),
                            change_ytd=row.get('change_ytd'),
                            data_source=data_source,
                        )
                        new_objects.append(record)
                        
                    saved_count += 1
                
                # Bulk insert new objects
                if new_objects:
                    session.add_all(new_objects)
                    
                session.commit()
                logger.info(f"批量保存成功，共 {saved_count} 条 (更新: {len(existing_map)}, 新增: {len(new_objects)})")
                
            except Exception as e:
                session.rollback()
                logger.error(f"批量保存失败: {e}")
                # 不抛出异常，避免中断流程
                
        return saved_count

    def save_snapshot(self, df: pd.DataFrame) -> int:
        """
        保存市场快照数据（适配 StockDaily）
        
        Args:
            df: get_all_stocks_snapshot 返回的 DataFrame
            
        Returns:
            保存记录数
        """
        if df is None or df.empty:
            return 0
            
        # 转换列名适配
        df_daily = df.copy()
        df_daily['date'] = datetime.now().date()
        
        # 映射 snapshot 列到 stock_daily 列
        # akshare stock_zh_a_spot_em 返回的列名映射
        rename_map = {
            '代码': 'code',
            '名称': 'name',
            '最新价': 'close',
            '涨跌幅': 'pct_chg',
            '涨跌额': 'change_amount',
            '今开': 'open',
            '最高': 'high',
            '最低': 'low',
            '昨收': 'pre_close',
            '振幅': 'amplitude',
            '成交量': 'volume',
            '成交额': 'amount',
            '换手率': 'turnover_rate',
            '量比': 'volume_ratio',
            '市盈率-动态': 'pe',
            '市净率': 'pb',
            '总市值': 'total_mv',
            '流通市值': 'circ_mv',
            '60日涨跌幅': 'change_60d',
            '年初至今涨跌幅': 'change_ytd'
        }
        
        # 重命名列
        df_daily = df_daily.rename(columns=rename_map)
        
        # 确保 code 列存在且为字符串
        if 'code' not in df_daily.columns:
             logger.error("快照数据缺少 code 列")
             return 0
        df_daily['code'] = df_daily['code'].astype(str)
        
        return self.save_daily_data_batch(df_daily, data_source="RealtimeSnapshot")

    def get_latest_batch(self, codes: List[str]) -> Dict[str, StockDaily]:
        """
        批量获取最新日线数据
        
        Args:
            codes: 股票代码列表
            
        Returns:
            {code: StockDaily}
        """
        if not codes:
            return {}
            
        with self._session_manager.get_session() as session:
            # 从 stock_basic_info 表查询数据
            from ..models.stock import StockBasicInfo
            results = session.execute(
                select(StockBasicInfo).where(
                    StockBasicInfo.code.in_(codes)
                )
            ).scalars().all()
            
            data_map = {}
            for basic_info in results:
                # 创建 StockDaily 对象以保持返回类型一致
                stock_daily = StockDaily(
                    code=basic_info.code,
                    date=datetime.now().date(),
                    close=basic_info.price,
                    open=basic_info.price,
                    high=basic_info.price,
                    low=basic_info.price,
                    volume=basic_info.volume,
                    amount=basic_info.amount,
                    pct_chg=basic_info.change_pct,
                    pe=basic_info.pe,
                    pb=basic_info.pb,
                    total_mv=basic_info.total_mv,
                    circ_mv=basic_info.circ_mv,
                    change_60d=basic_info.change_60d,
                    change_ytd=basic_info.change_ytd,
                    data_source="StockBasicInfo"
                )
                data_map[basic_info.code] = stock_daily
            
            # 检查是否有缺失，尝试获取市场全量数据
            missing = [c for c in codes if c not in data_map]
            if missing:
                logger.info(f"Missing data for codes: {missing}, trying to fetch market data")
                # 获取市场全量数据并保存到 stock_basic_info
                try:
                    from ..fetchers.akshare_fetcher import AkshareFetcher
                    
                    # 创建数据获取器
                    fetcher = AkshareFetcher()
                    
                    # 获取全市场数据
                    import akshare as ak
                    import pandas as pd
                    
                    logger.info("Fetching market snapshot data...")
                    df = ak.stock_zh_a_spot_em()
                    
                    if df is not None and not df.empty:
                        logger.info(f"Successfully fetched {len(df)} stocks from market snapshot")
                        
                        # 保存到 stock_basic_info 表
                        basic_repo = StockBasicRepository()
                        if basic_repo.save_all(df):
                            logger.info("Market data saved to stock_basic_info table")
                            
                            # 重新查询 stock_basic_info 表获取更新后的数据
                            updated_results = session.execute(
                                select(StockBasicInfo).where(
                                    StockBasicInfo.code.in_(missing)
                                )
                            ).scalars().all()
                            
                            for basic_info in updated_results:
                                # 创建 StockDaily 对象以保持返回类型一致
                                stock_daily = StockDaily(
                                    code=basic_info.code,
                                    date=datetime.now().date(),
                                    close=basic_info.price,
                                    open=basic_info.price,
                                    high=basic_info.price,
                                    low=basic_info.price,
                                    volume=basic_info.volume,
                                    amount=basic_info.amount,
                                    pct_chg=basic_info.change_pct,
                                    pe=basic_info.pe,
                                    pb=basic_info.pb,
                                    total_mv=basic_info.total_mv,
                                    circ_mv=basic_info.circ_mv,
                                    change_60d=basic_info.change_60d,
                                    change_ytd=basic_info.change_ytd,
                                    data_source="MarketSnapshot"
                                )
                                data_map[basic_info.code] = stock_daily
                        else:
                            logger.error("Failed to save market data to stock_basic_info table")
                    else:
                        logger.warning("Market snapshot data is empty")
                except Exception as e:
                    logger.error(f"Error fetching market data: {e}")
                
            # Detach objects from session to return them safely
            for obj in data_map.values():
                session.expunge(obj)
                
            return data_map

    def get_snapshot_status(self) -> Optional[datetime]:
        """
        获取市场快照数据的最新更新时间
        
        Returns:
            最新更新时间，如果没有快照数据则返回 None
        """
        from sqlalchemy import func
        with self._session_manager.get_session() as session:
            stmt = select(func.max(StockDaily.updated_at)).where(
                StockDaily.data_source == 'RealtimeSnapshot'
            )
            result = session.execute(stmt).scalar()
            return result

class WatchlistRepository(BaseRepository[WatchlistStock]):
    """
    自选股 Repository
    """

    def __init__(self):
        super().__init__(WatchlistStock)

    def _to_dict(self, obj: WatchlistStock) -> Dict[str, Any]:
        """将 ORM 对象转换为字典"""
        return {
            'id': obj.id,
            'stock_code': obj.stock_code,
            'stock_name': obj.stock_name or obj.stock_code,
            'display_order': obj.display_order,
            'created_at': obj.created_at,
            'updated_at': obj.updated_at,
        }

    def get_all(self) -> List[Dict[str, Any]]:
        """获取所有自选股（返回字典列表，避免 Session 问题）"""
        with self._session_manager.get_session() as session:
            results = session.query(WatchlistStock).order_by(
                WatchlistStock.display_order,
                WatchlistStock.stock_code
            ).all()
            return [self._to_dict(r) for r in results]

    def get_codes(self) -> List[str]:
        """获取所有股票代码"""
        with self._session_manager.get_session() as session:
            results = session.query(WatchlistStock.stock_code).order_by(
                WatchlistStock.display_order,
                WatchlistStock.stock_code
            ).all()
            return [r[0] for r in results]

    def get_names_dict(self) -> Dict[str, str]:
        """获取名称映射字典"""
        with self._session_manager.get_session() as session:
            results = session.query(
                WatchlistStock.stock_code,
                WatchlistStock.stock_name
            ).order_by(
                WatchlistStock.display_order,
                WatchlistStock.stock_code
            ).all()
            return {r[0]: r[1] or r[0] for r in results}

    def add(self, stock_code: str, stock_name: str = "") -> bool:
        """添加自选股"""
        try:
            with self._session_manager.get_session() as session:
                existing = session.query(WatchlistStock).filter(
                    WatchlistStock.stock_code == stock_code
                ).first()

                if existing:
                    existing.stock_name = stock_name or stock_code
                    existing.updated_at = datetime.now()
                else:
                    max_order = session.query(
                        WatchlistStock.display_order
                    ).order_by(
                        WatchlistStock.display_order.desc()
                    ).limit(1).scalar() or 0

                    watchlist = WatchlistStock(
                        stock_code=stock_code,
                        stock_name=stock_name or stock_code,
                        display_order=max_order + 1
                    )
                    session.add(watchlist)

                return True
        except Exception as e:
            logger.error(f"添加自选股失败: {e}")
            return False

    def add_batch(self, stock_codes: List[str]) -> bool:
        """批量添加自选股"""
        try:
            with self._session_manager.get_session() as session:
                max_order = session.query(
                    WatchlistStock.display_order
                ).order_by(
                    WatchlistStock.display_order.desc()
                ).limit(1).scalar() or 0

                for i, code in enumerate(stock_codes):
                    code = code.strip()
                    if not code:
                        continue

                    existing = session.query(WatchlistStock).filter(
                        WatchlistStock.stock_code == code
                    ).first()

                    if not existing:
                        watchlist = WatchlistStock(
                            stock_code=code,
                            stock_name=code,
                            display_order=max_order + i + 1
                        )
                        session.add(watchlist)

                return True
        except Exception as e:
            logger.error(f"批量添加自选股失败: {e}")
            return False

    def remove(self, stock_code: str) -> bool:
        """删除自选股"""
        try:
            with self._session_manager.get_session() as session:
                session.query(WatchlistStock).filter(
                    WatchlistStock.stock_code == stock_code
                ).delete()
                return True
        except Exception as e:
            logger.error(f"删除自选股失败: {e}")
            return False

    def clear(self) -> bool:
        """清空自选股"""
        try:
            with self._session_manager.get_session() as session:
                session.query(WatchlistStock).delete()
                return True
        except Exception as e:
            logger.error(f"清空自选股失败: {e}")
            return False


class StockBasicRepository(BaseRepository[StockBasicInfo]):
    """
    股票基本信息 Repository
    """

    def __init__(self):
        super().__init__(StockBasicInfo)

    def get_count(self) -> int:
        """获取股票总数"""
        return self.count()

    def get_last_updated(self):
        """获取最后更新时间"""
        with self._session_manager.get_session() as session:
            result = session.query(StockBasicInfo).order_by(
                StockBasicInfo.updated_at.desc()
            ).first()
            return result.updated_at if result else None

    def get_name(self, code: str) -> Optional[str]:
        """获取股票名称"""
        with self._session_manager.get_session() as session:
            result = session.query(StockBasicInfo).filter(
                StockBasicInfo.code == code
            ).first()
            return result.name if result else None

    def get_name_by_code(self, code: str) -> Optional[str]:
        """获取股票名称（别名）"""
        return self.get_name(code)

    def save_all(self, df: pd.DataFrame) -> bool:
        """批量保存股票信息（去重）"""
        try:
            with self._session_manager.get_session() as session:
                # 先清空表
                session.query(StockBasicInfo).delete()
                session.flush()
                
                # 映射 akshare 列名到数据库字段
                rename_map = {
                    '代码': 'code',
                    '名称': 'name',
                    '最新价': 'price',
                    '涨跌幅': 'change_pct',
                    '涨跌额': 'change_amount',
                    '振幅': 'amplitude',
                    '成交量': 'volume',
                    '成交额': 'amount',
                    '换手率': 'turnover_rate',
                    '量比': 'volume_ratio',
                    '市盈率-动态': 'pe',
                    '市净率': 'pb',
                    '总市值': 'total_mv',
                    '流通市值': 'circ_mv',
                    '60日涨跌幅': 'change_60d',
                    '年初至今涨跌幅': 'change_ytd'
                }
                
                # 重命名列
                df = df.rename(columns=rename_map)
                
                # 去重后插入
                seen = set()
                for _, row in df.iterrows():
                    code = str(row.get('code'))
                    if code and code not in seen:
                        seen.add(code)
                        session.add(StockBasicInfo(
                            code=code,
                            name=row.get('name'),
                            price=row.get('price'),
                            change_pct=row.get('change_pct'),
                            change_amount=row.get('change_amount'),
                            amplitude=row.get('amplitude'),
                            volume=row.get('volume'),
                            amount=row.get('amount'),
                            turnover_rate=row.get('turnover_rate'),
                            volume_ratio=row.get('volume_ratio'),
                            pe=row.get('pe'),
                            pb=row.get('pb'),
                            total_mv=row.get('total_mv'),
                            circ_mv=row.get('circ_mv'),
                            change_60d=row.get('change_60d'),
                            change_ytd=row.get('change_ytd')
                        ))
                
                return True
        except Exception as e:
            logger.error(f"保存股票信息失败: {e}")
            return False


StockRepository = StockBasicRepository
