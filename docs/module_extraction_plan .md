# 技术/筹码/舆情分析模块化重构计划

## 目标
将当前混合在 `analyzer.py`、`stock_analyzer.py` 等文件中的技术分析、筹码分析和舆情分析逻辑提取到独立的、可复用的模块中。

## 当前状态分析

### 现有文件结构
```
src/
├── analyzer.py (56KB, 1415 lines)  # 包含 GeminiAnalyzer 和 AI 分析逻辑
├── stock_analyzer.py (31KB, 822 lines)  # 包含 StockTrendAnalyzer，技术指标分析
├── analyzers/
│   ├── __init__.py
│   └── fundamental_analyzer.py  # 基本面分析器（已模块化）
└── core/
    └── pipeline.py  # 主分析流水线
```

### 混合逻辑识别

#### 1. **技术分析** (当前在 `stock_analyzer.py`)
- ✅ 已经相对独立
- 包含：均线分析、MACD、RSI、量能分析、支撑压力位
- 类：`StockTrendAnalyzer`
- **需要做的：** 移动到 `src/analyzers/technical_analyzer.py`

#### 2. **筹码分析** (当前分散在多个文件)
- 在 `analyzer.py` 中的提示词中提到（line 328-330, 391-396）
- 在 `pipeline.py` 中获取和处理（line 232-242, 357-435）
- **数据来源：** 通过 `DataFetcherManager.get_chip_distribution()`
- **需要做的：** 创建 `src/analyzers/chip_analyzer.py` 统一处理筹码数据分析

#### 3. **舆情分析** (当前在 `analyzer.py` 和搜索服务中)
- 在 `analyzer.py` 的 AI 分析中处理新闻和市场情绪
- 在 `search_service.py` 中获取新闻数据
- **需要做的：** 创建 `src/analyzers/sentiment_analyzer.py` 处理舆情数据

## 实施步骤

### Phase 1: 技术分析模块化 ✅
**文件：** `src/analyzers/technical_analyzer.py`

**迁移内容：**
- 从 `stock_analyzer.py` 迁移 `StockTrendAnalyzer` 类
- 保持向后兼容：在 `stock_analyzer.py` 中保留 import 重定向

**接口设计：**
```python
class TechnicalAnalyzer:
    def analyze(self, df: pd.DataFrame, code: str) -> TrendAnalysisResult
    def _calculate_mas(self, df: pd.DataFrame)
    def _calculate_macd(self, df: pd.DataFrame)
    def _calculate_rsi(self, df: pd.DataFrame)
    def _analyze_trend(self, df: pd.DataFrame, result)
    def _analyze_volume(self, df: pd.DataFrame, result)
    def _analyze_support_resistance(self, df: pd.DataFrame, result)
    def format_analysis(self, result: TrendAnalysisResult) -> str
```

### Phase 2: 筹码分析模块化 🆕
**文件：** `src/analyzers/chip_analyzer.py`

**新建内容：**
- 创建 `ChipAnalyzer` 类，统一筹码数据分析逻辑
- 从 `pipeline.py` 提取筹码数据处理逻辑

**接口设计：**
```python
class ChipAnalyzer:
    def analyze(self, chip_data: ChipDistribution) -> ChipAnalysisResult
    def calculate_health_score(self, chip_data) -> float
    def get_chip_status(self, chip_data) -> str  # "健康/一般/警惕"
    def format_analysis(self, result: ChipAnalysisResult) -> str
```

**数据类：**
```python
@dataclass
class ChipAnalysisResult:
    profit_ratio: float  # 获利比例
    avg_cost: float  # 平均成本
    concentration_90: float  # 90%筹码集中度
    concentration_70: float  # 70%筹码集中度
    chip_health: str  # 健康状态
    health_score: float  # 健康评分 0-100
    analysis_summary: str  # 分析摘要
```

### Phase 3: 舆情分析模块化 🆕
**文件：** `src/analyzers/sentiment_analyzer.py`

