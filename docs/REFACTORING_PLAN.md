# 项目重构计划 - 大文件拆分
**生成时间**: 2026-02-03

## 📊 重构概览
项目中发现 **14个文件** 超过500行，需要模块化重构。

## 🎯 重构优先级

### 🔴 P0 - 关键路径 (>1000行)
| 文件 | 行数 | 状态 | 优先级理由 |
|------|------|------|----------|
| src/notification.py | 2998 | 🟡 进行中 | 最大文件，核心通知逻辑 |
| data_provider/akshare_fetcher.py | 1455 | ⏸️  待处理 | 数据获取核心，接口众多 |
| src/analyzer.py | 1300 | ⏸️  待处理 | 核心分析引擎 |
| src/search_service.py | 1205 | ⏸️  待处理 | 搜索服务，多个API聚合 |

### 🟡 P1 - 重要模块 (800-1000行)
| 文件 | 行数 | 建议 |
|------|------|------|
| web/templates.py | 941 | 拆分为多个模板组件 |
| data_provider/base.py | 810 | 抽象类+具体实现分离 |
| web/handlers.py | 743 | 按功能域分组 (API/Bot/Page) |
| src/stock_analyzer.py | 732 | 拆分指标计算与分析逻辑 |

### 🟢 P2 - 常规优化 (500-700行)
| 文件 | 行数 | 建议 |
|------|------|------|
| data_provider/efinance_fetcher.py | 705 | 按数据类型拆分 |
| src/sector_stock_picker.py | 662 | 板块/个股分析分离 |
| data_provider/tushare_fetcher.py | 618 | 基础+高级接口分离 |
| src/core/pipeline.py | 613 | 管道阶段模块化 |
| bot/platforms/feishu_stream.py | 527 | 消息处理+事件处理分离 |
| src/storage.py | 509 | 按存储类型拆分 |

---

## 📁 推荐重构方案

### 1. src/notification.py (2998行) → src/notification/
```
notification/
├── __init__.py          # ✅ 已完成
├── models.py            # ✅ 已完成
├── detector.py          # ✅ 已完成
├── service.py           # ⏳ 待迁移
├── channels/            # ⏳ 各渠道实现
│   ├── wechat.py
│   ├── feishu.py
│   ├── telegram.py
│   └── ...
└── generators/          # ⏳ 报告生成器
    ├── daily_report.py
    ├── dashboard.py
    └── single_stock.py
```
**详见**: `docs/REFACTORING_NOTIFICATION.md`

### 2. data_provider/akshare_fetcher.py (1455行)
```
data_provider/akshare/
├── __init__.py          # 统一接口
├── base.py              # 基础类
├── stock.py             # 个股数据 (行情、财务)
├── market.py            # 市场数据 (指数、板块)
├── realtime.py          # 实时行情
└── historical.py        # 历史数据
```

### 3. src/analyzer.py (1300行)
```
src/analyzer/
├── __init__.py
├── core.py              # 核心分析类
├── technical.py         # 技术面分析
├── fundamental.py       # 基本面分析
├── risk.py              # 风险评估
└── signal.py            # 信号生成
```

### 4. src/search_service.py (1205行)
```
src/search_service/
├── __init__.py
├── base.py              # 基础搜索服务
├── providers/
│   ├── easyquant.py     # EasyQuant API
│   ├── akshare.py       # AkShare API
│   └── custom.py        # 自定义搜索
└── aggregator.py        # 多源聚合
```

### 5. web/templates.py (941行)
```
web/templates/
├── __init__.py
├── base.py              # 基础模板
├── config.py            # 配置页面
├── portfolio.py         # 持仓管理页
├── sector.py            # 板块分析页
└── error.py             # 错误页面
```

### 6. web/handlers.py (743行)
```
web/handlers/
├── __init__.py
├── base.py              # 基础类
├── api.py               # API处理器
├── page.py              # 页面处理器
├── bot.py               # Bot webhook
└── portfolio.py         # 持仓API
```

### 7. data_provider/base.py (810行)
```
data_provider/
├── base/
│   ├── __init__.py
│   ├── interface.py     # 抽象接口定义
│   ├── manager.py       # DataFetcherManager
│   └── utils.py         # 工具函数
└── [现有各fetcher保持独立]
```

