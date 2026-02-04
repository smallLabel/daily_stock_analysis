# -*- coding: utf-8 -*-
"""
===================================
EfinanceFetcher - 主数据源 (Priority 0)
===================================

数据来源：efinance 库
特点：免费开源，无需 API Key，无需配额限制

API 参考：https://github.com/Micro-sheep/efinance

主要方法：
- ef.stock.get_quote_history(stock_code) - 获取股票历史K线
- 支持 A 股、港股、美股
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

import pandas as pd

from ..core.base import BaseFetcher, DataFetchError, STANDARD_COLUMNS

logger = logging.getLogger(__name__)


class EfinanceFetcher(BaseFetcher):
    """
    efinance 数据源实现

    优先级：0（最高优先级）
    数据来源：efinance 库（免费开源）

    优点：
    - 无需 API Key
    - 无请求配额限制
    - 支持 A 股、港股、美股
    - 数据更新及时

    缺点：
    - 主要是历史数据
    - 实时行情功能有限
    """

    name = "EfinanceFetcher"
    priority = 0  # 最高优先级

    def __init__(self):
        """
        初始化 EfinanceFetcher
        """
        super().__init__()
        self._check_availability()

    def _check_availability(self) -> None:
        """检查 efinance 是否可用"""
        try:
            import efinance
            self._api = efinance
            logger.info("✅ efinance 库初始化成功")
        except ImportError as e:
            logger.error(f"❌ efinance 库未安装: {e}")
            self._api = None

    def is_available(self) -> bool:
        """检查数据源是否可用"""
        return self._api is not None

    def _convert_code(self, stock_code: str) -> str:
        """
        转换股票代码为 efinance 格式

        efinance 格式：
        - A 股：直接用代码，如 '600519'
        - 港股：需要前缀，如 'HK+股票代码' 或 '港股+名称'
        - 美股：直接用代码，如 'AAPL'
        """
        stock_code = stock_code.strip().upper()

        # 判断是否为美股
        if self._is_us_code(stock_code):
            return stock_code

        # 判断是否为港股
        if stock_code.startswith('HK') or stock_code.startswith('港股'):
            if stock_code.startswith('HK'):
                return f'HK{stock_code[2:]}'
            return stock_code.replace('港股', '')

        # A 股：如果是纯数字，补齐 6 位
        if stock_code.isdigit():
            return stock_code.zfill(6)

        return stock_code

    def _is_us_code(self, stock_code: str) -> bool:
        """
        判断代码是否为美股

        美股代码规则：
        - 1-5 个大写字母，如 'AAPL', 'TSLA'
        - 可能包含 '.'，如 'BRK.B'
        """
        code = stock_code.strip().upper()
        return bool(__import__('re').match(r'^[A-Z]{1,5}(\.[A-Z])?$', code))

    def _fetch_raw_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        从 efinance 获取原始数据

        Args:
            stock_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            原始数据 DataFrame
        """
        if not self.is_available():
            raise DataFetchError("efinance 库未安装或未初始化")

        stock_code = self._convert_code(stock_code)
        df = self._api.stock.get_quote_history(stock_code)

        if df is None or df.empty:
            raise DataFetchError(f"未获取到 {stock_code} 的历史数据")

        return df

    def _normalize_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        """
        标准化 efinance 数据为系统统一格式

        Args:
            df: 原始数据 DataFrame
            stock_code: 股票代码

        Returns:
            标准化后的 DataFrame
        """
        return self._standardize_data(df, stock_code)

    def fetch_history(
        self,
        stock_code: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        adjust: str = "qfq"
    ) -> pd.DataFrame:
        """
        获取股票历史K线数据

        Args:
            stock_code: 股票代码
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            adjust: 复权类型 ('qfq' 前复权, 'hfq' 后复权, '' 不复权)

        Returns:
            包含历史数据的 DataFrame

        Raises:
            DataFetchError: 获取失败时抛出
        """
        if not self.is_available():
            raise DataFetchError("efinance 库未安装或未初始化")

        try:
            stock_code = self._convert_code(stock_code)
            logger.debug(f"获取股票历史数据: {stock_code}")

            # 调用 efinance API
            df = self._api.stock.get_quote_history(stock_code)

            if df is None or df.empty:
                raise DataFetchError(f"未获取到 {stock_code} 的历史数据")

            # 日期范围过滤
            if start_date:
                start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                df = df[df['日期'] >= start_dt]

            if end_date:
                end_dt = datetime.strptime(end_date, "%Y-%m-%d")
                df = df[df['日期'] <= end_dt]

            # 标准化数据
            df = self._standardize_data(df, stock_code)

            logger.debug(f"获取 {stock_code} 历史数据成功: {len(df)} 条")
            return df

        except DataFetchError:
            raise
        except Exception as e:
            logger.error(f"efinance 获取 {stock_code} 历史数据失败: {e}")
            raise DataFetchError(f"efinance 获取数据失败: {e}") from e

    def _standardize_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        """
        标准化 efinance 数据为系统统一格式

        efinance 返回的列名：
        ['股票名称', '股票代码', '日期', '开盘', '收盘', '最高', '最低',
         '成交量', '成交额', '振幅', '涨跌幅', '涨跌额', '换手率']

        标准化后的列名 (STANDARD_COLUMNS)：
        ['date', 'open', 'high', 'low', 'close', 'volume', 'amount',
         'amplitude', 'pct_chg', 'change', 'turnover_rate']
        """
        if df is None or df.empty:
            return pd.DataFrame(columns=STANDARD_COLUMNS)

        # 重命名列
        rename_map = {
            '日期': 'date',
            '开盘': 'open',
            '收盘': 'close',
            '最高': 'high',
            '最低': 'low',
            '成交量': 'volume',
            '成交额': 'amount',
            '振幅': 'amplitude',
            '涨跌幅': 'pct_chg',
            '涨跌额': 'change',
            '换手率': 'turnover_rate'
        }

        df = df.rename(columns=rename_map)

        # 确保日期格式统一
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')

        # 确保数值列为数值类型
        numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'amount',
                       'amplitude', 'pct_chg', 'change', 'turnover_rate']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        # 成交量单位转换（efinance 的 vol 单位是手，转换为股）
        if 'volume' in df.columns:
            df['volume'] = df['volume'] * 100

        # 成交额单位转换（efinance 的 amount 单位是千元，转换为元）
        if 'amount' in df.columns:
            df['amount'] = df['amount'] * 1000

        # 按日期升序排列
        if 'date' in df.columns:
            df = df.sort_values('date')

        return df

    def get_stock_name(self, stock_code: str) -> Optional[str]:
        """
        获取股票名称

        Args:
            stock_code: 股票代码

        Returns:
            股票名称，未找到返回 None
        """
        try:
            stock_code = self._convert_code(stock_code)
            df = self._api.stock.get_quote_history(stock_code)

            if df is not None and not df.empty:
                # efinance 返回的数据第一行是最新数据
                return df.iloc[0].get('股票名称', stock_code)

            return stock_code

        except Exception as e:
            logger.warning(f"efinance 获取股票名称失败 {stock_code}: {e}")
            return None

    def get_stock_list(self, market: str = 'A') -> List[Dict[str, str]]:
        """
        获取股票列表

        Args:
            market: 市场类型 ('A' A股, 'HK' 港股, 'US' 美股)

        Returns:
            股票列表，每项包含代码和名称

        Note: efinance 暂未提供完整的股票列表接口，这里返回空列表
        """
        logger.debug("efinance 暂不支持获取完整股票列表")
        return []

    def fetch_realtime(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """
        获取股票实时行情

        Args:
            stock_code: 股票代码

        Returns:
            实时行情字典

        Note: efinance 主要用于历史数据，实时行情功能有限
        """
        try:
            stock_code = self._convert_code(stock_code)

            # 获取最新历史数据作为实时数据
            df = self._api.stock.get_quote_history(stock_code)

            if df is None or df.empty:
                return None

            # 取最新一条数据
            latest = df.iloc[0]

            return {
                'code': stock_code,
                'name': latest.get('股票名称', stock_code),
                'close': float(latest.get('收盘', 0)),
                'open': float(latest.get('开盘', 0)),
                'high': float(latest.get('最高', 0)),
                'low': float(latest.get('最低', 0)),
                'volume': float(latest.get('成交量', 0)) * 100,  # 转换为股
                'amount': float(latest.get('成交额', 0)) * 1000,  # 转换为元
                'pct_chg': float(latest.get('涨跌幅', 0)),
                'change': float(latest.get('涨跌额', 0)),
                'turnover_rate': float(latest.get('换手率', 0)),
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            logger.warning(f"efinance 获取实时行情失败 {stock_code}: {e}")
            return None


# 便捷函数
def get_efinance_fetcher() -> EfinanceFetcher:
    """获取 EfinanceFetcher 单例"""
    return EfinanceFetcher()
