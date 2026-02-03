# Notification 模块 - 当前状态说明

## ✅ 系统状态：转入模块化阶段

### 当前架构
```
src/
├── notification_legacy.py   # ⚠️ 核心实现 (必须保留，直到迁移完成)
└── notification/            # 🆕 模块化包
    ├── __init__.py          # 路由层：代理请求到 notification_legacy
    ├── models.py            # 数据模型
    ├── detector.py          # 渠道检测
    ├── channels/            # (待迁移)
    └── generators/          # (待迁移)
```

### 为什么保留 notification_legacy.py？
当前 `src/notification/__init__.py` 使用动态导入加载 `notification_legacy.py` 中的类。
**如果删除此文件，整个通知系统将停止工作。**

### 迁移路线图
1. 提取 `NotificationChannel` 等模型到 `models.py` (已完成)
2. 将渠道逻辑逐个迁移到 `channels/*.py` (待进行)
3. 将报告生成逻辑迁移到 `generators/*.py` (待进行)
4. 将 `__init__.py` 的导入指向新模块 (待进行)
5. **最后一步**：删除 `notification_legacy.py` (待进行)

### 导入方式 (保持不变)
```python
# ✅ 现有代码无需修改
from src.notification import NotificationService
# 内部会自动路由到 legacy 实现
```
