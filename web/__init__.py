# -*- coding: utf-8 -*-
"""
===================================
Web 服务模块 - 统一架构
===================================

分层架构：
- services/ - 业务服务层
- pages/    - UI 页面
- utils/    - 工具类 (主题, 模板)
- app.py    - NiceGUI 主入口

使用方式：
    python -m web.app
"""

from web.services.api import register_api

__all__ = [
    'register_api',
]
