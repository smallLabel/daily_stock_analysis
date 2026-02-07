# -*- coding: utf-8 -*-
"""
===================================
基本面分析器
===================================

职责：
1. 获取和分析上市公司财务数据
2. 评估盈利能力、成长性、估值和安全性
3. 提供基本面健康度评分

数据源：
- Tushare Pro（主要）
- AkShare（备用）
"""

import logging
from typing import Dict, Optional, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class FundamentalAnalyzer:
    """基本面分析器
    
    分析维度：
    1. 盈利能力 (Profitability): ROE, ROA, 净利率
    2. 成长性 (Growth): 营收增长率, 净利润增长率, EPS增长率  
    3. 估值 (Valuation): PE, PB, PS, PEG
    4. 安全性 (Safety): 流动比率, 资产负债率, 现金比率
    """
    
    def __init__(self, config=None):
        """
        初始化基本面分析器
        
        数据源优先级：
        1. Akshare/Efinance（免费开源，东方财富数据）
        2. Tushare（需要 Token，数据更专业）
        
        Args:
            config: 配置对象（可选，默认从全局配置读取）
        """
        if config is None:
            from src.config import get_config
            config = get_config()
        
        self.config = config
        self._tushare_api = None
        self._cache = {}  # 简单内存缓存
        self._cache_ttl = 86400  # 1天缓存时间
        
        # 初始化数据管理器（用于获取 Akshare/Efinance 数据）
        from data_provider.core.manager import DataFetcherManager
        self._data_manager = DataFetcherManager()
        
        # 初始化 Tushare API（作为备用数据源）
        self._init_tushare()
    
    def _init_tushare(self):
        """初始化 Tushare API"""
        try:
            import tushare as ts
            token = getattr(self.config, 'tushare_token', None)
            
            if not token:
                logger.info("未配置 TUSHARE_TOKEN，基本面分析将优先使用 Akshare")
                return
            
            ts.set_token(token)
            self._tushare_api = ts.pro_api()
            logger.info("Tushare API 初始化成功（作为备用数据源）")
        except ImportError:
            logger.info("未安装 tushare 库，基本面分析将仅使用 Akshare")
        except Exception as e:
            logger.error(f"Tushare API 初始化失败: {e}")
    
    def is_available(self) -> bool:
        """检查基本面分析器是否可用"""
        return self._tushare_api is not None
    
    def _get_cache_key(self, code: str, metric_type: str) -> str:
        """生成缓存键"""
        return f"{code}_{metric_type}"
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """检查缓存是否有效"""
        if cache_key not in self._cache:
            return False
        
        cached_data = self._cache[cache_key]
        if 'timestamp' not in cached_data:
            return False
        
        cache_age = datetime.now().timestamp() - cached_data['timestamp']
        return cache_age < self._cache_ttl
    
    def _set_cache(self, cache_key: str, data: Any):
        """设置缓存"""
        self._cache[cache_key] = {
            'data': data,
            'timestamp': datetime.now().timestamp()
        }
    
    def _get_cache(self, cache_key: str) -> Optional[Any]:
        """获取缓存数据"""
        if self._is_cache_valid(cache_key):
            return self._cache[cache_key]['data']
        return None
    
    def analyze_financial_health(self, code: str) -> Dict[str, Any]:
        """
        财务健康度分析（总入口）
        
        Args:
            code: 股票代码
            
        Returns:
            包含所有维度的财务分析结果
        """
        if not self.is_available():
            return {
                'available': False,
                'error': '基本面分析不可用：未配置 Tushare Token'
            }
        
        try:
            # 获取各维度指标
            profitability = self.get_profitability_metrics(code)
            growth = self.get_growth_metrics(code)
            valuation = self.get_valuation_metrics(code)
            safety = self.get_safety_metrics(code)
            
            return {
                'available': True,
                'code': code,
                'profitability': profitability,
                'growth': growth,
                'valuation': valuation,
                'safety': safety,
                'analyzed_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        except Exception as e:
            logger.error(f"基本面分析失败 [{code}]: {e}")
            return {
                'available': False,
                'error': f'分析失败: {str(e)}'
            }
    
    def get_profitability_metrics(self, code: str) -> Dict[str, Any]:
        """
        获取盈利能力指标
        
        数据源优先级：
        1. 优先使用 Akshare（免费，东方财富数据）
        2. 失败后使用 Tushare（需要 Token）
        
        Args:
            code: 股票代码
            
        Returns:
            盈利能力指标字典
        """
        cache_key = self._get_cache_key(code, 'profitability')
        cached = self._get_cache(cache_key)
        if cached:
            return cached
        
        # 优先尝试 Akshare
        result = self._get_profitability_from_akshare(code)
        if result and 'error' not in result:
            self._set_cache(cache_key, result)
            return result
        
        # Akshare 失败，使用 Tushare
        logger.info(f"Akshare 获取失败，尝试使用 Tushare 获取[{code}]盈利能力指标")
        result = self._get_profitability_from_tushare(code)
        if result:
            self._set_cache(cache_key, result)
        return result
    
    def _get_profitability_from_akshare(self, code: str) -> Dict[str, Any]:
        """从 Akshare 获取盈利能力指标"""
        try:
            # 从数据管理器中获取 AkshareFetcher
            for fetcher in self._data_manager._fetchers:
                if fetcher.name == "AkshareFetcher":
                    # 调用 AkshareFetcher 的财务指标接口
                    df = fetcher.get_financial_indicator(code)
                    
                    if df is None or df.empty:
                        return {'error': '无数据'}
                    
                    # 取最新一期数据
                    latest = df.iloc[0]
                    
                    # Akshare 返回的列名可能是中文，映射到标准字段
                    result = {
                        'roe': None,
                        'roa': None,
                        'net_margin': None
                    }
                    
                    # 尝试从多种可能的列名中获取数据
                    roe_cols = ['净资产收益率', 'ROE', 'roe', '加权净资产收益率']
                    for col in roe_cols:
                        if col in latest.index and pd.notna(latest[col]):
                            result['roe'] = round(float(latest[col]), 2)
                            break
                    
                    roa_cols = ['总资产收益率', 'ROA', 'roa', '总资产净利率']
                    for col in roa_cols:
                        if col in latest.index and pd.notna(latest[col]):
                            result['roa'] = round(float(latest[col]), 2)
                            break
                    
                    margin_cols = ['销售净利率', '净利率', 'net_margin', '销售净利润率']
                    for col in margin_cols:
                        if col in latest.index and pd.notna(latest[col]):
                            result['net_margin'] = round(float(latest[col]), 2)
                            break
                    
                    logger.info(f"[Akshare] 成功获取 {code} 盈利能力指标")
                    return result
                    
            return {'error': 'AkshareFetcher 不可用'}
            
        except Exception as e:
            logger.warning(f"[Akshare] 获取盈利能力指标失败 [{code}]: {e}")
            return {'error': str(e)}
    
    def _get_profitability_from_tushare(self, code: str) -> Dict[str, Any]:
        """从 Tushare 获取盈利能力指标（原有逻辑）"""
        if not self._tushare_api:
            return {'error': '未配置 Tushare'}
        
        try:
            # 获取最新财务指标
            df = self._tushare_api.fina_indicator(
                ts_code=self._convert_code_format(code),
                fields='roe,roa,net_margin'
            )
            
            if df.empty:
                return {'error': '无数据'}
            
            # 取最新一期数据
            latest = df.iloc[0]
            
            result = {
                'roe': round(latest['roe'], 2) if 'roe' in latest else None,  # 净资产收益率
                'roa': round(latest['roa'], 2) if 'roa' in latest else None,  # 总资产收益率
                'net_margin': round(latest['net_margin'], 2) if 'net_margin' in latest else None  # 净利率
            }
            
            logger.info(f"[Tushare] 成功获取 {code} 盈利能力指标")
            return result
            
        except Exception as e:
            logger.error(f"[Tushare] 获取盈利能力指标失败 [{code}]: {e}")
            return {'error': str(e)}
    
    def get_growth_metrics(self, code: str) -> Dict[str, Any]:
        """
        获取成长性指标
        
        Args:
            code: 股票代码
            
        Returns:
            成长性指标字典
        """
        cache_key = self._get_cache_key(code, 'growth')
        cached = self._get_cache(cache_key)
        if cached:
            return cached
        
        try:
            # 获取利润表数据（近2期，用于计算增长率）
            df = self._tushare_api.income(
                ts_code=self._convert_code_format(code),
                fields='total_revenue,n_income,basic_eps'
            )
            
            if df.empty or len(df) < 2:
                return {'error': '数据不足'}
            
            # 计算同比增长率
            current = df.iloc[0]
            previous = df.iloc[1]
            
            def calc_growth(current_val, previous_val):
                if previous_val == 0 or previous_val is None:
                    return None
                return round((current_val - previous_val) / abs(previous_val) * 100, 2)
            
            result = {
                'revenue_growth': calc_growth(
                    current.get('total_revenue'), 
                    previous.get('total_revenue')
                ),  # 营收增长率
                'profit_growth': calc_growth(
                    current.get('n_income'), 
                    previous.get('n_income')
                ),  # 净利润增长率
                'eps_growth': calc_growth(
                    current.get('basic_eps'), 
                    previous.get('basic_eps')
                )  # EPS增长率
            }
            
            self._set_cache(cache_key, result)
            return result
            
        except Exception as e:
            logger.error(f"获取成长性指标失败 [{code}]: {e}")
            return {'error': str(e)}
    
    def get_valuation_metrics(self, code: str) -> Dict[str, Any]:
        """
        获取估值指标
        
        Args:
            code: 股票代码
            
        Returns:
            估值指标字典
        """
        cache_key = self._get_cache_key(code, 'valuation')
        cached = self._get_cache(cache_key)
        if cached:
            return cached
        
        try:
            # 获取日行情（含PE、PB）
            df = self._tushare_api.daily_basic(
                ts_code=self._convert_code_format(code),
                fields='pe,pb,ps'
            )
            
            if df.empty:
                return {'error': '无数据'}
            
            latest = df.iloc[0]
            
            # 获取EPS增长率用于计算PEG
            growth = self.get_growth_metrics(code)
            eps_growth = growth.get('eps_growth', None) if 'error' not in growth else None
            
            pe = latest.get('pe', None)
            peg = None
            if pe and eps_growth and eps_growth > 0:
                peg = round(pe / eps_growth, 2)
            
            result = {
                'pe': round(latest['pe'], 2) if 'pe' in latest and latest['pe'] else None,  # 市盈率
                'pb': round(latest['pb'], 2) if 'pb' in latest and latest['pb'] else None,  # 市净率
                'ps': round(latest['ps'], 2) if 'ps' in latest and latest['ps'] else None,  # 市销率
                'peg': peg  # PEG = PE / EPS增长率
            }
            
            self._set_cache(cache_key, result)
            return result
            
        except Exception as e:
            logger.error(f"获取估值指标失败 [{code}]: {e}")
            return {'error': str(e)}
    
    def get_safety_metrics(self, code: str) -> Dict[str, Any]:
        """
        获取安全性指标
        
        Args:
            code: 股票代码
            
        Returns:
            安全性指标字典
        """
        cache_key = self._get_cache_key(code, 'safety')
        cached = self._get_cache(cache_key)
        if cached:
            return cached
        
        try:
            # 获取资产负债表
            df = self._tushare_api.balancesheet(
                ts_code=self._convert_code_format(code),
                fields='total_cur_assets,total_cur_liab,total_assets,total_liab,money_cap'
            )
            
            if df.empty:
                return {'error': '无数据'}
            
            latest = df.iloc[0]
            
            # 计算各项比率
            current_ratio = None
            if latest.get('total_cur_liab') and latest['total_cur_liab'] != 0:
                current_ratio = round(latest['total_cur_assets'] / latest['total_cur_liab'], 2)
            
            debt_ratio = None
            if latest.get('total_assets') and latest['total_assets'] != 0:
                debt_ratio = round(latest['total_liab'] / latest['total_assets'], 2)
            
            cash_ratio = None
            if latest.get('total_cur_liab') and latest['total_cur_liab'] != 0:
                cash_ratio = round(latest.get('money_cap', 0) / latest['total_cur_liab'], 2)
            
            result = {
                'current_ratio': current_ratio,  # 流动比率
                'debt_ratio': debt_ratio,  # 资产负债率
                'cash_ratio': cash_ratio  # 现金比率
            }
            
            self._set_cache(cache_key, result)
            return result
            
        except Exception as e:
            logger.error(f"获取安全性指标失败 [{code}]: {e}")
            return {'error': str(e)}
    
    def _convert_code_format(self, code: str) -> str:
        """
        转换股票代码格式为 Tushare 格式
        
        Args:
            code: 原始代码（如 "600519"）
            
        Returns:
            Tushare 格式代码（如 "600519.SH"）
        """
        if '.' in code:
            return code  # 已经是正确格式
        
        # 根据代码前缀判断交易所
        if code.startswith('6'):
            return f"{code}.SH"  # 上交所
        elif code.startswith('0') or code.startswith('3'):
            return f"{code}.SZ"  # 深交所
        elif code.startswith('8') or code.startswith('4'):
            return f"{code}.BJ"  # 北交所
        else:
            return code  # 其他情况保持原样
