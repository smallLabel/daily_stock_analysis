# 模块化分析器 - 快速开始指南

## 📚 概述

本项目已将股票分析功能模块化，提取出三个独立的分析器：

- **📊 技术分析器** (`technical_analyzer.py`) - 均线、MACD、RSI等技术指标分析
- **💎 筹码分析器** (`chip_analyzer.py`) - 筹码分布、获利比例、集中度分析
- **📰 舆情分析器** (`sentiment_analyzer.py`) - 新闻情感、风险警报、利好催化剂分析

## 🚀 快速开始

### 1. 技术分析

```python
from src.analyzers import StockTrendAnalyzer
import pandas as pd

# 准备K线数据 (DataFrame需包含: date, open, high, low, close, volume)
df = pd.read_csv('stock_data.csv')

# 创建分析器并执行分析
analyzer = StockTrendAnalyzer()
result = analyzer.analyze(df, code='600519')

# 查看分析结果
print(f"趋势状态: {result.trend_status.value}")
print(f"买入信号: {result.buy_signal.value}")
print(f"综合评分: {result.signal_score}/100")

# 打印格式化报告
print(analyzer.format_analysis(result))
```

### 2. 筹码分析

```python
from src.analyzers import ChipAnalyzer
from data_provider.realtime_types import ChipDistribution

# 准备筹码数据
chip_data = ChipDistribution(
    code='600519',
    profit_ratio=0.65,      # 获利比例
    avg_cost=1500.0,        # 平均成本
    concentration_90=0.12,  # 90%筹码集中度
    concentration_70=0.08,  # 70%筹码集中度
    cost_90_low=1400.0,     # 90%成本下限
    cost_90_high=1600.0,    # 90%成本上限
)

# 创建分析器并执行分析
analyzer = ChipAnalyzer()
result = analyzer.analyze(chip_data, current_price=1650.0)

# 查看分析结果
print(f"筹码健康: {result.chip_health}")
print(f"健康评分: {result.health_score}/100")

# 打印格式化报告
print(analyzer.format_analysis(result))
```

### 3. 舆情分析

```python
from src.analyzers import SentimentAnalyzer

# 准备新闻数据
news_context = """
公司发布2024年度业绩预增公告，预计净利润同比增长80%以上。
公司与知名企业达成战略合作协议。
公司获得政府补贴5000万元。
公司董事长增持公司股份。
部分股东计划减持不超过2%股份。
"""

# 创建分析器并执行分析
analyzer = SentimentAnalyzer()
result = analyzer.analyze(
    news_context=news_context,
    stock_code='600519',
    stock_name='贵州茅台'
)

# 查看分析结果
print(f"舆情评分: {result.sentiment_score:+.1f}/100")
print(f"市场情绪: {result.sentiment_label}")
print(f"风险数量: {len(result.risk_alerts)}")
print(f"利好数量: {len(result.positive_catalysts)}")

# 打印格式化报告
print(analyzer.format_analysis(result))
```

### 4. 综合分析

```python
from src.analyzers import (
    StockTrendAnalyzer,
    ChipAnalyzer,
    SentimentAnalyzer,
)

# 执行所有分析
tech_result = StockTrendAnalyzer().analyze(df, code='600519')
chip_result = ChipAnalyzer().analyze(chip_data, current_price)
sent_result = SentimentAnalyzer().analyze(news_context, '600519')

# 综合判断
if (tech_result.signal_score >= 70 and 
    chip_result.health_score >= 70 and 
    sent_result.sentiment_score > 20):
    print("✅ 多项指标向好，可考虑买入")
elif len(sent_result.risk_alerts) >= 3:
    print("⚠️ 重大风险，建议规避")
else:
    print("🟡 综合研判，谨慎决策")
```

## 📖 详细文档

### 技术分析器 API

#### `StockTrendAnalyzer`

**方法**:
- `analyze(df: pd.DataFrame, code: str) -> TrendAnalysisResult`
- `format_analysis(result: TrendAnalysisResult) -> str`

