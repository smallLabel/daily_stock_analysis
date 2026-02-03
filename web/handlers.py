# -*- coding: utf-8 -*-
"""
===================================
Web 处理器层 - 请求处理
===================================

职责：
1. 处理各类 HTTP 请求
2. 调用服务层执行业务逻辑
3. 返回响应数据

处理器分类：
- PageHandler: 页面请求处理
- ApiHandler: API 接口处理
"""

from __future__ import annotations

import json
import re
import logging
from http import HTTPStatus
from datetime import datetime
from typing import Dict, Any, TYPE_CHECKING

from web.services import get_config_service, get_analysis_service
from web.templates import render_config_page
from src.enums import ReportType

if TYPE_CHECKING:
    from http.server import BaseHTTPRequestHandler

logger = logging.getLogger(__name__)


# ============================================================
# 响应辅助类
# ============================================================

class Response:
    """HTTP 响应封装"""
    
    def __init__(
        self,
        body: bytes,
        status: HTTPStatus = HTTPStatus.OK,
        content_type: str = "text/html; charset=utf-8"
    ):
        self.body = body
        self.status = status
        self.content_type = content_type
    
    def send(self, handler: 'BaseHTTPRequestHandler') -> None:
        """发送响应到客户端"""
        handler.send_response(self.status)
        handler.send_header("Content-Type", self.content_type)
        handler.send_header("Content-Length", str(len(self.body)))
        handler.end_headers()
        handler.wfile.write(self.body)


class JsonResponse(Response):
    """JSON 响应封装"""
    
    def __init__(
        self,
        data: Dict[str, Any],
        status: HTTPStatus = HTTPStatus.OK
    ):
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        super().__init__(
            body=body,
            status=status,
            content_type="application/json; charset=utf-8"
        )


class HtmlResponse(Response):
    """HTML 响应封装"""
    
    def __init__(
        self,
        body: bytes,
        status: HTTPStatus = HTTPStatus.OK
    ):
        super().__init__(
            body=body,
            status=status,
            content_type="text/html; charset=utf-8"
        )


# ============================================================
# 页面处理器
# ============================================================

class PageHandler:
    """页面请求处理器"""
    
    def __init__(self):
        self.config_service = get_config_service()
    
    def handle_index(self) -> Response:
        """处理首页请求 GET /"""
        stock_list = self.config_service.get_stock_list()
        env_filename = self.config_service.get_env_filename()
        body = render_config_page(stock_list, env_filename)
        return HtmlResponse(body)
    
    def handle_update(self, form_data: Dict[str, list]) -> Response:
        """
        处理配置更新 POST /update
        
        Args:
            form_data: 表单数据
        """
        stock_list = form_data.get("stock_list", [""])[0]
        normalized = self.config_service.set_stock_list(stock_list)
        env_filename = self.config_service.get_env_filename()
        body = render_config_page(normalized, env_filename, message="已保存")
        return HtmlResponse(body)


# ============================================================
# API 处理器
# ============================================================

