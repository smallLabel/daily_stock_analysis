# 大文件重构 - 快速参考

## 🎯 核心信息

### 项目状态
- ✅ **系统稳定运行** - 所有功能正常
- 🟡 **重构进行中** - 已建立框架，待完整迁移
- 📊 **发现17个大文件** - 需要模块化

### 目录结构变化
```diff
src/
+ ├── notification/         # 🆕 模块化包 (进行中)
+ │   ├── __init__.py       # 向后兼容
+ │   ├── models.py
+ │   ├── detector.py
+ │   ├── channels/
+ │   └── generators/
  ├── notification.py       # ⚠️  原始实现(保留)
+ └── notification_legacy.py # 📦 备份
```

## 📚 文档导航

| 需求 | 文档 |
|------|------|
| 了解整体计划 | [`docs/REFACTORING_PLAN.md`](./REFACTORING_PLAN.md) |
| Notification重构细节 | [`docs/REFACTORING_NOTIFICATION.md`](./REFACTORING_NOTIFICATION.md) |
| 查看工作总结 | [`docs/REFACTORING_SUMMARY.md`](./REFACTORING_SUMMARY.md) |
| 大文件清单 | [`docs/LARGE_FILES_REPORT.md`](./LARGE_FILES_REPORT.md) |
| Notification状态 | [`src/notification/README.md`](../src/notification/README.md) |

## 🛠️ 常用命令

### 扫描大文件
```bash
python tools/find_large_files.py
```

### 验证系统
```bash
# 测试导入
python -c "from src.notification import NotificationService; print('OK')"

# 运行WebUI
python webui.py
```

### 查看重构进度
```bash
# 查看notification模块结构
ls -la src/notification/

# 查看文档
cat docs/REFACTORING_SUMMARY.md
```

## ⚡ 快速决策树

### Q1: 我需要修改notification相关代码吗？
- **A**: 继续修改 `src/notification.py`，重构不影响开发

### Q2: notification包导入报错怎么办？
- **A**: 系统会自动fallback到原文件，不影响运行

### Q3: 什么时候删除legacy文件？
- **A**: 完成100%迁移 + 测试通过后

### Q4: 我要添加新功能到notification？
- **A**: 
  - 方案1：直接加到 `notification.py` (快速)
  - 方案2：按新架构加到 `notification/channels/` (推荐)

## 📋 检查清单

### 开发前
- [ ] 了解有重构在进行中
- [ ] 查看相关文档
- [ ] 确认修改位置

### 开发时
- [ ] 导入路径不变：`from src.notification import ...`
- [ ] 测试本地功能
- [ ] 记录改动

### 提交前
- [ ] 重构框架不影响你的更改
- [ ] 代码能正常导入
- [ ] 功能测试通过

## 🆘 遇到问题？

### 导入失败
```python
# 检查路径
import sys
print(sys.path)

# 强制使用原文件
from src.notification_legacy import NotificationService
```

### 重构冲突
1. 暂停使用 `src/notification/` 包
2. 继续使用 `src/notification.py`
3. 等待重构完成

---

**最后更新**: 2026-02-03
**下一次扫描**: 建议每月运行一次 `find_large_files.py`
