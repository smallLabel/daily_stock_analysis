# 🎯 持仓管理系统 - 快速使用指南

## 📋 目录
1. [快速开始](#快速开始)
2. [功能演示](#功能演示)
3. [API文档](#api文档)
4. [常见问题](#常见问题)

---

## 🚀 快速开始

### 1. 启动WebUI服务
```bash
python main.py --webui-only
```

### 2. 访问持仓管理页面
在浏览器中打开: **http://127.0.0.1:8000/portfolio.html**

### 3. 开始使用
- 📊 查看持仓摘要 (市值、盈亏)
- ➕ 添加交易记录 (买入/卖出)
- 📈 实时更新盈亏数据

---

## 💼 功能演示

### 示例1: 买入股票
1. 填写表单:
   - 股票代码: `600519`
   - 股票名称: `贵州茅台`
   - 交易类型: `买入`
   - 数量: `100`
   - 价格: `1800.00`
   - 手续费: `5.0`

2. 点击"提交交易"

3. 系统自动:
   - 创建交易记录
   - 建立持仓
   - 计算平均成本

### 示例2: 加仓操作
1. 再次买入同一只股票
2. 系统自动更新:
   - 持仓数量 = 原数量 + 新增数量
   - 平均成本 = (原成本 + 新成本) / 总数量

### 示例3: 查看盈亏
1. 持仓列表自动显示:
   - 🟢 绿色: 盈利
   - 🔴 红色: 亏损
   - 盈亏金额和比例

---

## 📡 API 文档

### 1. 获取持仓摘要

**请求:**
```http
GET /api/portfolio/summary
```

**响应:**
```json
{
  "success": true,
  "data": {
    "total_positions": 2,
    "total_market_value": 285000.00,
    "total_cost": 272505.00,
    "total_profit_loss": 12495.00,
    "total_profit_loss_pct": 4.58,
    "positions": [
      {
        "stock_code": "600519",
        "stock_name": "贵州茅台",
        "quantity": 150,
        "avg_cost": 1816.72,
        "current_price": 1900.00,
        "market_value": 285000.00,
        "profit_loss": 12492.50,
        "profit_loss_pct": 4.58
      }
    ]
  }
}
```

### 2. 添加交易记录

**请求:**
```http
POST /api/portfolio/transaction
Content-Type: application/x-www-form-urlencoded

stock_code=600519&stock_name=贵州茅台&type=buy&quantity=100&price=1800&commission=5&notes=建仓
```

**响应:**
```json
{
  "success": true,
  "message": "交易记录已添加",
  "transaction_id": 1
}
```

### 3. 查询交易记录

**请求:**
```http
GET /api/portfolio/transactions?code=600519&limit=10
```

**响应:**
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "stock_code": "600519",
      "stock_name": "贵州茅台",
      "type": "buy",
      "quantity": 100,
      "price": 1800.00,
      "amount": 180000.00,
      "commission": 5.00,
      "tax": 0.00,
      "total_cost": 180005.00,
      "transaction_date": "2026-02-02T23:37:00",
      "notes": "建仓"
    }
  ]
}
```

### 4. 更新持仓价格

**请求:**
```http
POST /api/portfolio/update-prices
Content-Type: application/x-www-form-urlencoded

prices={"600519": 1900.00, "601138": 35.20}
```

**响应:**
```json
{
  "success": true,
  "message": "已更新2个持仓的价格"
}
```

### 5. 设置止盈止损

**请求:**
```http
POST /api/portfolio/set-risk
Content-Type: application/x-www-form-urlencoded

stock_code=600519&stop_loss_price=1750&take_profit_price=2000
```

**响应:**
```json
{
  "success": true,
  "message": "风控参数已设置"
}
```

---

## 🔧 Python编程使用

### 基础用法
```python
from src.portfolio import PortfolioManager, TransactionType

# 1. 初始化管理器
manager = PortfolioManager()

# 2. 添加买入记录
manager.add_transaction(
    stock_code="600519",
    stock_name="贵州茅台",
    transaction_type=TransactionType.BUY,
    quantity=100,
    price=1800.00,
    commission=5.0,
    notes="首次建仓"
)

# 3. 更新价格
manager.update_prices({
    "600519": 1900.00
})

# 4. 获取持仓
positions = manager.get_active_positions()
for pos in positions:
    print(f"{pos.stock_code}: 盈亏{pos.profit_loss:.2f}元 ({pos.profit_loss_pct:.2f}%)")

# 5. 查看组合摘要
summary = manager.get_portfolio_summary()
print(f"总盈亏: {summary['total_profit_loss']:.2f}元")
```

### 高级用法
```python
# 设置止盈止损
manager.set_risk_params(
    stock_code="600519",
    stop_loss_price=1750.00,
    take_profit_price=2000.00
)

# 检查风险提醒
position = manager.get_position("600519")
alerts = position.check_risk_alerts()
for alert in alerts:
    print(alert)

# 查询交易记录
transactions = manager.get_transactions(
    stock_code="600519",
    limit=10
)

# 卖出操作
manager.add_transaction(
    stock_code="600519",
    stock_name="贵州茅台",
    transaction_type=TransactionType.SELL,
    quantity=50,
    price=1900.00,
    commission=2.5,
    tax=1.0,
    notes="部分获利了结"
)
```

---

## ❓ 常见问题

### Q1: 如何计算平均成本?
**A:** 系统自动计算，公式为:
```
平均成本 = (原持仓成本 + 新买入成本 + 所有手续费) / 总持仓数量
```

### Q2: 卖出时如何处理?
**A:** 
- 部分卖出: 持仓数量减少，成本价不变
- 全部卖出: 持仓状态变为"已平仓"

### Q3: 止盈止损如何生效?
**A:** 系统会在价格更新时自动检查:
```python
position = manager.get_position("600519")
alerts = position.check_risk_alerts()  # 获取风险提醒
```

### Q4: 数据存储在哪里?
**A:** SQLite数据库: `data/portfolio.db`

### Q  5: 如何备份数据?
**A:** 直接复制数据库文件:
```bash
cp data/portfolio.db data/portfolio_backup.db
```

### Q6: 支持哪些股票市场?
**A:** 支持A股、港股、美股 (股票代码格式验证)

### Q7: 如何批量导入交易记录?
**A:** 编写Python脚本批量调用API:
```python
transactions = [
    {"code": "600519", "type": "buy", "quantity": 100, "price": 1800},
    {"code": "601138", "type": "buy", "quantity": 500, "price": 35.2}
]

for t in transactions:
    manager.add_transaction(...TransactionType.BUY,...)
```

---

## 🎨 WebUI界面说明

### 1. 顶部摘要卡片
- **持仓股票数**: 当前持有股票种类
- **持仓市值**: 所有持仓的当前总价值
- **总成本**: 所有买入的总成本(含手续费)
- **盈亏金额**: 当前市值 - 总成本
- **盈亏比例**: (盈亏金额 / 总成本) × 100%

### 2. 持仓列表
- 实时显示所有持仓
- 🟢 绿色: 盈利
- 🔴 红色: 亏损
- 点击可查看详细信息

### 3. 交易表单
- 必填项: 股票代码、数量、价格
- 选填项: 股票名称、手续费、印花税、备注
- 提交后自动刷新持仓

### 4. 自动刷新
- 每30秒自动更新一次数据
- 也可手动点击"刷新数据"按钮

---

## 🔍 数据库结构

### positions 表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 |
| stock_code | String | 股票代码 |
| stock_name | String | 股票名称 |
| quantity | Float | 持仓数量 |
| avg_cost | Float | 平均成本 |
| current_price | Float | 当前价格 |
| market_value | Float | 市值 |
| profit_loss | Float | 盈亏金额 |
| profit_loss_pct | Float | 盈亏比例 |
| status | Enum | 状态 (active/closed/partial) |
| stop_loss_price | Float | 止损价 |
| take_profit_price | Float | 止盈价 |

### transactions 表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 |
| stock_code | String | 股票代码 |
| transaction_type | Enum | 交易类型 (buy/sell) |
| quantity | Float | 数量 |
| price | Float | 价格 |
| amount | Float | 成交金额 |
| commission | Float | 手续费 |
| tax | Float | 印花税 |
| transaction_date | DateTime | 交易日期 |
| notes | Text | 备注 |

---

## 🎯 最佳实践

### 1. 交易记录规范
- 买入时填写完整备注 (建仓/加仓原因)
- 卖出时记录卖出理由
- 计算好手续费和印花税

### 2. 风险管理
- 每只股票设置止损价 (通常-5% ~ -10%)
- 设置止盈价 (目标收益)
- 定期检查`check_risk_alerts()`

### 3. 数据维护
- 每日更新价格 (可集成实时行情)
- 定期备份数据库
- 清理已平仓的历史记录

---

## 📞 技术支持

如需帮助，请查看:
- 📖 [完整文档](./feature-extensions.md)
- 🧪 [测试示例](../test_portfolio.py)
- 💻 [源代码](../src/portfolio/)

---

*最后更新: 2026-02-02*
