# 股票智能分析系统 - 项目规则

本文档定义了本项目的开发规范、技术栈约定和最佳实践。AI助手在为本项目工作时应遵循这些规则。

---

## 🎯 项目概述

**项目名称**: 股票智能分析系统 (Daily Stock Analysis)  
**主要功能**: 基于AI大模型的A股/港股/美股自选股智能分析系统，每日自动分析并推送决策仪表盘  
**技术栈**: Python 3.10+, NiceGUI, SQLite, AI (Gemini/OpenAI)  
**代码风格**: 标识符使用英文，注释和文档字符串使用中文

## SYSTEM LANGUAGE SETTINGS (HIGHEST PRIORITY)

1.  **Output Language**: You MUST strictly use **Simplified Chinese (简体中文)** for ALL interactions, including:
    -   Chat responses and explanations.
    -   Reasoning and logic analysis.
    -   Walkthrough documentation.
    -   Q&A.

2.  **Code Exception**: Only keep the following in English:
    -   Code snippets.
    -   Variable/Function names.
    -   Technical keywords (e.g., React, SQL, API).
    -   Error logs.

3.  **Behavior Override**: Even if the user asks in English or the provided code is in English, your explanation MUST remain in Chinese. Do NOT switch to English just because the context is technical.

4.  **Translation Protocol**: If you accidentally generate an English sentence (outside of code blocks), you must immediately translate it to Chinese.

## 📁 项目结构

```
daily_stock_analysis/
├── main.py                    # CLI入口，分析流水线入口
├── webui.py                   # Web UI入口(FastAPI)
├── src/                       # 核心业务逻辑
│   ├── config.py             # 配置管理（单例模式）
│   ├── analyzer.py           # AI分析层（Gemini/OpenAI）
│   ├── market_analyzer.py    # 大盘分析
│   ├── stock_analyzer.py     # 个股技术分析
│   ├── storage.py            # SQLite数据持久化
│   ├── notification.py       # 多渠道推送
│   └── search_service.py     # 新闻舆情搜索
├── data_provider/            # 数据获取层（多源策略）
│   └── data_fetcher_manager.py
├── bot/                      # 通知机器人（企微/飞书/Telegram）
│   └── platforms/
├── web/                      # NiceGUI Web界面
│   ├── app.py               # NiceGUI主入口
│   ├── pages/               # 页面模块
│   ├── components/          # UI组件
│   ├── services/            # 服务层（API/业务逻辑）
│   └── utils/               # 工具函数（主题/配色）
└── core/                     # 分析流水线编排
    └── pipeline.py
```

### 关键职责说明

| 模块                      | 职责                                                      |
| ------------------------- | --------------------------------------------------------- |
| `config.py`               | 环境变量加载、全局配置单例                                |
| `analyzer.py`             | AI分析层，封装Gemini/OpenAI调用                           |
| `market_analyzer.py`      | 大盘复盘、板块分析、北向资金                              |
| `stock_analyzer.py`       | 个股技术分析、买卖点计算                                  |
| `storage.py`              | SQLite数据持久化                                          |
| `notification.py`         | 多渠道推送（企微/飞书/Telegram/邮件）                     |
| `search_service.py`       | 新闻舆情搜索（Tavily/SerpAPI/Bocha）                      |
| `data_provider/`          | 数据获取层，多源聚合策略（efinance→akshare→tushare→pytdx）|
| `web/app.py`              | NiceGUI统一Web UI，注册路由和API                          |

---

## 💻 技术栈规范

### 1. Python版本与依赖
- **Python**: 3.10+（必须）
- **核心依赖**:
  - `nicegui`: Web UI框架（唯一UI框架，不使用Flask/Streamlit）
  - `akshare`, `efinance`: 行情数据获取
  - `google-generativeai`: Gemini AI分析
  - `openai`: OpenAI兼容API
  - `python-dotenv`: 环境变量管理
  - `sqlite3`: 数据持久化

### 2. Web界面架构（NiceGUI）
- **框架**: NiceGUI（唯一UI框架）
- **架构说明**:
  - 使用`@ui.page('/')`装饰器注册路由
  - 每个页面路由在函数内部调用`setup_theme()`初始化主题
  - 全局UI设置（CSS/JavaScript）必须在页面函数内部，不能在全局作用域
  - API端点通过`@app.get('/api/xxx')`注册，使用NiceGUI的`app`实例
  
- **UI组件规范**:
  - 使用`web/utils/theme.py`定义的`Colors`和`Styles`常量
  - 保持深色主题风格（`bg-[#09090B]`, `text-zinc-400`）
  - 使用Material Icons图标（`ui.icon('icon_name')`）
  
- **关键注意事项**:
  ```python
  # ✅ 正确：在页面函数内初始化
  @ui.page('/')
  def index_page():
      setup_theme()
      ui.add_css('...')  # 页面特定CSS
      # ... UI构建
  
  # ❌ 错误：全局作用域调用（会导致RuntimeError）
  setup_theme()  # 不能在全局作用域
  ui.add_css('...')  # 不能在全局作用域
  
  @ui.page('/')
  def index_page():
      # ... UI构建
  ```

