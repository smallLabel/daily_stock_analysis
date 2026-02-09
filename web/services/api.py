# -*- coding: utf-8 -*-
"""
===================================
NiceGUI API 层 - 统一API接口
===================================

职责：
1. 提供NiceGUI的API端点
2. 调用现有服务层
3. 返回JSON响应

API Endpoints:
  POST /analysis - 触发股票分析（异步任务）
  GET  /tasks - 查询任务列表
  GET  /task - 查询任务状态
  GET  /api/analyze - 同步股票分析（推荐）
  GET  /api/watchlist - 获取自选股
  POST /api/watchlist/add - 添加自选股
  GET /api/watchlist/remove - 删除自选股
  GET  /api/portfolio/summary - 持仓摘要
  POST /api/portfolio/transaction - 添加交易记录
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime
from typing import Dict, Any, List, Optional
import os
from fastapi.staticfiles import StaticFiles

from nicegui import ui, app
from src.enums import ReportType
from .core import get_analysis_service

logger = logging.getLogger(__name__)


class ApiEndpoints:
    """NiceGUI API端点类"""
    
    def __init__(self):
        self.analysis_service = get_analysis_service()
        self.progress_store = {}  # 存储分析进度 {code: {step: str, progress: int, message: str}}
        
        # 初始化共享的 pipeline 实例
        try:
            from src.config import get_config
            from main import StockAnalysisPipeline
            config = get_config()
            self.pipeline = StockAnalysisPipeline(
                config=config,
                max_workers=1
            )
            logger.info("Shared StockAnalysisPipeline initialized in ApiEndpoints")
        except Exception as e:
            logger.error(f"Failed to initialize shared StockAnalysisPipeline: {e}")
            self.pipeline = None

        self._register_endpoints()
    
    def _register_endpoints(self):
        """注册所有API端点"""
        
        # 挂载静态文件目录 (web/services/ -> web/static)
        # __file__ is web/services/api.py
        # static dir is web/static
        static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static')
        if os.path.exists(static_dir):
            app.mount('/web/static', StaticFiles(directory=static_dir), name='web_static')
            logger.info(f"已挂载静态文件目录: {static_dir} -> /web/static")
        else:
            logger.warning(f"静态文件目录不存在: {static_dir}")
        
        @app.get('/health')
        async def health_check():
            """健康检查"""
            return {
                "status": "ok",
                "timestamp": datetime.now().isoformat(),
                "service": "stock-analysis-webui"
            }
        
        @app.get('/tasks')
        async def list_tasks(limit: int = 20):
            """查询任务列表"""
            tasks = self.analysis_service.list_tasks(limit=limit)
            return {"success": True, "tasks": tasks}
        
        @app.get('/task')
        async def get_task_status(id: str = None):
            """查询任务状态"""
            if not id:
                return {"success": False, "error": "缺少参数: id"}
            task = self.analysis_service.get_task_status(id)
            if task is None:
                return {"success": False, "error": f"任务不存在: {id}"}
            return {"success": True, "task": task}
        
        @app.get('/api/analyze/progress')
        async def get_analysis_progress(code: str = None):
            """
            获取分析进度
            
            Args:
                code: 股票代码
            
            Returns:
                {
                    "success": true,
                    "step": "数据获取",
                    "progress": 25,
                    "message": "正在获取实时行情..."
                }
            """
            if not code:
                return {"success": False, "error": "缺少参数: code"}
            
            code = code.upper().strip()
            progress_info = self.progress_store.get(code, {})
            
            if progress_info:
                return {
                    "success": True,
                    "step": progress_info.get("step", "准备中"),
                    "progress": progress_info.get("progress", 0),
                    "message": progress_info.get("message", "")
                }
            else:
                return {
                    "success": True,
                    "step": "准备中",
                    "progress": 0,
                    "message": "等待开始..."
                }
        
        @app.get('/api/analyze')
        async def analyze_stock_sync(code: str = None, report_type: str = 'simple'):
            """
            同步股票分析 - 推荐使用
            
            这是真正的实时方案，不需要轮询：
            1. 前端发起请求
            2. 后端使用asyncio运行分析（不阻塞）
            3. 分析完成后直接返回结果
            
            Args:
                code: 股票代码
                report_type: 报告类型 (simple/full)
            
            Returns:
                {
                    "success": true,
                    "result": {...}  // 分析结果
                }
            """
            if not code:
                return {"success": False, "error": "缺少参数: code"}
            
            code = code.upper().strip()
            
            # 验证股票代码
            if not self.validate_stock_code(code):
                return {"success": False, "error": f"无效的股票代码格式: {code}"}
            
            try:
                # 初始化进度
                self.progress_store[code] = {
                    "step": "准备中",
                    "progress": 0,
                    "message": "正在初始化分析流程..."
                }
                
                # 使用asyncio在后台运行分析，不阻塞
                loop = asyncio.get_event_loop()
                
                # 定义进度回调
                def progress_callback(step: str, progress: int, message: str):
                    self.progress_store[code] = {
                        "step": step,
                        "progress": progress,
                        "message": message
                    }
                    logger.info(f"[{code}] 进度更新: {step} - {progress}% - {message}")
                
                # 在后台运行分析
                result = await loop.run_in_executor(
                    None,
                    self._run_analysis_sync,
                    code,
                    report_type,
                    progress_callback
                )
                
                # 清理进度信息
                if code in self.progress_store:
                    del self.progress_store[code]
                
                if result:
                    return {"success": True, "result": result}
                else:
                    return {"success": False, "error": "分析失败，未返回结果"}
                    
            except Exception as e:
                logger.error(f"[API] 同步分析失败: {e}")
                # 清理进度信息
                if code in self.progress_store:
                    del self.progress_store[code]
                return {"success": False, "error": str(e)}
        
        @app.post('/api/analysis_history/save')
        async def save_analysis_history_endpoint(data: Dict[str, Any]):
            """
            保存分析历史记录
            
            Args:
                data: 分析结果数据
            
            Returns:
                {"success": true/false}
            """
            try:
                from src.storage import get_db
                db = get_db()
                success = db.save_analysis_history(data)
                return {"success": success}
            except Exception as e:
                logger.error(f"[API] 保存分析历史失败: {e}")
                return {"success": False, "error": str(e)}
        
        @app.get('/api/analysis_history')
        async def get_analysis_history_endpoint(
            limit: int = 50,
            offset: int = 0,
            stock_code: Optional[str] = None
        ):
            """
            获取分析历史记录
            
            Args:
                limit: 返回记录数量
                offset: 偏移量（分页）
                stock_code: 可选的股票代码筛选
            
            Returns:
                {
                    "success": true,
                    "data": [...],
                    "total": 100
                }
            """
            try:
                from src.storage import get_db
                db = get_db()
                
                history = db.get_analysis_history(
                    limit=limit,
                    offset=offset,
                    stock_code=stock_code
                )
                total = db.get_analysis_history_count(stock_code=stock_code)
                
                return {
                    "success": True,
                    "data": [h.to_dict() for h in history],
                    "total": total
                }
            except Exception as e:
                logger.error(f"[API] 获取分析历史失败: {e}")
                return {"success": False, "error": str(e), "data": [], "total": 0}
        
        @app.delete('/api/analysis_history/{history_id}')
        async def delete_analysis_history_endpoint(history_id: int):
            """
            删除分析历史记录
            
            Args:
                history_id: 历史记录ID
            
            Returns:
                {"success": true/false}
            """
            try:
                from src.storage import get_db
                db = get_db()
                success = db.delete_analysis_history(history_id)
                return {"success": success}
            except Exception as e:
                logger.error(f"[API] 删除分析历史失败: {e}")
                return {"success": False, "error": str(e)}
        
        @app.get('/api/watchlist')
        async def get_watchlist():
            """获取自选股列表"""
            try:
                from src.storage import get_db
                db = get_db()
                stocks = db.get_watchlist_stocks()
                return {"success": True, "data": stocks}  # 已经是字典列表
            except Exception as e:
                logger.error(f"获取自选股列表失败: {e}")
                return {"success": False, "error": str(e)}
        
        @app.get('/api/portfolio/summary')
        async def get_portfolio_summary():
            """获取持仓摘要"""
            try:
                from src.portfolio import PortfolioManager
                manager = PortfolioManager()
                summary = manager.get_portfolio_summary()
                return {"success": True, "data": summary}
            except Exception as e:
                logger.error(f"获取持仓摘要失败: {e}")
                return {"success": False, "error": str(e)}
    
    def _run_analysis_sync(self, code: str, report_type: str, progress_callback=None) -> Optional[Dict[str, Any]]:
        """
        同步运行分析（在线程池中执行）
        
        Args:
            code: 股票代码
            report_type: 报告类型
            progress_callback: 进度回调函数 callback(step, progress, message)
            
        Returns:
            分析结果字典
        """
        try:
            from src.config import get_config
            if not self.pipeline:
                logger.error("Pipeline not initialized")
                return None

            report_enum = ReportType.FULL if report_type == 'full' else ReportType.SIMPLE

            # 使用共享的 pipeline 实例
            result = self.pipeline.process_single_stock(
                code=code,
                skip_analysis=False,
                single_stock_notify=self.pipeline.config.single_stock_notify,  # 根据配置决定是否推送
                report_type=report_enum,
                progress_callback=progress_callback
            )
            
            if result and hasattr(result, 'to_dict'):
                result_dict = result.to_dict()
                
                # 自动保存到数据库
                try:
                    from src.storage import get_db
                    db = get_db()
                    db.save_analysis_history(result_dict)
                    logger.info(f"✅ 分析历史已保存到数据库: {code}")
                except Exception as save_err:
                    logger.warning(f"⚠️ 保存分析历史失败（不影响返回结果）: {save_err}")
                
                return result_dict
            elif result:
                return result
            else:
                return None
                
        except Exception as e:
            logger.error(f"同步分析执行失败: {e}")
            return None
    
    def validate_stock_code(self, code: str) -> bool:
        """验证股票代码格式"""
        code = code.upper().strip()
        is_a_stock = re.match(r'^\d{6}$', code)
        is_hk_stock = re.match(r'^HK\d{5}$', code)
        is_us_stock = re.match(r'^[A-Z]{1,5}(\.[A-Z]{1,2})?$', code)
        return bool(is_a_stock or is_hk_stock or is_us_stock)


def register_api():
    """注册所有API端点"""
    ApiEndpoints()
