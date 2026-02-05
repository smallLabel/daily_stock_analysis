# -*- coding: utf-8 -*-
"""
===================================
Web 服务层 - 业务逻辑
===================================

职责：
1. 配置管理服务 (ConfigService)
2. 分析任务服务 (AnalysisService)
"""

from __future__ import annotations

import os
import re
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Optional, Dict, Any, List, Union

from src.enums import ReportType
from bot.models import BotMessage

logger = logging.getLogger(__name__)

# ============================================================
# 配置管理服务
# ============================================================

_ENV_PATH = os.getenv("ENV_FILE", ".env")

_ENV_KEY_RE = re.compile(
    r"^(?P<prefix>\s*(?P<key>[A-Z_][A-Z0-9_]*)\s*=\s*)(?P<value>.*?)(?P<suffix>\s*)$"
)


class ConfigService:
    """
    配置管理服务
    
    负责 .env 文件中 STOCK_LIST 的读写操作
    """
    
    def __init__(self, env_path: Optional[str] = None):
        self.env_path = env_path or _ENV_PATH
    
    def read_env_text(self) -> str:
        """读取 .env 文件内容"""
        try:
            with open(self.env_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return ""
    
    def write_env_text(self, text: str) -> None:
        """写入 .env 文件内容"""
        with open(self.env_path, "w", encoding="utf-8") as f:
            f.write(text)
    
    def get_stock_list(self) -> str:
        """获取当前自选股列表字符串"""
        return self.get_config('STOCK_LIST')
    
    def set_stock_list(self, stock_list: str) -> str:
        """设置自选股列表"""
        normalized = self._normalize_stock_list(stock_list)
        self.update_config('STOCK_LIST', normalized)
        return normalized

    def get_config(self, key: str) -> str:
        """
        获取指定配置项的值
        
        Args:
            key: 配置键名 (例如: OPENAI_API_KEY)
        """
        env_text = self.read_env_text()
        return self._extract_value(env_text, key)

    def update_config(self, key: str, value: str) -> bool:
        """
        更新单个配置项
        
        Args:
            key: 配置键名
            value: 新值
        """
        env_text = self.read_env_text()
        updated = self._update_env_content(env_text, {key: value})
        self.write_env_text(updated)
        return True

    def update_multiple_configs(self, updates: Dict[str, str]) -> bool:
        """
        批量更新配置项
        
        Args:
            updates: 键值对字典 {key: value}
        """
        env_text = self.read_env_text()
        updated = self._update_env_content(env_text, updates)
        self.write_env_text(updated)
        return True
    
    def get_env_filename(self) -> str:
        """获取 .env 文件名"""
        return os.path.basename(self.env_path)
    
    def _extract_value(self, env_text: str, target_key: str) -> str:
        """从环境文件中提取指定 Key 的值"""
        for line in env_text.splitlines():
            m = _ENV_KEY_RE.match(line)
            if m and m.group("key") == target_key:
                raw = m.group("value").strip()
                # 去除引号
                if (raw.startswith('"') and raw.endswith('"')) or \
                   (raw.startswith("'") and raw.endswith("'")):
                    raw = raw[1:-1]
                return raw
        return ""
    
    def _normalize_stock_list(self, value: str) -> str:
        """规范化股票列表格式"""
        parts = [p.strip() for p in value.replace("\n", ",").split(",")]
        parts = [p for p in parts if p]
        return ",".join(parts)
    
    def _update_env_content(self, env_text: str, updates: Dict[str, str]) -> str:
        """
        更新环境文件内容
        
        策略：
        1. 遍历每一行，如果匹配到 updates 中的 key，则替换值
        2. 如果 updates 中有 key 在文件中未找到，则追加到文件末尾
        """
        lines = env_text.splitlines(keepends=False)
        out_lines: List[str] = []
        
        # 记录已处理的 key
        processed_keys = set()
        
        for line in lines:
            m = _ENV_KEY_RE.match(line)
            if m:
                key = m.group("key")
                if key in updates:
                    new_value = updates[key]
                    # 尝试保留原有引用格式（如果有），这里简单处理，直接替换值部分
                    # 如果原值有引号，最好也根据新值决定是否加引号。
                    # 为简单起见，如果新值包含空格或特殊字符，建议加引号。
                    # 或者，仅替换 value 部分，保留 prefix 和 suffix
                    
                    # 简单的引号处理 logic:
                    # 如果 new_value 包含空格且没有引号，加上双引号
                    # 其实 .env 通常不需要引号除非有特殊字符，但为了安全...
                    
                    out_lines.append(f"{m.group('prefix')}{new_value}{m.group('suffix')}")
                    processed_keys.add(key)
                    continue
            
            out_lines.append(line)
        
        # 处理新增的 key
        new_keys_added = False
        for key, value in updates.items():
            if key not in processed_keys:
                if not new_keys_added and out_lines and out_lines[-1].strip() != "":
                    out_lines.append("") # 添加空行分隔
                out_lines.append(f"{key}={value}")
                new_keys_added = True
        
        trailing_newline = env_text.endswith("\n") if env_text else True
        out = "\n".join(out_lines)
        return out + ("\n" if trailing_newline else "")


# ============================================================
# 分析任务服务
# ============================================================

class AnalysisService:
    """
    分析任务服务
    
    负责：
    1. 管理异步分析任务
    2. 执行股票分析
    3. 触发通知推送
    """
    
    _instance: Optional['AnalysisService'] = None
    _lock = threading.Lock()
    
    def __init__(self, max_workers: int = 3):
        self._executor: Optional[ThreadPoolExecutor] = None
        self._max_workers = max_workers
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self._tasks_lock = threading.Lock()
    
    @classmethod
    def get_instance(cls) -> 'AnalysisService':
        """获取单例实例"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance
    
    @property
    def executor(self) -> ThreadPoolExecutor:
        """获取或创建线程池"""
        if self._executor is None:
            self._executor = ThreadPoolExecutor(
                max_workers=self._max_workers,
                thread_name_prefix="analysis_"
            )
        return self._executor
    
    def submit_analysis(
        self, 
        code: str, 
        report_type: Union[ReportType, str] = ReportType.SIMPLE,
        source_message: Optional[BotMessage] = None
    ) -> Dict[str, Any]:
        """
        提交异步分析任务
        
        Args:
            code: 股票代码
            report_type: 报告类型枚举
            
        Returns:
            任务信息字典
        """
        # 确保 report_type 是枚举类型
        if isinstance(report_type, str):
            report_type = ReportType.from_str(report_type)
        
        task_id = f"{code}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        
        # 提交到线程池
        self.executor.submit(self._run_analysis, code, task_id, report_type, source_message)
        
        logger.info(f"[AnalysisService] 已提交股票 {code} 的分析任务, task_id={task_id}, report_type={report_type.value}")
        
        return {
            "success": True,
            "message": "分析任务已提交，将异步执行并推送通知",
            "code": code,
            "task_id": task_id,
            "report_type": report_type.value
        }
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态"""
        with self._tasks_lock:
            return self._tasks.get(task_id)
    
    def list_tasks(self, limit: int = 20) -> List[Dict[str, Any]]:
        """列出最近的任务"""
        with self._tasks_lock:
            tasks = list(self._tasks.values())
        # 按开始时间倒序
        tasks.sort(key=lambda x: x.get('start_time', ''), reverse=True)
        return tasks[:limit]
    
    def _run_analysis(
        self, 
        code: str, 
        task_id: str, 
        report_type: ReportType = ReportType.SIMPLE,
        source_message: Optional[BotMessage] = None
    ) -> Dict[str, Any]:
        """
        执行单只股票分析
        
        内部方法，在线程池中运行
        
        Args:
            code: 股票代码
            task_id: 任务ID
            report_type: 报告类型枚举
        """
        # 初始化任务状态
        with self._tasks_lock:
            self._tasks[task_id] = {
                "task_id": task_id,
                "code": code,
                "status": "running",
                "start_time": datetime.now().isoformat(),
                "result": None,
                "error": None,
                "report_type": report_type.value
            }
        
        try:
            # 延迟导入避免循环依赖
            from src.config import get_config
            from main import StockAnalysisPipeline
            
            logger.info(f"[AnalysisService] 开始分析股票: {code}")
            
            # 创建分析管道
            config = get_config()
            pipeline = StockAnalysisPipeline(
                config=config,
                max_workers=1,
                source_message=source_message
            )
            
            # 执行单只股票分析（启用单股推送）
            result = pipeline.process_single_stock(
                code=code,
                skip_analysis=False,
                single_stock_notify=True,
                report_type=report_type
            )
            
            if result:
                result_data = {
                    "code": result.code,
                    "name": result.name,
                    "sentiment_score": result.sentiment_score,
                    "operation_advice": result.operation_advice,
                    "trend_prediction": result.trend_prediction,
                    "analysis_summary": result.analysis_summary,
                }
                
                with self._tasks_lock:
                    self._tasks[task_id].update({
                        "status": "completed",
                        "end_time": datetime.now().isoformat(),
                        "result": result_data
                    })
                
                logger.info(f"[AnalysisService] 股票 {code} 分析完成: {result.operation_advice}")
                return {"success": True, "task_id": task_id, "result": result_data}
            else:
                with self._tasks_lock:
                    self._tasks[task_id].update({
                        "status": "failed",
                        "end_time": datetime.now().isoformat(),
                        "error": "分析返回空结果"
                    })
                
                logger.warning(f"[AnalysisService] 股票 {code} 分析失败: 返回空结果")
                return {"success": False, "task_id": task_id, "error": "分析返回空结果"}
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"[AnalysisService] 股票 {code} 分析异常: {error_msg}")
            
            with self._tasks_lock:
                self._tasks[task_id].update({
                    "status": "failed",
                    "end_time": datetime.now().isoformat(),
                    "error": error_msg
                })
            
            return {"success": False, "task_id": task_id, "error": error_msg}