### 3. 数据获取策略
- **多源降级策略**: `efinance` → `akshare` → `tushare` → `pytdx`
- **重试机制**: 使用`tenacity`装饰器，指数退避（`wait_exponential`）
- **超时设置**: 所有HTTP请求必须设置`timeout=30`

### 4. AI分析层
- **支持模型**: Gemini（免费，推荐）, OpenAI兼容API, DeepSeek, Claude
- **API调用约定**:
  - 使用`tenacity`进行重试（最多3次）
  - 设置合理的`temperature`（0.3-0.7）
  - 使用结构化输出（JSON格式）
  - 记录所有API调用日志

---

## 🔧 代码规范

### 1. 命名约定
- **类名**: PascalCase（`StockAnalyzer`, `NotificationService`）
- **函数/变量**: snake_case（`get_config`, `stock_list`）
- **常量**: UPPER_SNAKE_CASE（`MAX_RETRIES`, `API_DELAY`）
- **私有成员**: 前缀下划线（`_private_method`, `_cache`）
- **代码标识符**: 英文
- **注释/文档字符串**: 中文

### 2. 类型注解
- 必须为所有函数参数和返回值添加类型提示
- 使用`typing`模块（`Dict`, `List`, `Optional`, `Union`）
- 使用`dataclass`定义结构化数据（配置、模型、DTO）
- 使用`Enum`（继承`str`）定义枚举类型

```python
from dataclasses import dataclass
from typing import Dict, List, Optional
from enum import Enum

class ReportType(str, Enum):
    SIMPLE = "simple"
    FULL = "full"

@dataclass
class StockAnalysisResult:
    code: str
    name: str
    current_price: float
    signal: Optional[str] = None
    confidence: float = 0.0
```

### 3. 导入顺序
- 标准库 → 第三方库 → 本地模块
- 使用绝对导入（`from src.config import Config`）
- 使用`isort`自动排序（`--profile black --line-length 120`）

```python
# 标准库
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

# 第三方库
import pandas as pd
from dotenv import load_dotenv
from tenacity import retry, wait_exponential

# 本地模块
from src.config import get_config
from src.storage import get_db
```

### 4. 错误处理
- 使用具体的异常类型（不使用裸`except`）
- 使用`logger.error()`记录错误（禁止使用`print`）
- 向上传播异常，让调用者处理
- API调用使用`@retry`装饰器

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2))
def fetch_stock_data(symbol: str) -> Dict:
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error(f"获取{symbol}数据失败: {e}")
        raise
```

### 5. 日志规范
- 使用`logger = logging.getLogger(__name__)`
- 日志级别:
  - `DEBUG`: 调试详情（变量值、中间结果）
  - `INFO`: 流程进度（开始分析、完成步骤）
  - `WARNING`: 可恢复问题（降级到备用数据源）
  - `ERROR`: 失败情况（API调用失败、数据缺失）
- **严禁提交包含`print()`的代码**（使用`logger`代替）

### 6. 文件头规范

```python
# -*- coding: utf-8 -*-
"""
===================================
模块名 - 简要描述
===================================

职责：
1. 第一项职责
2. 第二项职责
3. 第三项职责

架构说明：
- 说明模块在系统中的位置
- 与其他模块的交互关系
"""

import os
from typing import Any
```

---

## 🏗️ 架构最佳实践

### 1. 配置管理
- 所有配置通过环境变量（`.env`文件）
- 使用`src/config.py`的单例模式获取配置
- 敏感信息（API Key）不得硬编码
- 提供合理的默认值（可选配置）

```python
from src.config import get_config

