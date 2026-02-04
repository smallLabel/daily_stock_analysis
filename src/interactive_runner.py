# -*- coding: utf-8 -*-
"""
交互式选股 + 定向回测 模块
"""
import logging
import time
import pandas as pd
from typing import List, Dict, Any
from data_provider.fetchers.akshare_fetcher import AkshareFetcher
from src.core.pipeline import StockAnalysisPipeline
from src.backtest import SimpleBacktester
from src.health_rater import StockHealthRater

logger = logging.getLogger(__name__)

class InteractiveRunner:
    def __init__(self):
        self.fetcher = AkshareFetcher()
        self.pipeline = StockAnalysisPipeline()
        self.backtester = SimpleBacktester()
        self.health_rater = StockHealthRater()
        
    def run_interaction(self):
        """交互主循环"""
        print("\n" + "="*50)
        print("进入交互式板块分析模式")
        print("="*50)
        
        while True:
            keyword = input("\n请输入板块名称（输入 'q' 退出）: ").strip()
            if keyword.lower() == 'q':
                break
            
            if not keyword:
                continue
                
            # 1. 搜索板块
            print(f"正在搜索 '{keyword}' ...")
            boards = self.fetcher.search_board(keyword)
            
            if not boards:
                print("未找到匹配的板块，请重试。")
                continue
            
            # 显示匹配结果
            print(f"\n找到 {len(boards)} 个匹配板块:")
            for i, b in enumerate(boards[:5]):
                print(f"{i+1}. {b['name']} (涨跌: {b['change_pct']}%, 资金: {b['money_flow']:.2f}亿, 股票: {b['stock_count']}只)")
            
            # 选择板块
            try:
                idx = int(input("\n请选择板块序号 (1-5, 0取消): "))
                if idx == 0: continue
                target_board = boards[idx-1]
            except:
                print("输入无效")
                continue
                
            print(f"\n已选择: {target_board['name']}")
            
            # 2. 获取成分股
            print("正在获取成分股列表...")
            stock_codes = self.fetcher.get_sector_stocks(target_board['name'])
            if not stock_codes:
                print("该板块暂无成分股信息。")
                continue
                
            print(f"共获取 {len(stock_codes)} 只成分股。")
            
            # 3. 询问是否回测
            do_backtest = input("是否对这些股票进行策略回测/健康度评分? (y/n): ").strip().lower()
            if do_backtest != 'y':
                continue
                
            strategy = input("请选择策略 (ma:双均线, rps:强势股, div:底背离) [默认ma]: ").strip().lower() or 'ma'
            
            self.run_batch_backtest(stock_codes, strategy)
            
    def run_batch_backtest(self, stock_codes: List[str], strategy: str):
        """批量回测"""
        results = []
        print(f"\n开始回测 {len(stock_codes)} 只股票，策略: {strategy}")
        
        # 进度条
        total = len(stock_codes)
        for i, code in enumerate(stock_codes):
            print(f"\r处理中... [{i+1}/{total}] {code}", end="")
            
            try:
                # 定向数据抓取 (缓存优先)
                # fetch_and_save_stock_data 内部有检查 has_today_data
                success, msg = self.pipeline.fetch_and_save_stock_data(code)
                if not success:
                    continue
                    
                # 从数据库读取历史数据 (用于回测，需要更长的时间窗口，比如200天)
                context = self.pipeline.db.get_analysis_context(code)
                if not context or 'raw_data' not in context:
                    continue
                    
                raw_data = context['raw_data']
                df = pd.DataFrame(raw_data)
                
                # 运行回测
                bt_res = self.backtester.run_strategy(df, strategy_type=strategy)
                
                # 运行健康度评分
                health_res = self.health_rater.evaluate(df, strategy_type=strategy)
                
                if bt_res and health_res:
                    combined = {
                        'code': code,
                        'name': context.get('stock_name', code),
                        **bt_res,
                        'health_score': health_res['total_score'],
                        'equity_curve': bt_res['equity_curve']
                    }
                    results.append(combined)
                    
            except Exception as e:
                logger.error(f"处理 {code} 失败: {e}")
                
        print("\n\n分析完成！")
        
        # 排序并展示结果
        df_res = pd.DataFrame(results)
        if df_res.empty:
            print("无可展示的结果")
            return
            
        # 按健康分排序
        df_res = df_res.sort_values('health_score', ascending=False)
        
        print(f"\n🏆 个股健康度排行榜 TOP 10 (策略: {strategy}):")
        print(f"{'代码':<8} {'名称':<8} {'健康分':<8} {'年化收益':<10} {'最大回撤':<10} {'夏普比率':<10} {'最新信号':<8}")
        print("-" * 75)
        
        top_10 = df_res.head(10)
        for _, row in top_10.iterrows():
            print(f"{row['code']:<8} {row['name']:<8} {row['health_score']:<8.1f} {row['annualized_return']:.2%}    {row['max_drawdown']:.2%}    {row['sharpe_ratio']:.2f}      {row['latest_signal']}")

        # 生成对照图
        try:
            chart_file = self.health_rater.generate_comparison_chart(results[:10], filename="top10_comparison.png")
            if chart_file:
                print(f"\n📈 已生成净值对照图: {chart_file}")
        except Exception as e:
            logger.error(f"生成图表失败: {e}")

if __name__ == "__main__":
    runner = InteractiveRunner()
    runner.run_interaction()
