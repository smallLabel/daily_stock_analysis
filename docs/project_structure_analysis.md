# 每日股票分析系统 (Daily Stock Analysis) 项目文件结构与功能说明文档

***

## 📂 项目结构全解 (Project Structure Analysis)

本项目是一个基于 AI 大模型 (Gemini/OpenAI) 的智能股票分析系统，后端采用 Python 构建核心分析逻辑，前端使用 NiceGUI 搭建交互界面。

目录结构主要分为两大块：
1.  **`src/`**: 核心业务逻辑、数据处理、AI 分析与策略实现。
2.  **`web/`**: Web 界面、API 服务与用户交互层。

---

### 1. 核心逻辑层 (`src/`)

此目录包含了系统的后台核心功能，包括数据获取、策略回测、AI 分析、通知推送等。

#### 📁 根目录文件

| 文件名 | 功能描述 | 关键类/模块 |
| :--- | :--- | :--- |
| **`analyzer.py`** | **AI 分析器核心**。封装了与 Google Gemini (或 OpenAI) 的交互逻辑，定义了系统提示词 (System Prompt)，负责将股票数据转化为自然语言分析报告。 | `GeminiAnalyzer`, `AnalysisResult` |
| **`backtest.py`** | **向量化回测引擎**。提供简单的 Pandas 向量化回测功能，用于快速验证双均线、RPS、底背离等基础策略的有效性。 | `SimpleBacktester` |
| **`config.py`** | **配置管理中心**。单例模式，负责加载 `.env` 环境变量，管理 API 密钥、数据库路径、代理设置等全局配置。 | `Config`, `get_config` |
| **`enums.py`** | **枚举定义**。定义通用的枚举类型，如交易信号 (Buy/Sell)、趋势状态、报告类型等。 | `SignalType`, `TrendStatus` |
| **`feishu_doc.py`** | **飞书云文档集成**。对接飞书开放平台 API，支持将每日复盘报告自动创建并同步到飞书云文档。 | `FeishuDocManager` |
| **`formatters.py`** | **数据格式化工具**。提供用于生成 Markdown 表格、格式化数字/日期的辅助函数，主要用于报告生成。 | - |
| **`health_rater.py`** | **股性健康度评分**。从策略契合度、收益风险比 (Efficiency)、股性活跃度 (Vitality) 三个维度对个股进行打分。 | `StockHealthRater` |
| **`interactive_runner.py`** | **交互式运行器**。支持在命令行环境下交互式地运行分析任务，方便调试或服务器端无 UI 运行。 | - |
| **`market_analyzer.py`** | **大盘分析器**。负责分析整体市场情绪、指数走势、板块排行，并生成大盘复盘报告。 | `MarketAnalyzer` |
| **`notification.py`** | **通知服务中心**。集成了企业微信、飞书、Telegram、邮件、Pushover 等多渠道推送功能，负责分发分析日报。 | `NotificationService` |
| **`search_service.py`** | **联网搜索服务**。封装 Tavily/SerpAPI/Bocha，用于实时获取个股新闻、公告和市场舆情，解决大模型知识滞后问题。 | `SearchService` |
| **`stock_analyzer.py`** | **技术指标分析器**。计算 MA, MACD, RSI, KDJ, Bollinger 等技术指标，生成量化的买卖信号。 | `StockTrendAnalyzer` |
| **`storage.py`** | **持久化层 (ORM)**。定义 SQLAlchemy 数据模型 (Stock, AnalysisHistory 等)，管理 SQLite 数据库连接与 CRUD 操作。**已实现 UPSERT 逻辑**。 | `DatabaseManager`, `AnalysisHistory` |
| **`scheduler.py`** | **定时任务调度**。基于 `APScheduler`，负责每日定时执行全量股票分析、发送日报等任务。 | - |

#### 📁 子目录模块

**`src/core/` (核心流程)**
| 文件名 | 功能描述 |
| :--- | :--- |
| **`pipeline.py`** | **分析流水线**。系统的“总指挥”，串联数据获取 -> 技术分析 -> AI 解读 -> 结果保存 -> 通知推送的全过程。 |
| **`market_review.py`** | **市场复盘逻辑**。专注于生成每日市场总结的专用流程。 |

**`src/selection/` (选股策略)**
| 文件名 | 功能描述 |
| :--- | :--- |
| **`sector_picker.py`** | **板块选股器**。分析行业板块热度、资金流向，推荐潜力板块及板块内的龙头股。 |
| **`rps_ranker.py`** | **RPS 排名系统**。计算股票的欧奈尔相对强度 (RPS)，筛选市场最强趋势股。 |
| **`theme_hunter.py`** | **题材挖掘**。利用搜索服务挖掘当前市场热点题材（如“低空经济”、“AI应用”）。 |
| **`backtest_picker.py`** | **回测选股**。基于历史回测表现来筛选当前适合交易的股票。 |