config = get_config()
api_key = config.gemini_api_key  # 自动从环境变量读取
```

### 2. 数据持久化
- 使用`src/storage.py`的单例数据库（`get_db()`）
- 所有分析结果必须持久化到SQLite
- 使用事务保证数据一致性
- 查询历史记录支持分页

### 3. 通知推送
- 支持多渠道同时推送（企微、飞书、Telegram、邮件）
- 使用Webhook异步通知
- 返回结构化结果供UI展示
- 失败不阻塞主流程（记录日志后继续）

### 4. 模块化原则
- 单一职责：每个模块/类专注一个功能
- 文件大小：单文件不超过500行（超过则拆分）
- 函数长度：单函数不超过50行
- 类方法：每个方法专注一个任务

---

## 🧪 测试与质量检查

### 运行Lint检查（提交前必须执行）
```bash
# 语法检查
python -m py_compile main.py src/*.py data_provider/*.py

# 关键错误检查
flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics

# 代码格式化（行长度120）
black src/ tests/ main.py --line-length 120

# 导入排序
isort src/ tests/ data_provider/ --profile black --line-length 120

# 安全检查
bandit -r src/ --exclude-dir=tests
```

### 运行测试
```bash
# 运行所有测试
pytest -v --tb=short

# 运行单个测试文件
pytest tests/test_storage.py -v --tb=short
```

---

## 🎨 UI/UX规范（NiceGUI）

### 1. 设计风格
- **主题**: 深色主题（Dark Mode）
- **配色方案**:
  - 主色调: `#3B82F6` (蓝色)
  - 背景色: `#09090B` (极深灰)
  - 表面色: `#18181B` (深灰)
  - 边框色: `#27272A` (中灰)
  - 文本色: `#FFFFFF` (白色), `#A1A1AA` (灰色)
  - 成功: `#10B981` (绿色)
  - 警告: `#F59E0B` (琥珀色)
  - 错误: `#EF4444` (红色)

### 2. 组件使用
- 使用`web/components/`中的可复用组件
- 使用`web/utils/theme.py`中的`Colors`和`Styles`常量
- 不要硬编码颜色值，使用主题变量

```python
from web.utils.theme import Colors, Styles

ui.button('分析', color=Colors.PRIMARY).classes(Styles.BUTTON_PRIMARY)
ui.label('错误信息').classes(Styles.TEXT_ERROR)
```

### 3. 响应式设计
- 使用Tailwind CSS类（`flex`, `grid`, `w-full`）
- 使用`ui.row()`和`ui.column()`布局
- 关键操作添加loading状态
- 使用`ui.notify()`显示操作反馈

---

## 🔄 GitHub Actions与自动化

### 工作流约定
- 每个工作日18:00（北京时间）自动执行分析
- 使用GitHub Secrets存储敏感配置
- 支持手动触发（`workflow_dispatch`）
- 失败时发送通知

### 环境变量管理
- 本地开发：`.env`文件
- GitHub Actions：Repository Secrets
- Docker部署：环境变量注入

---

## 📝 文档规范

### README更新
- 新功能必须更新README.md
- 配置项变更必须更新文档
- 使用中文编写用户文档
- 技术文档使用中文混合

### 代码注释
- 复杂逻辑必须添加注释
- API调用必须说明参数和返回值
- 使用中文解释业务逻辑

---

## ⚠️ 项目特定注意事项

### 1. 止损价计算
- 当前`web/app.py`中止损价硬编码为`¥1,350`（第256行）
- **修改时必须同步更新**: 确保从`dashboard`数据中正确提取止损价

### 2. NiceGUI路由注册
- 页面模块import时自动注册路由（使用`@ui.page()`装饰器）
- 修改路由路径时必须同步更新导航链接
- 示例：
  ```python
  import web.pages.settings    # 自动注册 /settings_v2
  import web.pages.watchlist   # 自动注册 /watchlist
  ```

### 3. 数据库迁移
- 修改数据库表结构时必须提供迁移脚本
- 保持向后兼容性
- 在`src/storage.py`中更新schema版本

### 4. API限流
- 使用`ANALYSIS_DELAY`环境变量控制API调用间隔
- 避免触发AI服务的限流保护
- 默认延迟：个股与大盘分析之间等待10秒

### 5. 交易纪律规则
- **严禁追高**: 乖离率 > 5% 自动提示风险
- **趋势交易**: MA5 > MA10 > MA20 多头排列
- **精确点位**: 买入价、止损价、目标价
- **检查清单**: 每项条件以「满足 / 注意 / 不满足」标记

---

## 🔐 安全规范

1. **不得提交**:
   - `.env`文件（已在`.gitignore`）
   - API Keys、Token
   - 个人股票持仓数据

2. **敏感数据处理**:
   - 使用环境变量
   - 日志中脱敏（不打印完整API Key）
   - 数据库文件不提交到Git

3. **依赖安全**:
   - 定期运行`bandit`安全检查
   - 审查第三方库的CVE漏洞
   - 使用最新稳定版本依赖

---

## 📚 参考资源

- **完整配置指南**: `docs/full-guide.md`
- **常见问题**: `docs/FAQ.md`
- **更新日志**: `docs/CHANGELOG.md`
- **开发者指南**: `AGENTS.md`
- **贡献指南**: `docs/CONTRIBUTING.md`

---

## 🤝 工作流程

### 新功能开发
1. 在`task.md`中记录任务
2. 创建功能分支（可选）
3. 编写代码并遵循规范
4. 运行Lint和测试
5. 更新文档（README/CHANGELOG）
6. 提交代码

### Bug修复
1. 复现问题
2. 定位根本原因
3. 编写修复代码
4. 添加测试用例（防止回归）
5. 提交代码

### 代码审查重点
- 是否遵循命名约定
- 是否添加类型注解
- 是否正确处理异常
- 是否使用logger（而非print）
- 是否更新相关文档

---

**最后更新**: 2026-02-05  
**维护者**: AI Coding Assistant (Antigravity)
