# -*- coding: utf-8 -*-
"""
===================================
Stock Data Service - 市场数据服务
===================================

职责：
1. 协调 Fetcher 获取数据
2. 协调 Repository 保存/查询数据
3. 对外提供统一的业务接口
"""

import logging
from typing import Optional
from datetime import datetime
import pandas as pd

from data_provider.repository.stock_repo import StockRepository
# Avoid circular imports if possible, or import inside methods
from data_provider import DataFetcherManager
# Or import specific fetcher if needed, but Manager is better for abstraction

logger = logging.getLogger(__name__)

class StockDataService:
    def __init__(self):
        self.repo = StockRepository()
        
    def ensure_market_data(self):
        """
        Ensure market data exists in DB.
        If missing or outdated, fetch from Akshare and save.
        """
        try:
            # 1. Check data count
            count = self.repo.get_count()
            
            # 2. Check last update time
            last_updated = self.repo.get_last_updated()
            
            need_update = False
            if count < 4000:
                logger.info(f"Stock basic info incomplete (count={count}). Triggering update...")
                need_update = True
            elif last_updated:
                days_since = (datetime.now() - last_updated).days
                if days_since > 3:
                     logger.info(f"Stock basic info outdated ({days_since} days). Triggering update...")
                     need_update = True
            else:
                # Count ok but no timestamp? Weird, maybe update
                pass

            if need_update:
                self._update_all_stocks()
            else:
                logger.debug(f"Stock basic info exists ({count} stocks). Skipping fetch.")
                
        except Exception as e:
            logger.error(f"Error ensuring market data: {e}", exc_info=True)

    def _update_all_stocks(self):
        """Fetch from Akshare and save to Repo."""
        try:
            # Use specific fetcher for this administrative task
            from data_provider.fetchers.akshare_fetcher import AkshareFetcher
            fetcher = AkshareFetcher()
            
            logger.info("Fetching stock list from Akshare...")
            df = fetcher.fetch_ticket_list()
            
            if df is None or df.empty:
                logger.warning("Fetched empty stock list.")
                return

            # Save DataFrame directly to Repo
            self.repo.save_all(df)
            
        except Exception as e:
            logger.error(f"Failed to update stock market data: {e}", exc_info=True)

    def get_stock_name(self, code: str) -> Optional[str]:
        """Get stock name by code."""
        return self.repo.get_name_by_code(code)

_stock_data_service = None

def get_stock_data_service():
    global _stock_data_service
    if _stock_data_service is None:
        _stock_data_service = StockDataService()
    return _stock_data_service
