## 修复 SQLAlchemy DetachedInstanceError 问题

### 问题分析
`WatchlistRepository.get_all()` 返回 ORM 对象列表，Session 关闭后访问 `s.stock_code`、`s.stock_name` 等属性会触发 `DetachedInstanceError`。

### 修复方案

#### 1. 修改 `WatchlistRepository` 返回字典
**文件**: `data_provider/repository/stock_repo.py`

修改以下方法：
- `get_all()` → 返回 `List[Dict[str, Any]]` 而不是 `List[WatchlistStock]`
- `get_codes()` → 直接在 session 内提取代码
- `get_names_dict()` → 直接在 session 内构建字典

#### 2. 修改调用方处理字典
**文件**: `web/pages/watchlist.py`
- `load_watchlist()` 函数处理字典列表

**文件**: `web/services/api.py`
- `get_watchlist()` 处理字典列表

**文件**: `web/services/handlers.py`
- `handle_get_watchlist()` 处理字典列表

### 验证
- 重启服务器
- 加载自选股页面，确认无错误