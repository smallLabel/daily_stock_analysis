# -*- coding: utf-8 -*-
"""
===================================
WebUI 入口文件 (向后兼容)
===================================

本文件保持向后兼容，实际实现已迁移到 NiceGUI

架构说明：
    web/
    ├── api.py         - NiceGUI API 端点层
    ├── main_ui.py     - NiceGUI 主入口（推荐使用）
    ├── services.py    - 业务服务层（复用）
    ├── theme.py       - 主题配置
    ├── server.py      - HTTP 服务器（旧版，已弃用）
    ├── router.py      - 路由分发（旧版，已弃用）
    ├── handlers.py    - 请求处理器（旧版，已弃用）
    └── templates.py   - HTML 模板（旧版，已弃用）

使用方式：
    # 推荐方式：使用 NiceGUI
    python web/main_ui.py
    
    # 向后兼容：使用本文件
    python webui.py
    
    # 命令行参数
    WEBUI_HOST=0.0.0.0 WEBUI_PORT=8000 python webui.py
"""

from __future__ import annotations

import os
import logging

# 从 web 包导入（新架构）
from nicegui import ui

logger = logging.getLogger(__name__)


def _start_bot_stream_clients() -> None:
    """启动 Bot Stream 模式客户端（如果已配置）"""
    from src.config import get_config
    config = get_config()
    
    # 钉钉 Stream 模式
    if config.dingtalk_stream_enabled:
        try:
            from bot.platforms import start_dingtalk_stream_background, DINGTALK_STREAM_AVAILABLE
            if DINGTALK_STREAM_AVAILABLE:
                if start_dingtalk_stream_background():
                    logger.info("[WebUI] 钉钉 Stream 客户端已在后台启动")
                else:
                    logger.warning("[WebUI] 钉钉 Stream 客户端启动失败")
            else:
                logger.warning("[WebUI] 钉钉 Stream 模式已启用但 SDK 未安装")
                logger.warning("[WebUI] 请运行: pip install dingtalk-stream")
        except Exception as e:
            logger.error(f"[WebUI] 启动钉钉 Stream 客户端失败: {e}")

    # 飞书 Stream 模式
    if getattr(config, 'feishu_stream_enabled', False):
        try:
            from bot.platforms import start_feishu_stream_background, FEISHU_SDK_AVAILABLE
            if FEISHU_SDK_AVAILABLE:
                if start_feishu_stream_background():
                    logger.info("[WebUI] 飞书 Stream 客户端已在后台启动")
                else:
                    logger.warning("[WebUI] 飞书 Stream 客户端启动失败")
            else:
                logger.warning("[WebUI] 飞书 Stream 模式已启用但 SDK 未安装")
                logger.warning("[WebUI] 请运行: pip install lark-oapi")
        except Exception as e:
            logger.error(f"[WebUI] 启动飞书 Stream 客户端失败: {e}")


def main() -> int:
    """
    主入口函数
    
    支持环境变量配置:
        WEBUI_HOST: 监听地址 (默认 127.0.0.1)
        WEBUI_PORT: 监听端口 (默认 8000)
    """
    host = os.getenv("WEBUI_HOST", "127.0.0.1")
    port = int(os.getenv("WEBUI_PORT", "8000"))
    
    print(f"WebUI running: http://{host}:{port}")
    print("使用 NiceGUI 框架")
    print()
    print("功能:")
    print("  - 个股分析")
    print("  - 自选股管理")
    print("  - 持仓管理")
    print("  - 分析记录查询")
    print()
    
    # 启动 Bot Stream 客户端（如果配置了）
    _start_bot_stream_clients()
    
    # 导入 main_ui 模块会执行全局UI构建代码
    import web.main_ui
    
    # 启动服务器
    try:
        ui.run(
            title='股票每日分析',
            dark=True,
            host=host,
            port=port,
            show=False
        )
    except KeyboardInterrupt:
        pass
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
