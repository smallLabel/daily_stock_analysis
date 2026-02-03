# -*- coding: utf-8 -*-
"""
通知系统 - 渠道检测器
"""

from .models import NotificationChannel


class ChannelDetector:
    """
    渠道检测器 - 简化版
    
    根据配置直接判断渠道类型（不再需要 URL 解析）
    """
    
    @staticmethod
    def get_channel_name(channel: NotificationChannel) -> str:
        """获取渠道中文名称"""
        channel_names = {
            NotificationChannel.WECHAT: "企业微信",
            NotificationChannel.FEISHU: "飞书",
            NotificationChannel.TELEGRAM: "Telegram",
            NotificationChannel.EMAIL: "邮件",
            NotificationChannel.PUSHOVER: "Pushover",
            NotificationChannel.PUSHPLUS: "PushPlus",
            NotificationChannel.DISCORD: "Discord",
            NotificationChannel.ASTRBOT: "AstrBot",
            NotificationChannel.CUSTOM: "自定义渠道",
        }
        return channel_names.get(channel, "未知渠道")