**新建内容：**
- 创建 `SentimentAnalyzer` 类，处理新闻和市场情绪分析
- 整合搜索服务的新闻数据

**接口设计：**
```python
class SentimentAnalyzer:
    def analyze(self, news_context: str, stock_code: str) -> SentimentAnalysisResult
    def extract_risk_alerts(self, news_context: str) -> List[str]
    def extract_positive_catalysts(self, news_context: str) -> List[str]
    def calculate_sentiment_score(self, news_context: str) -> float
    def format_analysis(self, result: SentimentAnalysisResult) -> str
```

**数据类：**
```python
@dataclass
class SentimentAnalysisResult:
    sentiment_score: float  # 情绪评分 -100 到 100
    risk_alerts: List[str]  # 风险警报
    positive_catalysts: List[str]  # 利好催化剂
    news_summary: str  # 新闻摘要
    market_sentiment: str  # 市场情绪描述
    hot_topics: str  # 相关热点
```

### Phase 4: 更新主流水线集成
**文件：** `src/core/pipeline.py`

**修改点：**
- 导入新的分析器模块
- 在 `analyze_stock()` 方法中调用各个分析器
- 在 `_enhance_context()` 中整合各分析器结果

### Phase 5: 更新 __init__.py 导出
**文件：** `src/analyzers/__init__.py`

**导出所有分析器：**
```python
from src.analyzers.technical_analyzer import TechnicalAnalyzer, TrendAnalysisResult
from src.analyzers.fundamental_analyzer import FundamentalAnalyzer, FundamentalData
from src.analyzers.chip_analyzer import ChipAnalyzer, ChipAnalysisResult
from src.analyzers.sentiment_analyzer import SentimentAnalyzer, SentimentAnalysisResult

__all__ = [
    'TechnicalAnalyzer',
    'TrendAnalysisResult',
    'FundamentalAnalyzer',
    'FundamentalData',
    'ChipAnalyzer',
    'ChipAnalysisResult',
    'SentimentAnalyzer',
    'SentimentAnalysisResult',
]
```

## 向后兼容策略

1. **保留旧导入路径**
   - 在 `stock_analyzer.py` 中保留 `from src.analyzers.technical_analyzer import *`
   - 在必要时添加 DeprecationWarning

2. **渐进式迁移**
   - 先创建新模块并确保测试通过
   - 再逐步更新调用方代码
   - 最后清理旧代码

## 预期收益

### 代码质量
- ✅ 单一职责原则：每个分析器专注一个领域
- ✅ 可测试性：独立模块更易于单元测试
- ✅ 可维护性：清晰的模块边界，易于定位和修改

### 可复用性
- ✅ 各分析器可单独使用
- ✅ 便于在不同场景下组合使用
- ✅ 易于扩展新的分析维度

### 性能优化
- ✅ 可按需加载分析器
- ✅ 支持并行分析
- ✅ 便于实现缓存机制

## 依赖关系

```
pipeline.py
    ├── technical_analyzer.py (技术面)
    ├── fundamental_analyzer.py (基本面) ✅ 已存在
    ├── chip_analyzer.py (筹码)
    └── sentiment_analyzer.py (舆情)
        └── search_service.py (新闻搜索)
```

## 风险与注意事项

1. **数据流完整性**：确保各模块能正确接收和传递数据
2. **配置一致性**：各分析器的配置参数需统一管理
3. **错误处理**：每个模块需要独立的异常处理和降级策略
4. **日志记录**：保持一致的日志格式和级别

## 测试计划

### 单元测试
- [ ] `test_technical_analyzer.py`
- [ ] `test_chip_analyzer.py`
- [ ] `test_sentiment_analyzer.py`

### 集成测试
- [ ] 测试 pipeline 与各分析器的集成
- [ ] 测试分析器之间的数据传递

### 回归测试
- [ ] 确保现有功能不受影响
- [ ] 对比新旧分析结果一致性
