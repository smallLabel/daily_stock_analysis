# -*- coding: utf-8 -*-
"""
通知系统 - 数据模型
"""

from enum import Enum


class NotificationChannel(str, Enum):
    """通知渠道类型"""
    WECHAT = "wechat"
    FEISHU = "feishu"
    TELEGRAM = "telegram"
    EMAIL = "email"
    PUSHOVER = "pushover"
    PUSHPLUS = "pushplus"
    CUSTOM = "custom"
    DISCORD = "discord"
    ASTRBOT = "astrbot"
    UNKNOWN = "unknown"


# SMTP 服务器配置（自动识别）
SMTP_CONFIGS = {
    # QQ邮箱
    "qq.com": {"server": "smtp.qq.com", "port": 465, "ssl": True},
    "foxmail.com": {"server": "smtp.qq.com", "port": 465, "ssl": True},
    # 网易邮箱
    "163.com": {"server": "smtp.163.com", "port": 465, "ssl": True},
    "126.com": {"server": "smtp.126.com", "port": 465, "ssl": True},
    "yeah.net": {"server": "smtp.yeah.net", "port": 465, "ssl": True},
    # Gmail
    "gmail.com": {"server": "smtp.gmail.com", "port": 587, "ssl": False},
    # Outlook
    "outlook.com": {"server": "smtp-mail.outlook.com", "port": 587, "ssl": False},
    "hotmail.com": {"server": "smtp-mail.outlook.com", "port": 587, "ssl": False},
    # 新浪邮箱
    "sina.com": {"server": "smtp.sina.com", "port": 465, "ssl": True},
    "sina.cn": {"server": "smtp.sina.cn", "port": 465, "ssl": True},
    # 搜狐邮箱
    "sohu.com": {"server": "smtp.sohu.com", "port": 465, "ssl": True},
    # 阿里云
    "aliyun.com": {"server": "smtp.aliyun.com", "port": 465, "ssl": True},
    # 139邮箱
    "139.com": {"server": "smtp.139.com", "port": 465, "ssl": True},
}