**关键字段** (`TrendAnalysisResult`):
- `trend_status` - 趋势状态 (TrendStatus枚举)
- `buy_signal` - 买入信号 (BuySignal枚举)
- `signal_score` - 综合评分 (0-100)
- `ma5, ma10, ma20` - 均线值
- `bias_ma5` - MA5乖离率
- `macd_dif, macd_dea` - MACD指标
- `rsi_6, rsi_12, rsi_24` - RSI指标
- `volume_status` - 量能状态
- `signal_reasons` - 买入理由列表
- `risk_factors` - 风险因素列表

---

### 筹码分析器 API

#### `ChipAnalyzer`

**方法**:
- `analyze(chip_data: ChipDistribution, current_price: float) -> ChipAnalysisResult`
- `calculate_health_score(result, current_price) -> float`
- `format_analysis(result: ChipAnalysisResult) -> str`

**关键字段** (`ChipAnalysisResult`):
- `chip_health` - 健康等级 ("健康"/"一般"/"警惕")
- `health_score` - 健康评分 (0-100)
- `profit_ratio` - 获利比例 (0-1)
- `avg_cost` - 平均成本
- `concentration_90` - 90%筹码集中度
- `profit_status` - 获利状态描述
- `concentration_status` - 集中度状态描述
- `cost_position` - 成本位置描述
- `trading_implications` - 交易含义
- `risk_points` - 风险点列表

---

### 舆情分析器 API

#### `SentimentAnalyzer`

**方法**:
- `analyze(news_context: str, stock_code: str, stock_name: str) -> SentimentAnalysisResult`
- `extract_risk_alerts(news_context: str) -> List[str]`
- `extract_positive_catalysts(news_context: str) -> List[str]`
- `calculate_sentiment_score(...) -> float`
- `format_analysis(result: SentimentAnalysisResult) -> str`

**关键字段** (`SentimentAnalysisResult`):
- `sentiment_score` - 情绪评分 (-100 到 100)
- `sentiment_label` - 情绪标签 ("极度看多"/"看多"/"中性"/"看空"/"极度看空")
- `risk_alerts` - 风险警报列表
- `positive_catalysts` - 利好催化剂列表
- `news_summary` - 新闻摘要
- `market_sentiment` - 市场情绪描述
- `hot_topics` - 相关热点
- `impact_level` - 影响程度 ("高"/"中"/"低")
- `trading_suggestion` - 交易建议

---

## 🔧 配置说明

### 技术分析器配置

可通过修改类常量调整分析参数：

```python
class StockTrendAnalyzer:
    BIAS_THRESHOLD = 5.0        # 乖离率阈值（%）
    VOLUME_SHRINK_RATIO = 0.7   # 缩量判断阈值
    VOLUME_HEAVY_RATIO = 1.5    # 放量判断阈值
    MACD_FAST = 12              # MACD快线周期
    MACD_SLOW = 26              # MACD慢线周期
    MACD_SIGNAL = 9             # MACD信号线周期
    RSI_SHORT = 6               # 短期RSI周期
    RSI_MID = 12                # 中期RSI周期
    RSI_LONG = 24               # 长期RSI周期
```

### 筹码分析器配置

```python
class ChipAnalyzer:
    PROFIT_WEIGHT = 0.4         # 获利比例权重
    CONCENTRATION_WEIGHT = 0.3  # 集中度权重
    COST_POSITION_WEIGHT = 0.3  # 成本位置权重
    
    CONCENTRATION_TIGHT = 0.08   # 高度集中阈值
    CONCENTRATION_MODERATE = 0.15 # 较集中阈值
    CONCENTRATION_LOOSE = 0.25    # 分散阈值
```

### 舆情分析器配置

```python
class SentimentAnalyzer:
    # 修改关键词库
    RISK_KEYWORDS = {
        '减持': 5,
        '业绩预亏': 8,
        # ... 更多关键词
    }
    
    POSITIVE_KEYWORDS = {
        '增持': 5,
        '业绩预增': 7,
        # ... 更多关键词
    }
```

---

## 🧪 测试

### 运行测试套件

```bash
python test_modular_analyzers.py
```

测试覆盖：
- ✅ 技术分析器功能测试
- ✅ 筹码分析器功能测试
- ✅ 舆情分析器功能测试
- ✅ 向后兼容性测试
- ✅ 统一导入测试

### 运行示例

```bash
python examples_modular_analyzers.py
```

示例包括：
- 技术分析器单独使用
- 筹码分析器单独使用
- 舆情分析器单独使用
- 综合分析（组合使用）

