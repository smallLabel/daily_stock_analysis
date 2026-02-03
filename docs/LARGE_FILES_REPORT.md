# 大文件检测报告

**检测时间**: 2026-02-03 12:34:09

**发现 17 个文件超过500行**

## 📊 详细列表

| 优先级 | 文件 | 行数 | 建议 |
|--------|------|------|------|
| 🔴 P0 | `src\notification.py` | 3112 | **紧急重构** |
| 🔴 P0 | `src\notification_legacy.py` | 3112 | **紧急重构** |
| 🔴 P0 | `data_provider\fetchers\akshare_fetcher.py` | 1560 | 优先重构 |
| 🔴 P0 | `src\analyzer.py` | 1364 | 优先重构 |
| 🔴 P0 | `src\search_service.py` | 1251 | 优先重构 |
| 🔴 P0 | `web\templates.py` | 1031 | 优先重构 |
| 🟡 P1 | `src\stock_analyzer.py` | 821 | 需要重构 |
| 🟢 P2 | `web\handlers.py` | 780 | 需要重构 |
| 🟢 P2 | `data_provider\fetchers\efinance_fetcher.py` | 728 | 需要重构 |
| 🟢 P2 | `data_provider\fetchers\tushare_fetcher.py` | 691 | 需要重构 |
| 🟢 P2 | `src\sector_stock_picker.py` | 684 | 需要重构 |
| 🟢 P2 | `src\core\pipeline.py` | 630 | 需要重构 |
| 🟢 P2 | `bot\platforms\feishu_stream.py` | 615 | 需要重构 |
| 🟢 P2 | `data_provider\core\manager.py` | 596 | 需要重构 |
| 🟢 P2 | `src\storage.py` | 529 | 需要重构 |
| 🟢 P2 | `src\config.py` | 512 | 需要重构 |
| 🟢 P2 | `src\market_analyzer.py` | 510 | 需要重构 |

## 🎯 重构建议

1. 优先处理 P0 级别的文件（>1000行）
2. 将大文件拆分为模块化的包结构
3. 保持向后兼容性
4. 参考 `docs/REFACTORING_PLAN.md`