# ============================================================
# 便捷函数
# ============================================================

def get_config_service() -> ConfigService:
    """获取配置服务实例"""
    return ConfigService()


def get_analysis_service() -> AnalysisService:
    """获取分析服务单例"""
    return AnalysisService.get_instance()


def get_all_env_config() -> Dict[str, Any]:
    """
    获取所有环境变量配置
    
    Returns:
        包含所有环境变量配置的字典，按类别分组
    """
    config = {
        'stock_list': os.getenv('STOCK_LIST', ''),
        'ai_config': {
            'gemini_api_key': os.getenv('GEMINI_API_KEY', ''),
            'gemini_model': os.getenv('GEMINI_MODEL', 'gemini-3-flash-preview'),
            'gemini_temperature': os.getenv('GEMINI_TEMPERATURE', '0.7'),
            'openai_api_key': os.getenv('OPENAI_API_KEY', ''),
            'openai_base_url': os.getenv('OPENAI_BASE_URL', ''),
            'openai_model': os.getenv('OPENAI_MODEL', 'gpt-4o-mini'),
            'openai_temperature': os.getenv('OPENAI_TEMPERATURE', '0.7'),
        },
        'search_config': {
            'tavily_api_keys': os.getenv('TAVILY_API_KEYS', ''),
            'serpapi_api_keys': os.getenv('SERPAPI_API_KEYS', ''),
        },
        'notification_config': {
            'wechat_webhook_url': os.getenv('WECHAT_WEBHOOK_URL', ''),
            'feishu_webhook_url': os.getenv('FEISHU_WEBHOOK_URL', ''),
            'telegram_bot_token': os.getenv('TELEGRAM_BOT_TOKEN', ''),
            'telegram_chat_id': os.getenv('TELEGRAM_CHAT_ID', ''),
            'email_sender': os.getenv('EMAIL_SENDER', ''),
            'custom_webhook_urls': os.getenv('CUSTOM_WEBHOOK_URLS', ''),
            'pushover_user_key': os.getenv('PUSHOVER_USER_KEY', ''),
            'pushplus_token': os.getenv('PUSHPLUS_TOKEN', ''),
            'discord_webhook_url': os.getenv('DISCORD_WEBHOOK_URL', ''),
            'serverchan3_sendkey': os.getenv('SERVERCHAN3_SENDKEY', ''),
        },
        'webui_config': {
            'webui_enabled': os.getenv('WEBUI_ENABLED', 'false'),
            'webui_host': os.getenv('WEBUI_HOST', '127.0.0.1'),
            'webui_port': os.getenv('WEBUI_PORT', '8000'),
        },
        'schedule_config': {
            'schedule_enabled': os.getenv('SCHEDULE_ENABLED', 'false'),
            'schedule_time': os.getenv('SCHEDULE_TIME', '18:00'),
            'market_review_enabled': os.getenv('MARKET_REVIEW_ENABLED', 'false'),
        },
        'proxy_config': {
            'use_proxy': os.getenv('USE_PROXY', 'false'),
            'proxy_host': os.getenv('PROXY_HOST', '127.0.0.1'),
            'proxy_port': os.getenv('PROXY_PORT', '7890'),
        },
        'system_config': {
            'log_dir': os.getenv('LOG_DIR', './logs'),
            'log_level': os.getenv('LOG_LEVEL', 'INFO'),
            'max_workers': os.getenv('MAX_WORKERS', '3'),
            'debug': os.getenv('DEBUG', 'false'),
        },
        'data_source_config': {
            'efinance_priority': os.getenv('EFINANCE_PRIORITY', '0'),
            'akshare_priority': os.getenv('AKSHARE_PRIORITY', '1'),
            'tushare_priority': os.getenv('TUSHARE_PRIORITY', '2'),
            'yfinance_priority': os.getenv('YFINANCE_PRIORITY', '4'),
        },
    }
    return config
