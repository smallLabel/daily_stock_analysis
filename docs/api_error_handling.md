# API错误提示功能说明

## 功能概述

已为板块选股功能添加详细的API和Key可用性错误提示，帮助你快速定位问题。

## 新增功能

### 1. 后端错误追踪

**位置**: `web/handlers.py` 的 `handle_sector_analysis` 方法

**功能**:
- ✅ 检测所有配置的数据源状态
- ✅ 区分可用和不可用的API
- ✅ 捕获并分类错误信息
- ✅ 提供智能化的解决建议

**返回信息包括**:
```json
{
  "success": false,
  "message": "板块选股分析失败",
  "error": "具体错误信息",
  "details": {
    "available_apis": [
      "AkshareFetcher (优先级 1)",
      "TushareFetcher (优先级 -1)"
    ],
    "failed_apis": [
      "SomeFetcher: API Key未配置"
    ],
    "error_messages": [
      "分析错误: 具体错误",
      "可能的原因：数据源API不可用或API Key配置错误"
    ]
  },
  "suggestion": "请检查以下项目：\n1. 网络连接是否正常\n2. API Key是否配置正确（.env文件）\n3. 数据源服务是否可用\n4. 查看详细错误信息"
}
```

### 2. 前端错误展示

**位置**: `web/static/sector_picker.html` 的 `startAnalysis` 函数

**展示内容**:

#### ✅ 可用数据源
- 绿色标识
- 显示数据源名称和优先级
- 列表形式展示所有可用API

#### ❌ 不可用数据源
- 红色标识
- 详细说明哪个API失败及原因
- 帮助快速定位配置问题

#### ⚠️ 错误消息
- 黄色警告框
- 详细的错误信息
- 可能的原因分析

#### 💡 解决建议
- 蓝色提示框
- 智能化的问题解决步骤
- 配置检查清单

## 错误类型

### 1. 数据源配置错误
**错误示例**:
```
❌ 不可用数据源 (1):
- TushareFetcher: API Key未配置
```

**解决方法**:
检查 `.env` 文件，确保配置了必要的API Key：
```env
TUSHARE_TOKEN=your_token_here
```

### 2. 网络连接错误
**错误示例**:
```
❌ 请求失败
错误：Failed to fetch

💡 可能的原因：
• 网络连接中断
• 服务器未响应
• 请检查服务器是否正常运行
```

**解决方法**:
- 检查网络连接
- 确认服务器正常运行
- 检查防火墙设置

### 3. API服务不可用
**错误示例**:
```
⚠️ 错误信息：
• 分析错误: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))
• 可能的原因：数据源API不可用或API Key配置错误
```

**解决方法**:
1. 检查API Key是否正确
2. 验证API服务是否在线
3. 查看API调用限制
4. 等待一段时间后重试

## 使用方法

### 查看详细错误信息

1. 访问板块选股页面: http://127.0.0.1:8000/web/static/sector_picker.html
2. 点击"开始分析"按钮
3. 如果出现错误，页面会显示：
   - 错误标题和详情
   - 可用/不可用的数据源列表
   - 具体错误消息
   - 解决建议

### 检查服务器日志

如果需要更详细的错误信息，可以查看服务器控制台输出，包含完整的错误堆栈。

## 常见问题排查

### Q: 提示"所有数据源都无法获取板块数据"

**检查项目**:
1. ✅ 网络连接是否正常
2. ✅ `.env` 文件中的API Key是否配置
3. ✅ API服务是否有访问限制
4. ✅ 查看详细错误信息中的具体API名称

### Q: 部分数据源可用，但仍然失败

**检查项目**:
1. 查看"可用数据源"列表
2. 确认优先级高的数据源是否可用
3. 检查失败的数据源是否是关键依赖
4. 根据建议修复配置

### Q: 如何添加新的数据源

1. 在 `data_provider/` 目录下创建新的fetcher
2. 实现 `BaseFetcher` 接口
3. 在 `DataFetcherManager` 中注册
4. 配置相应的API Key（如需要）

## 样式说明

错误提示框使用统一的设计语言：

- **绿色框** (✅): 表示正常/可用
- **红色框** (❌): 表示错误/不可用
- **黄色框** (⚠️): 表示警告/注意事项
- **蓝色框** (💡): 表示建议/提示

所有错误提示都包含：
- 清晰的图标
- 彩色边框
- 良好的可读性
- 响应式布局

## 技术实现

### 后端实现要点

```python
# 检查数据源状态
for fetcher in data_manager._fetchers:
    try:
        fetcher_name = fetcher.name
        if hasattr(fetcher, 'api') and fetcher.api is not None:
            error_details["available_apis"].append(f"{fetcher_name} (优先级 {fetcher.priority})")
    except Exception as fe:
        error_details["failed_apis"].append(f"{fetcher_name}: {str(fe)}")
```

### 前端实现要点

```javascript
// 构建详细的错误HTML
if (data.details.available_apis && data.details.available_apis.length > 0) {
    errorHtml += `<div style="background: #e8f5e9; border-left: 4px solid #4caf50;">`;
    errorHtml += `<strong>✅ 可用数据源:</strong><br>`;
    // ... 列表展示
}
```

## 更新日志

**2026-02-03**
- ✅ 添加数据源状态检测
- ✅ 实现详细错误信息收集
- ✅ 优化前端错误展示UI
- ✅ 添加智能化解决建议
- ✅ 美化错误提示框样式

## 下一步改进

- [ ] 添加数据源健康检查端点
- [ ] 实现自动重试机制
- [ ] 添加错误统计和分析
- [ ] 提供配置验证工具
- [ ] 集成日志下载功能
