# -*- coding: utf-8 -*-
"""
通知系统 - 重构中的包
==================

当前状态：过渡期 - 保持向后兼容
从 notification_legacy.py 导入所有接口

TODO: 逐步将功能迁移到模块化结构
- models.py: 数据模型 ✅
- detector.py: 渠道检测 ✅
- channels/: 各渠道实现 (待迁移)
- generators/: 报告生成器 (待迁移)
- service.py: 核心服务类 (待迁移)
"""

# 临时方案：从原文件导入所有内容，确保向后兼容
import sys
import os

# 将 src 目录添加到路径中，以便能导入 notification_legacy
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# 从原始文件导入所有公开接口
try:
    # 尝试从重构后的模块导入
    from .models import NotificationChannel, SMTP_CONFIGS
    from .detector import ChannelDetector
except ImportError:
    # 如果重构模块不存在，从原始文件导入
    pass

# 从 legacy 文件导入核心类（保证兼容性）
try:
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "notification_legacy",
        os.path.join(parent_dir, "notification_legacy.py")
    )
    if spec and spec.loader:
        legacy_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(legacy_module)
        
        # 导入核心类
        # 导入核心类
        NotificationService = legacy_module.NotificationService
        
        # ⚠️ 关键修正：强制使用 legacy 模块中的枚举和辅助类
        # 这是为了确保 NotificationService 内部使用的类与外部导入的类一致（避免类型不匹配）
        NotificationChannel = legacy_module.NotificationChannel
        SMTP_CONFIGS = legacy_module.SMTP_CONFIGS
        ChannelDetector = legacy_module.ChannelDetector
            
except Exception as e:
    # Fallback: 直接从src.notification导入
    import warnings
    warnings.warn(f"Failed to load from legacy module: {e}. Falling back to original import.")
    from src.notification_legacy import NotificationService, NotificationChannel, ChannelDetector, SMTP_CONFIGS

# 公开导出的接口
__all__ = [
    'NotificationService',
    'NotificationChannel',
    'ChannelDetector',
    'SMTP_CONFIGS',
]
