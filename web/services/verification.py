from typing import List, Dict, Any, Optional
from datetime import date, timedelta, datetime
import logging
from sqlalchemy import select, and_, desc

from src.storage import DatabaseManager, AnalysisHistory, StockDaily
from data_provider import DataFetcherManager

logger = logging.getLogger(__name__)

class VerificationService:
    def __init__(self):
        self.db = DatabaseManager.get_instance()
        self.data_manager = DataFetcherManager()

    def get_last_trading_day_analysis(self, stock_codes: List[str]) -> Dict[str, Any]:
        """
        Retrieves the latest analysis record for each stock from the *previous* day (or earlier).
        Simple logic: Look for analysis records created before today.
        """
        results = {}
        today = date.today()
        
        with self.db.get_session() as session:
            for code in stock_codes:
                # Find the latest analysis BEFORE today
                # We sort by analyzed_at desc to get the most recent one
                record = session.execute(
                    select(AnalysisHistory)
                    .where(
                        and_(
                            AnalysisHistory.stock_code == code,
                            AnalysisHistory.analyzed_at < datetime.combine(today, datetime.min.time())
                        )
                    )
                    .order_by(desc(AnalysisHistory.analyzed_at))
                    .limit(1)
                ).scalar_one_or_none()
                
                if record:
                    results[code] = record
        
        return results

    def verify_predictions(self, stock_codes: List[str]) -> List[Dict[str, Any]]:
        """
        Verifies predictions for the given stocks.
        1. Get prior analysis.
        2. Get current/next-day market data.
        3. Compare.
        """
        past_analyses = self.get_last_trading_day_analysis(stock_codes)
        if not past_analyses:
            return []

        # Get real-time quotes for "today" (or the verification period)
        quotes = self.data_manager.get_realtime_quotes(list(past_analyses.keys()))
        
        verification_results = []
        
        for code, analysis in past_analyses.items():
            current = quotes.get(code)
            if not current:
                continue
                
            curr_price = current.get('current', 0)
            high_price = current.get('high', curr_price) # Ideally we want today's high
            low_price = current.get('low', curr_price)
            
            # Prediction Data
            buy_point = analysis.buy_point
            target_price = analysis.target_price
            stop_loss = analysis.stop_loss
            analysis_date = analysis.analyzed_at.strftime('%Y-%m-%d')
            
            # Logic:
            # 1. Did it hit Target? (Win)
            # 2. Did it hit Stop Loss? (Loss)
            # 3. Did it rise above Buy Point? (Active)
            
            status = "Waiting"
            badge_color = "grey"
            performance_pct = 0.0
            
            if analysis.current_price and analysis.current_price > 0:
                performance_pct = (curr_price - analysis.current_price) / analysis.current_price * 100
            
            # Simple Heuristics
            if target_price > 0 and high_price >= target_price:
                status = "Target Hit 🎯"
                badge_color = "green"
            elif stop_loss > 0 and low_price <= stop_loss:
                status = "Stop Hit 🛑"
                badge_color = "red"
            elif performance_pct > 0:
                 status = "Profit 📈"
                 badge_color = "blue"
            else:
                 status = "Loss 📉"
                 badge_color = "orange"

            verification_results.append({
                'code': code,
                'name': analysis.stock_name,
                'analysis_date': analysis_date,
                'rec_price': analysis.current_price,
                'curr_price': curr_price,
                'target': target_price,
                'return_pct': performance_pct,
                'status': status,
                'badge_color': badge_color
            })
            
        return verification_results

_verification_service = None

def get_verification_service():
    global _verification_service
    if _verification_service is None:
        _verification_service = VerificationService()
    return _verification_service
