# Notification 模块重构指南

## 📊 当前状态
- **原文件**: `src/notification_legacy.py` (3113行，已备份)
- **重构进度**: 20% (基础结构已建立)

## 🎯 重构目标
将超大单文件 (3113行) 拆分为模块化的包结构，提高可维护性和可测试性。

## 📁 目标结构
```
src/notification/
├── __init__.py              # ✅ 向后兼容接口
├── models.py                # ✅ 数据模型
├── detector.py              # ✅ 渠道检测器
├── service.py               # ⏳ 核心服务类 (待迁移)
├── generators/              # ⏳ 报告生成器
│   ├── __init__.py
│   ├── daily_report.py      # 日报生成 (line 333-524)
│   ├── dashboard.py         # 仪表盘生成 (line 551-966)
│   └── single_stock.py      # 单股报告 (line 1032-1142)
└── channels/                # ⏳ 各渠道实现
    ├── __init__.py
    ├── base.py              # 基础抽象类
    ├── wechat.py            # 企业微信 (line 1144-1413)
    ├── feishu.py            # 飞书 (line 1415-1857)
    ├── telegram.py          # Telegram (line 1995-2089)
    ├── email.py             # 邮件 (line 2091-2289)
    ├── discord.py           # Discord (line 2291-2383)
    ├── pushover.py          # Pushover (line 2385-2448)
    └── pushplus.py          # PushPlus (line 2450-2503)
```

## 🔧 重构步骤

### Phase 1: 基础设施 (✅ 已完成)
- [x] 创建目录结构
- [x] 提取数据模型 (`models.py`)
- [x] 提取渠道检测器 (`detector.py`)
- [x] 创建向后兼容的 `__init__.py`
- [x] 备份原文件为 `notification_legacy.py`

### Phase 2: 渠道抽象 (下一步)
1. **创建基础渠道类** (`channels/base.py`)
   ```python
   class BaseChannel(ABC):
       @abstractmethod
       def send(self, content: str) -> bool:
           pass
       
       @abstractmethod
       def is_configured(self) -> bool:
           pass
   ```

2. **迁移企业微信渠道** (`channels/wechat.py`)
   - 从 line 1144 提取 `send_to_wechat`
   - 提取分批发送逻辑 `_send_wechat_chunked` (line 1195)
   - 提取强制分割 `_send_wechat_force_chunked` (line 1304)
   - 提取消息构建 `_gen_wechat_payload` (line 1376)

3. **迁移飞书渠道** (`channels/feishu.py`)
   - 从 line 1415 提取 `send_to_feishu`
   - 提取分批逻辑 (line 1459-1603)
   - 提取 Markdown 卡片格式化

4.  **迁移其他渠道**
   - Telegram → `channels/telegram.py`
   - Email → `channels/email.py`
   - Discord → `channels/discord.py`
   - Pushover → `channels/pushover.py`
   - PushPlus → `channels/pushplus.py`

### Phase 3: 报告生成器
1. **日报生成器** (`generators/daily_report.py`)
   - 提取 `generate_daily_report` (line 333-524)
   - 提取 `_get_signal_level` (line 526-549)

2. **仪表盘生成器** (`generators/dashboard.py`)
   - 提取 `generate_dashboard_report` (line 551-831)
   - 提取 `generate_wechat_dashboard` (line 833-966)
   - 提取 `generate_wechat_summary` (line 968-1030)

3. **单股报告生成器** (`generators/single_stock.py`)
   - 提取 `generate_single_stock_report` (line 1032-1142)

### Phase 4: 核心服务类 (`service.py`)
1. 保留 `NotificationService` 的核心逻辑：
   - 渠道检测与初始化
   - 多渠道并发推送
   - 上下文渠道管理 (钉钉/飞书 Stream 模式)

2. 使用组合模式集成：
   - 报告生成器
   - 各渠道实现

### Phase 5: 测试与验证
1. 创建单元测试
2. 集成测试
3. 向后兼容性测试

## 🔄 当前兼容性方案
`src/notification/__init__.py` 当前采用动态导入策略：
1. 优先从新模块导入 (models, detector)
2. 核心类从 `notification_legacy.py` 导入
3. 确保所有现有代码无需修改即可工作

## ⚠️ 注意事项
1. **不要删除** `notification_legacy.py` - 它是当前的实际实现
2. **保持接口一致** - 重构后的接口必须与原版完全兼容
3. **增量迁移** - 每迁移一个模块就进行测试
4. **更新 `__init__.py`** - 完成迁移后更新导入逻辑

## 📊 预期收益
- **可维护性**: 每个文件 < 500 行
- **可测试性**: 模块间解耦，便于单元测试
- **可扩展性**: 新增渠道只需实现 `BaseChannel` 接口
- **可读性**: 清晰的模块职责划分

## 🚀 快速开始重构
```bash
# 1. 确认备份存在
ls src/notification_legacy.py

# 2. 开始迁移第一个渠道 (示例：企业微信)
# 复制 line 1144-1413 到 src/notification/channels/wechat.py

# 3. 运行测试
python -m pytest tests/test_notification_wechat.py

# 4. 更新 service.py 使用新的渠道类
# 5. 更新 __init__.py 导入
```

## 📝 迁移检查清单
- [ ] channels/base.py - 基础抽象类
- [ ] channels/wechat.py - 企业微信
- [ ] channels/feishu.py - 飞书
- [ ] channels/telegram.py - Telegram
- [ ] channels/email.py - 邮件
- [ ] channels/discord.py - Discord
- [ ] channels/pushover.py - Pushover
- [ ] channels/pushplus.py - PushPlus
- [ ] generators/daily_report.py - 日报
- [ ] generators/dashboard.py - 仪表盘
- [ ] generators/single_stock.py - 单股
- [ ] service.py - 核心服务
- [ ] tests/ - 单元测试
- [ ] 删除 notification_legacy.py
- [ ] 更新文档