**`src/strategies/` (量化策略)**
| 文件名 | 功能描述 |
| :--- | :--- |
| **`backtester.py`** | **事件驱动回测器**。比根目录的 `backtest.py` 更复杂，支持逐日模拟交易、资金管理、胜率/赔率计算。 |
| **`strategies.py`** | **策略库**。定义具体的交易策略类，如 `MacdStrategy`, `RsiMeanReversionStrategy` 等。 |

**`src/portfolio/` (持仓管理)**
| 文件名 | 功能描述 |
| :--- | :--- |
| **`manager.py`** | **持仓管理器**。管理用户的真实/模拟持仓，记录交易流水，计算持仓盈亏、市值等。 |
| **`models.py`** | **持仓数据模型**。定义 `Position` (持仓) 和 `Transaction` (交易记录) 表结构。 |

**`src/notification/` (新版通知架构)**
*注：逐渐替代根目录的单文件 notification.py，采用插件化设计。*
| 文件名 | 功能描述 |
| :--- | :--- |
| **`detector.py`** | 检测环境支持的通知渠道。 |
| **`models.py`** | 定义标准化的消息体结构。 |

---

### 2. Web 界面层 (`web/`)

此目录基于 **NiceGUI** 框架，提供现代化的 Web 用户界面。

#### 📁 根目录文件

| 文件名 | 功能描述 |
| :--- | :--- |
| **`app.py`** | **Web 应用入口**。定义主页面布局、导航栏、全局样式加载，以及启动 FastAPI/NiceGUI 服务。 |

#### 📁 子目录模块

**`web/services/` (Web 业务服务)**
| 文件名 | 功能描述 |
| :--- | :--- |
| **`core.py`** | **核心 Web 服务**。包含 `ConfigService` (读写 .env 配置) 和 `AnalysisService` (异步分析任务线程池管理)。 |
| **`api.py`** | **API 端点**。定义前端调用的后端接口，与 `src/core/pipeline.py` 交互，触发分析并返回结果。 |
| **`handlers.py`** | **IO 处理器**。处理日志流输出 (Log Streaming)，将后台日志实时推送到前端控制台。 |
| **`history.py`** | **历史数据服务**。负责从数据库加载历史分析记录，供前端“历史回顾”页面展示。 |
| **`verification.py`** | **验证服务**。处理 API Key 验证、连通性测试等辅助功能。 |

**`web/pages/` (页面视图)**
| 文件名 | 功能描述 |
| :--- | :--- |
| **`watchlist.py`** | **自选股管理页**。提供自选股的增删改查 UI，展示实时行情概览。 |
| **`settings.py`** | **系统设置页**。提供可视化的配置界面，修改 API Key、提示词模版、通知渠道等。 |

**`web/components/` (UI 组件)**
| 文件名 | 功能描述 |
| :--- | :--- |
| **`pagination.py`** | **分页组件**。通用的分页控件封装。 |

**`web/utils/` (Web 工具)**
| 文件名 | 功能描述 |
| :--- | :--- |
| **`templates.py`** | **HTML 模板**。可能包含一些静态 HTML 片段或 Report 渲染模板。 |
| **`theme.py`** | **主题样式**。管理 CSS 样式、暗色模式切换、全局配色方案。 |

---

### 💡 核心链路总结

1.  **分析触发**: 用户在 Web 界面 (`web/app.py`) 点击“分析” -> 调用 `web/services/api.py`。
2.  **任务调度**: `AnalysisService` (`web/services/core.py`) 将任务放入线程池。
3.  **流程执行**: `StockAnalysisPipeline` (`src/core/pipeline.py`) 启动。
    *   **数据**: 通过 `DataFetcherManager` 获取行情。
    *   **指标**: `StockTrendAnalyzer` (`src/stock_analyzer.py`) 计算技术指标。
    *   **资讯**: `SearchService` (`src/search_service.py`) 抓取新闻。
    *   **大脑**: `GeminiAnalyzer` (`src/analyzer.py`) 生成最终分析报告。
4.  **结果处理**: 结果存入 SQLite (`src/storage.py`) 并通过 `NotificationService` (`src/notification.py`) 推送。
5.  **展示**: 前端轮询状态，分析完成后，`web/services/history.py` 读取新记录并在界面展示。