class ApiHandler:
    """API 请求处理器"""
    
    def __init__(self):
        self.analysis_service = get_analysis_service()
    
    def handle_health(self) -> Response:
        """
        健康检查 GET /health
        
        返回:
            {
                "status": "ok",
                "timestamp": "2026-01-19T10:30:00",
                "service": "stock-analysis-webui"
            }
        """
        data = {
            "status": "ok",
            "timestamp": datetime.now().isoformat(),
            "service": "stock-analysis-webui"
        }
        return JsonResponse(data)
    
    def handle_analysis(self, query: Dict[str, list]) -> Response:
        """
        触发股票分析 GET /analysis?code=xxx
        
        Args:
            query: URL 查询参数
            
        返回:
            {
                "success": true,
                "message": "分析任务已提交",
                "code": "600519",
                "task_id": "600519_20260119_103000"
            }
        """
        # 获取股票代码参数
        code_list = query.get("code", [])
        if not code_list or not code_list[0].strip():
            return JsonResponse(
                {"success": False, "error": "缺少必填参数: code (股票代码)"},
                status=HTTPStatus.BAD_REQUEST
            )
        
        code = code_list[0].strip()

        # 验证股票代码格式：A股(6位数字) / 港股(HK+5位数字) / 美股(1-5个大写字母+.+2个后缀字母)
        code = code.upper()
        is_a_stock = re.match(r'^\d{6}$', code)
        is_hk_stock = re.match(r'^HK\d{5}$', code)
        is_us_stock = re.match(r'^[A-Z]{1,5}(\.[A-Z]{1,2})?$', code.upper())

        if not (is_a_stock or is_hk_stock or is_us_stock):
            return JsonResponse(
                {"success": False, "error": f"无效的股票代码格式: {code} (A股6位数字 / 港股HK+5位数字 / 美股1-5个字母)"},
                status=HTTPStatus.BAD_REQUEST
            )
        
        # 获取报告类型参数（默认精简报告）
        report_type_str = query.get("report_type", ["simple"])[0]
        report_type = ReportType.from_str(report_type_str)
        
        # 提交异步分析任务
        try:
            result = self.analysis_service.submit_analysis(code, report_type=report_type)
            return JsonResponse(result)
        except Exception as e:
            logger.error(f"[ApiHandler] 提交分析任务失败: {e}")
            return JsonResponse(
                {"success": False, "error": f"提交任务失败: {str(e)}"},
                status=HTTPStatus.INTERNAL_SERVER_ERROR
            )
    
    def handle_tasks(self, query: Dict[str, list]) -> Response:
        """
        查询任务列表 GET /tasks
        
        Args:
            query: URL 查询参数 (可选 limit)
            
        返回:
            {
                "success": true,
                "tasks": [...]
            }
        """
        limit_list = query.get("limit", ["20"])
        try:
            limit = int(limit_list[0])
        except ValueError:
            limit = 20
        
        tasks = self.analysis_service.list_tasks(limit=limit)
        return JsonResponse({"success": True, "tasks": tasks})
    
    def handle_task_status(self, query: Dict[str, list]) -> Response:
        """
        查询单个任务状态 GET /task?id=xxx
        
        Args:
            query: URL 查询参数
        """
        task_id_list = query.get("id", [])
        if not task_id_list or not task_id_list[0].strip():
            return JsonResponse(
                {"success": False, "error": "缺少必填参数: id (任务ID)"},
                status=HTTPStatus.BAD_REQUEST
            )
        
        task_id = task_id_list[0].strip()
        task = self.analysis_service.get_task_status(task_id)
        
        if task is None:
            return JsonResponse(
                {"success": False, "error": f"任务不存在: {task_id}"},
                status=HTTPStatus.NOT_FOUND
            )
        
        return JsonResponse({"success": True, "task": task})
    
    # ============================================================
    # 持仓管理 API
    # ============================================================
    
    def handle_portfolio_summary(self, query: Dict[str, list]) -> Response:
        """
        获取持仓组合摘要 GET /api/portfolio/summary
        
        返回:
            {
                "success": true,
                "data": {
                    "total_positions": 5,
                    "total_market_value": 100000.0,
                    "total_cost": 95000.0,
                    "total_profit_loss": 5000.0,
                    "total_profit_loss_pct": 5.26,
                    "positions": [...]
                }
            }
        """
        try:
            from src.portfolio import PortfolioManager
            manager = PortfolioManager()
            summary = manager.get_portfolio_summary()
            return JsonResponse({"success": True, "data": summary})
        except Exception as e:
            logger.error(f"获取持仓摘要失败: {e}")
            return JsonResponse(
                {"success": False, "error": str(e)},
                status=HTTPStatus.INTERNAL_SERVER_ERROR
            )
    
    def handle_add_transaction(self, form_data: Dict[str, list]) -> Response:
        """
        添加交易记录 POST /api/portfolio/transaction
        
        Args:
            form_data: {
                "stock_code": "600519",
                "stock_name": "贵州茅台",
                "type": "buy" | "sell",
                "quantity": "100",
                "price": "1850.50",
                "commission": "5.0",
                "tax": "0",
                "notes": "建仓"
            }
        """
        try:
            from src.portfolio import PortfolioManager, TransactionType
            
            stock_code = form_data.get("stock_code", [""])[0].strip()
            stock_name = form_data.get("stock_name", [""])[0].strip()
            trans_type = form_data.get("type", ["buy"])[0].strip()
            quantity = float(form_data.get("quantity", ["0"])[0])
            price = float(form_data.get("price", ["0"])[0])
            commission = float(form_data.get("commission", ["0"])[0])
            tax = float(form_data.get("tax", ["0"])[0])
            notes = form_data.get("notes", [""])[0].strip()
            
            if not stock_code or quantity <= 0 or price <= 0:
                return JsonResponse(
                    {"success": False, "error": "参数错误: stock_code, quantity, price 必填"},
                    status=HTTPStatus.BAD_REQUEST
                )
            
            transaction_type = TransactionType.BUY if trans_type == "buy" else TransactionType.SELL
            
            manager = PortfolioManager()
            transaction = manager.add_transaction(
                stock_code=stock_code,
                stock_name=stock_name or f"股票{stock_code}",
                transaction_type=transaction_type,
                quantity=quantity,
                price=price,
                commission=commission,
                tax=tax,
                notes=notes
            )
            
            return JsonResponse({
                "success": True,
                "message": "交易记录已添加",
                "transaction_id": transaction.id
            })
        except Exception as e:
            logger.error(f"添加交易记录失败: {e}")
            return JsonResponse(
                {"success": False, "error": str(e)},
                status=HTTPStatus.INTERNAL_SERVER_ERROR
            )
    
    def handle_get_transactions(self, query: Dict[str, list]) -> Response:
        """
        获取交易记录 GET /api/portfolio/transactions?code=600519&limit=50
        """
        try:
            from src.portfolio import PortfolioManager
            
            code = query.get("code", [""])[0].strip() or None
            limit = int(query.get("limit", ["100"])[0])
            
            manager = PortfolioManager()
            transactions = manager.get_transactions(stock_code=code, limit=limit)
            
            return JsonResponse({
                "success": True,
                "data": [
                    {
                        "id": t.id,
                        "stock_code": t.stock_code,
                        "stock_name": t.stock_name,
                        "type": t.transaction_type.value,
                        "quantity": t.quantity,
                        "price": t.price,
                        "amount": t.amount,
                        "commission": t.commission,
                        "tax": t.tax,
                        "total_cost": t.get_total_cost(),
                        "transaction_date": t.transaction_date.isoformat(),
                        "notes": t.notes
                    }
                    for t in transactions
                ]
            })
        except Exception as e:
            logger.error(f"获取交易记录失败: {e}")
            return JsonResponse(
                {"success": False, "error": str(e)},
                status=HTTPStatus.INTERNAL_SERVER_ERROR
            )
    
    def handle_update_prices(self, form_data: Dict[str, list]) -> Response:
        """
        批量更新持仓价格 POST /api/portfolio/update-prices
        
        Args:
            form_data: {
                "prices": '{"600519": 1850.50, "601138": 35.20}'
            }
        """
        try:
            import json
            from src.portfolio import PortfolioManager
            
            prices_json = form_data.get("prices", ["{}"])[0]
            prices = json.loads(prices_json)
            
            if not prices:
                return JsonResponse(
                    {"success": False, "error": "prices参数为空"},
                    status=HTTPStatus.BAD_REQUEST
                )
            
            manager = PortfolioManager()
            manager.update_prices(prices)
            
            return JsonResponse({
                "success": True,
                "message": f"已更新{len(prices)}个持仓的价格"
            })
        except Exception as e:
            logger.error(f"更新价格失败: {e}")
            return JsonResponse(
                {"success": False, "error": str(e)},
                status=HTTPStatus.INTERNAL_SERVER_ERROR
            )
    
    def handle_set_risk_params(self, form_data: Dict[str, list]) -> Response:
        """
        设置止盈止损 POST /api/portfolio/set-risk
        
        Args:
            form_data: {
                "stock_code": "600519",
                "stop_loss_price": "1750.0",
                "take_profit_price": "1950.0"
            }
        """
        try:
            from src.portfolio import PortfolioManager
            
            stock_code = form_data.get("stock_code", [""])[0].strip()
            stop_loss = form_data.get("stop_loss_price", [""])[0].strip()
            take_profit = form_data.get("take_profit_price", [""])[0].strip()
            
            if not stock_code:
                return JsonResponse(
                    {"success": False, "error": "stock_code参数必填"},
                    status=HTTPStatus.BAD_REQUEST
                )
            
            manager = PortfolioManager()
            manager.set_risk_params(
                stock_code=stock_code,
                stop_loss_price=float(stop_loss) if stop_loss else None,
                take_profit_price=float(take_profit) if take_profit else None
            )
            
            return JsonResponse({
                "success": True,
                "message": "风控参数已设置"
            })
        except Exception as e:
            logger.error(f"设置风控参数失败: {e}")
            return JsonResponse(
                {"success": False, "error": str(e)},
                status=HTTPStatus.INTERNAL_SERVER_ERROR
            )

    def handle_history_performance(self) -> JsonResponse:
        """获取历史推荐表现（战绩回顾）"""
        try:
            import os
            import json
            from datetime import datetime
            
            # 1. 查找最近的历史记录
            history_dir = os.path.join(os.getcwd(), 'data', 'history')
            if not os.path.exists(history_dir):
                return JsonResponse({"success": False, "message": "暂无历史记录"})
                
            files = [f for f in os.listdir(history_dir) if f.startswith('recommendation_')]
            if not files:
                return JsonResponse({"success": False, "message": "暂无历史推荐记录"})
                
            # 按文件名排序（日期）
            files.sort(reverse=True)
            
            # 逻辑：查找最近一个非今日的记录，如果没有则取今日的
            # 这样如果用户今天还没跑，昨天有数据，就看昨天的
            # 如果今天跑了，想看昨天的，就得找第二个
            
            today_str = datetime.now().strftime('%Y%m%d')
            target_file = None
            
            for f in files:
                # 简单逻辑：取最新的一个文件进行回顾
                # 无论是今天刚跑的，还是昨天的，都回顾一下
                # 实际场景：如果今天刚跑，当前价格和推荐价格一样，没变化
                # 如果是昨天的，就有变化
                target_file = f
                break
                
            if not target_file:
                 return JsonResponse({"success": False, "message": "未找到有效记录"})

            file_date = target_file.split('_')[1].split('.')[0]
            
            # 2. 读取记录
            with open(os.path.join(history_dir, target_file), 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            recommendations = data.get('all_recommendations', [])
            if not recommendations:
                return JsonResponse({
                    "success": True, 
                    "data": {
                        "summary": {"date": file_date, "count": 0, "win_rate": 0, "avg_return": 0},
                        "details": [],
                        "message": "该日无推荐个股"
                    }
                })
                
            # 3. 获取当前实时行情
            codes = [rec['code'] for rec in recommendations]
            current_quotes = self.data_manager.get_realtime_quotes(codes)
            
            # 4. 计算表现
            performance_list = []
            total_return = 0
            win_count = 0
            
            for rec in recommendations:
                code = rec['code']
                start_price = rec['current_price']
                
                curr_price = start_price # 默认不动
                
                if code in current_quotes:
                    curr_price = current_quotes[code]['current']
                
                # 计算自推荐以来的收益
                period_return = 0.0
                if start_price > 0:
                    period_return = ((curr_price - start_price) / start_price) * 100
                    
                if period_return > 0:
                    win_count += 1
                    
                total_return += period_return
                
                performance_list.append({
                    "code": code,
                    "name": rec['name'],
                    "rec_price": start_price,
                    "curr_price": curr_price,
                    "period_return": period_return,
                    "strategy": rec.get('strategy_name', '未知')
                })
                
            # 排序：涨幅高的在前
            performance_list.sort(key=lambda x: x['period_return'], reverse=True)
            
            summary = {
                "date": file_date,
                "count": len(performance_list),
                "win_rate": (win_count / len(performance_list)) * 100 if performance_list else 0,
                "avg_return": total_return / len(performance_list) if performance_list else 0,
                "best_stock": performance_list[0] if performance_list else None
            }
            
            return JsonResponse({
                "success": True, 
                "data": {
                    "summary": summary,
                    "details": performance_list
                }
            })
            
        except Exception as e:
            logger.error(f"获取战绩失败: {e}")
            return JsonResponse({
                "success": False, 
                "message": str(e)
            }, status=HTTPStatus.INTERNAL_SERVER_ERROR)
    
    
    def handle_sector_analysis(self, query: Dict[str, list]) -> Response:
        """
        板块选股分析 GET /api/sector-analysis?sector_count=10&stock_count=3
        
        Args:
            query: URL查询参数
                - sector_count: 分析板块数量（默认10）
                - stock_count: 每个板块推荐个股数（默认3）
        
        返回:
            {
                "success": true,
                "result": {
                    "sectors": [...],
                    "recommendations_by_sector": {...},
                    "summary": {...},
                    "analysis_time": "2026-02-03 10:16:50"
                }
            }
        """
        error_details = {
            "failed_apis": [],
            "available_apis": [],
            "error_messages": []
        }
        
        try:
            from src.sector_stock_picker import SectorStockPicker
            from data_provider import DataFetcherManager
            
            # 获取参数
            sector_count = int(query.get("sector_count", ["10"])[0])
            stock_count = int(query.get("stock_count", ["3"])[0])
            
            # 参数验证
            if sector_count < 1 or sector_count > 50:
                sector_count = 10
            if stock_count < 1 or stock_count > 10:
                stock_count = 3
            
            logger.info(f"开始板块选股分析: sector_count={sector_count}, stock_count={stock_count}")
            
            # 创建数据管理器并检查数据源状态
            data_manager = DataFetcherManager()
            
            # 检查各个数据源的可用性
            for fetcher in data_manager._fetchers:
                try:
                    fetcher_name = fetcher.name
                    # 尝试简单的健康检查（如果有的话）
                    if hasattr(fetcher, 'api') and fetcher.api is not None:
                        error_details["available_apis"].append(f"{fetcher_name} (优先级 {fetcher.priority})")
                    else:
                        error_details["available_apis"].append(f"{fetcher_name} (优先级 {fetcher.priority}, 无需API)")
                except Exception as fe:
                    error_details["failed_apis"].append(f"{fetcher_name}: {str(fe)}")
            
            # 创建选股器并执行分析
            picker = SectorStockPicker(data_manager=data_manager)
            
            try:
                result = picker.run_full_analysis(
                    sector_top_n=sector_count,
                    stock_top_n=stock_count
                )
                
                logger.info("板块选股分析完成")
                
                # 添加数据源信息到结果中
                result["data_source_info"] = {
                    "available_apis": error_details["available_apis"],
                    "total_sources": len(data_manager._fetchers)
                }
                
                return JsonResponse({
                    "success": True,
                    "result": result
                })
                
            except Exception as analysis_error:
                # 分析过程中的错误
                error_msg = str(analysis_error)
                error_details["error_messages"].append(f"分析错误: {error_msg}")
                
                # 检查是否是数据源错误
                if "数据源" in error_msg or "API" in error_msg or "token" in error_msg.lower():
                    error_details["error_messages"].append("可能的原因：数据源API不可用或API Key配置错误")
                
                logger.error(f"板块选股分析失败: {analysis_error}", exc_info=True)
                
                return JsonResponse({
                    "success": False,
                    "message": "板块选股分析失败",
                    "error": error_msg,
                    "details": error_details,
                    "suggestion": "请检查以下项目：\n1. 网络连接是否正常\n2. API Key是否配置正确（.env文件）\n3. 数据源服务是否可用\n4. 查看详细错误信息"
                }, status=HTTPStatus.INTERNAL_SERVER_ERROR)
            
        except ImportError as ie:
            logger.error(f"模块导入失败: {ie}", exc_info=True)
            return JsonResponse({
                "success": False,
                "message": "系统模块导入失败",
                "error": str(ie),
                "suggestion": "请检查依赖包是否正确安装：pip install -r requirements.txt"
            }, status=HTTPStatus.INTERNAL_SERVER_ERROR)
            
        except Exception as e:
            logger.error(f"板块选股分析失败: {e}", exc_info=True)
            return JsonResponse({
                "success": False,
                "message": "系统错误",
                "error": str(e),
                "details": error_details,
                "suggestion": "请查看服务器日志获取详细信息"
            }, status=HTTPStatus.INTERNAL_SERVER_ERROR)



# ============================================================
# Bot Webhook 处理器
# ============================================================

class BotHandler:
    """
    机器人 Webhook 处理器
    
    处理各平台的机器人回调请求。
    """
    
    def handle_webhook(self, platform: str, form_data: Dict[str, list], headers: Dict[str, str], body: bytes) -> Response:
        """
        处理 Webhook 请求
        
        Args:
            platform: 平台名称 (feishu, dingtalk, wecom, telegram)
            form_data: POST 数据（已解析）
            headers: HTTP 请求头
            body: 原始请求体
            
        Returns:
            Response 对象
        """
        try:
            from bot.handler import handle_webhook
            from bot.models import WebhookResponse
            
            # 调用 bot 模块处理
            webhook_response = handle_webhook(platform, headers, body)
            
            # 转换为 web 响应
            return JsonResponse(
                webhook_response.body,
                status=HTTPStatus(webhook_response.status_code)
            )
            
        except ImportError as e:
            logger.error(f"[BotHandler] Bot 模块未正确安装: {e}")
            return JsonResponse(
                {"error": "Bot module not available"},
                status=HTTPStatus.INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            logger.error(f"[BotHandler] 处理 {platform} Webhook 失败: {e}")
            return JsonResponse(
                {"error": str(e)},
                status=HTTPStatus.INTERNAL_SERVER_ERROR
            )


# ============================================================
# 处理器工厂
# ============================================================

_page_handler: PageHandler | None = None
_api_handler: ApiHandler | None = None
_bot_handler: BotHandler | None = None


def get_page_handler() -> PageHandler:
    """获取页面处理器实例"""
    global _page_handler
    if _page_handler is None:
        _page_handler = PageHandler()
    return _page_handler


def get_api_handler() -> ApiHandler:
    """获取 API 处理器实例"""
    global _api_handler
    if _api_handler is None:
        _api_handler = ApiHandler()
    return _api_handler


def get_bot_handler() -> BotHandler:
    """获取 Bot 处理器实例"""
    global _bot_handler
    if _bot_handler is None:
        _bot_handler = BotHandler()
    return _bot_handler
