# -*- coding: utf-8 -*-
"""
===================================
Web 服务模块 - 统一架构
===================================

分层架构：
- api.py       - NiceGUI API 端点层
- services.py  - 业务服务层（复用）
- theme.py     - 主题配置
- main_ui.py  - NiceGUI 主入口（统一UI）

旧版（已弃用）：
- server.py    - HTTP 服务器核心
- router.py    - 路由分发
- handlers.py  - 请求处理器
- templates.py - HTML 模板

使用方式：
    # NiceGUI 方式（推荐）
    python -m web.main_ui
    
    # 或者直接运行
    python web/main_ui.py
    
    # 旧版 HTTP 服务器（向后兼容）
    from web import run_server_in_thread, WebServer
    run_server_in_thread(host="127.0.0.1", port=8000)
"""

from web.api import register_api

__all__ = [
    # 新版 NiceGUI
    'register_api',
    # 旧版 HTTP 服务器（向后兼容）
    'WebServer',
    'run_server_in_thread',
]