### 8. src/stock_analyzer.py (732行)
```
src/stock_analyzer/
├── __init__.py
├── core.py              # StockTrendAnalyzer
├── indicators/
│   ├── ma.py            # 均线指标
│   ├── macd.py          # MACD指标
│   ├── volume.py        # 成交量指标
│   └── pattern.py       # 形态识别
└── scoring.py           # 评分系统
```

---

## 🔧 重构原则

### 1. 单一职责
每个模块只负责一个明确的功能域。

### 2. 向后兼容
所有重构必须保持原有API接口不变。

### 3. 增量迁移
- 先备份原文件 (添加 `_legacy` 后缀)
- 在新模块中实现功能
- 通过 `__init__.py` 保持兼容
- 测试通过后删除 legacy 文件

### 4. 测试驱动
每个拆分的模块都应该有对应的单元测试。

---

## 📋 实施步骤

### Step 1: 准备阶段
```bash
# 1. 创建备份
cp src/notification.py src/notification_legacy.py

# 2. 创建新目录结构
mkdir -p src/notification/{channels,generators}
```

### Step 2: 模块迁移
```bash
# 3. 创建基础文件 (__init__.py, models.py, etc.)
# 4. 逐个迁移功能模块
# 5. 更新 __init__.py 导入逻辑
```

### Step 3: 导入更新
```bash
# 6. 搜索所有导入语句
rg "from src.notification import" -l

# 7. 确认兼容性（应该无需修改）
# 8. 可选：使用新的模块化导入
# from src.notification.channels import WeChatChannel
```

### Step 4: 测试验证
```bash
# 9. 运行单元测试
pytest tests/

# 10. 运行集成测试
python -m src.main --analyze XXX
```

### Step 5: 清理
```bash
# 11. 删除 legacy 文件
rm src/notification_legacy.py

# 12. 更新文档
# 13. 提交代码
```

---

## ⚠️  风险控制

### 1. 备份策略
- ✅ 所有原文件重命名为 `*_legacy.py`
- ✅ Git 版本控制提交重构前状态
- ✅ 单独分支进行重构

### 2. 回滚方案
如果重构导致问题：
```bash
# 方案1: 恢复 legacy 文件
cp src/notification_legacy.py src/notification.py
rm -rf src/notification/

# 方案2: Git 回滚
git checkout <pre-refactor-commit>
```

### 3. 渐进式发布
- 先在开发环境验证
- 小范围灰度测试
- 监控日志和错误
- 逐步全量发布

---

## 📊 进度跟踪

| 模块 | 计划开始 | 实际开始 | 完成 | 负责人 |
|------|---------|---------|------|--------|
| notification | 2026-02-03 | 2026-02-03 | 20% | - |
| akshare_fetcher | - | - | 0% | - |
| analyzer | - | - | 0% | - |
| search_service | - | - | 0% | - |
| templates | - | - | 0% | - |
| base | - | - | 0% | - |
| handlers | - | - | 0% | - |
| stock_analyzer | - | - | 0% | - |

---

## 📚 参考资料
- [Python 模块化最佳实践](https://docs.python.org/3/tutorial/modules.html)
- [项目重构指南](./REFACTORING_NOTIFICATION.md)
- 代码规范: PEP 8

---

## ✅ 检查清单

### 重构前
- [ ] 确认文件已备份
- [ ] 创建功能分支
- [ ] 了解现有代码结构
- [ ] 设计新的模块划分
- [ ] 准备测试用例

### 重构中
- [ ] 保持增量提交
- [ ] 每个模块独立验证
- [ ] 更新 `__init__.py` 导出
- [ ] 保持向后兼容
- [ ] 记录重要决策

### 重构后
- [ ] 运行完整测试套件
- [ ] 更新文档和注释
- [ ] 性能对比验证
- [ ] 代码审查
- [ ] 合并到主分支
- [ ] 删除 legacy 文件

---

**最后更新**: 2026-02-03
**状态**: 🟡 进行中
**整体进度**: 7% (1/14 完成基础框架)