---

## 📁 文件结构

```
src/analyzers/
├── __init__.py                 # 统一导出
├── technical_analyzer.py       # 技术分析器
├── chip_analyzer.py            # 筹码分析器
├── sentiment_analyzer.py       # 舆情分析器
└── fundamental_analyzer.py     # 基本面分析器

.agent/
├── modular_analyzers_summary.md  # 重构总结
└── module_extraction_plan.md     # 重构计划

项目根目录/
├── test_modular_analyzers.py     # 测试套件
└── examples_modular_analyzers.py # 使用示例
```

---

## 🔄 迁移指南

### 从旧版本迁移

**旧代码** (仍然可用，但会有弃用警告):
```python
from src.stock_analyzer import StockTrendAnalyzer
```

**新代码** (推荐):
```python
from src.analyzers import StockTrendAnalyzer
```

### 兼容性说明

- ✅ 旧代码仍然可以运行
- ⚠️ 会显示 `DeprecationWarning`
- 🔄 建议逐步迁移到新模块
- 📦 新模块提供更好的可组合性

---

## 💡 最佳实践

### 1. 模块组合使用

```python
def comprehensive_analysis(stock_code, df, chip_data, news_context):
    """综合分析函数"""
    # 技术面
    tech = StockTrendAnalyzer().analyze(df, stock_code)
    
    # 筹码面
    chip = ChipAnalyzer().analyze(chip_data, tech.current_price)
    
    # 舆情面
    sent = SentimentAnalyzer().analyze(news_context, stock_code)
    
    # 综合评分
    score = (tech.signal_score + chip.health_score) / 2
    
    # 决策逻辑
    if score >= 70 and sent.sentiment_score > 0:
        return "买入"
    elif len(sent.risk_alerts) >= 3:
        return "观望"
    else:
        return "持有"
```

### 2. 结果缓存

```python
from functools import lru_cache

@lru_cache(maxsize=100)
def cached_technical_analysis(stock_code, date):
    """带缓存的技术分析"""
    df = load_data(stock_code, date)
    analyzer = StockTrendAnalyzer()
    return analyzer.analyze(df, stock_code)
```

### 3. 批量分析

```python
def batch_analyze(stock_codes):
    """批量分析多只股票"""
    results = []
    analyzer = StockTrendAnalyzer()
    
    for code in stock_codes:
        df = load_data(code)
        result = analyzer.analyze(df, code)
        results.append((code, result))
    
    return results
```

---

## 🐛 常见问题

### Q: 如何获取筹码数据？

A: 筹码数据通过 `DataFetcherManager.get_chip_distribution()` 获取：

```python
from data_provider import DataFetcherManager

manager = DataFetcherManager()
chip_data = manager.get_chip_distribution('600519')
```

### Q: 新闻数据从哪里来？

A: 新闻数据通过搜索服务获取：

```python
from src.search_service import SearchService

search = SearchService()
news = search.search_news('600519 贵州茅台')
```

### Q: 如何调整评分权重？

A: 直接修改分析器类的常量：

```python
# 修改筹码分析器评分权重
ChipAnalyzer.PROFIT_WEIGHT = 0.5
ChipAnalyzer.CONCENTRATION_WEIGHT = 0.3
ChipAnalyzer.COST_POSITION_WEIGHT = 0.2
```

---

## 📞 联系与支持

- 📖 详细文档: `.agent/modular_analyzers_summary.md`
- 🧪 测试代码: `test_modular_analyzers.py`
- 💡 使用示例: `examples_modular_analyzers.py`
- 📋 重构计划: `.agent/module_extraction_plan.md`

---

## 📝 变更日志

### v1.0.0 (2024-02-07)

**新增**:
- ✅ 技术分析器模块 (`technical_analyzer.py`)
- ✅ 筹码分析器模块 (`chip_analyzer.py`)
- ✅ 舆情分析器模块 (`sentiment_analyzer.py`)

**改进**:
- ✅ 模块化架构，提高代码可维护性
- ✅ 统一导出接口，简化使用
- ✅ 向后兼容，平滑迁移

**弃用**:
- ⚠️ `src.stock_analyzer` 模块 (使用 `src.analyzers.technical_analyzer` 替代)

---

## 📄 许可证

本项目采用 MIT 许可证。
