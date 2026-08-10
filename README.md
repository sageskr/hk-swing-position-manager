# HK Swing Position Manager

港股持仓波段交易决策辅助 Skill。它帮助用户把已有持仓拆分为长期 Core Position 与可交易 Swing Position，使用价格区间提供上涨分批卖出、下跌分批买回的手动交易建议，并比较交易成本与净收益。所有买入和卖出决定由投资人自行作出。

## Skill 调用关键词

保留完整名称，同时支持英文简写和中文关联关键词：

| 类型 | 关键词 |
|---|---|
| 完整名称 | `HK Swing Position Manager` |
| 英文简写 | `hkswing` |
| 中文核心关键词 | `港股售卖建议`、`港股卖出建议`、`港股买卖建议` |
| 中文关联关键词 | `港股波段建议`、`港股持仓分析`、`港股交易分析`、`港股波段管理`、`港股持仓管理` |

以下写法等价：

```text
请使用 HK Swing Position Manager 分析 Tencent 0700.HK。
```

```text
hkswing 分析 Tencent 0700.HK，先给结论。
```

```text
港股售卖建议：请分析 Tencent 0700.HK 最近行情。
```

```text
港股持仓分析：我的 0700.HK 持仓成本是 HK$303.508。
```

这些关键词只是调用别名，仍然遵守所有原有规则：结论优先、BUY/SELL/HOLD/WAIT 互斥、只提供建议、不执行订单，并读取本地 State（如果该环境存在）。只有关键词与具体股票、持仓或分析请求同时出现时，才执行 Skill；单独讨论关键词或文档时不生成股票建议。

> **重要：当前已完成 Phase 1–3 的基础版本。** State、Profit Ledger、Profit Reserve 和人工调整已实现；行情、完整费用、阶梯和回测仍未完成。项目只输出建议，永久不提供经纪商连接、直接卖出、直接买入或自动下单。所有结果在实现完成并经过测试前都不应视为投资建议。

## 项目是什么

- 默认平台：Moomoo Singapore
- 默认市场：Hong Kong Stock Exchange
- 默认货币：HKD
- 目标：生成 Market Analysis、Trading Recommendation、Buy/Sell Recommendation Ladder、费用估算、净收益模拟和风险警告
- 原则：Core Position 优先保护；净收益优先于毛收益；重大支撑跌破后停止机械补仓

本项目是建议辅助工具，不是交易执行机器人。最终买入、卖出、订单确认和风险承担均由投资人负责。

## 目录结构

```text
hk-swing-position-manager/
├── SKILL.md                         # Skill 运行规范与不可变策略约束
├── README.md                        # 用户文档
├── pyproject.toml                   # Python 项目与测试配置
├── .gitignore                       # Python 缓存和本地文件忽略规则
├── config/
│   └── default.yaml                 # 默认输入、风险、滑点和费用配置
├── references/                      # 策略定义与领域规则，不放程序实现
│   ├── strategy.md
│   ├── market-analysis.md
│   ├── position-management.md
│   ├── transaction-cost.md
│   ├── risk-control.md
│   └── calculation.md
├── schemas/
│   ├── input.schema.yaml            # 输入契约
│   ├── output.schema.yaml           # 输出契约
│   ├── state.schema.yaml            # 持久化 State 契约
│   └── profit-ledger.schema.yaml    # Profit Ledger 契约
├── examples/
│   ├── tencent-0700.yaml            # Tencent 0700.HK 输入示例
│   └── tencent-state-v2.yaml        # V2 State 示例
├── src/                             # Python 实现
│   ├── market_data.py
│   ├── trend.py
│   ├── support_resistance.py
│   ├── position.py
│   ├── ladder.py
│   ├── transaction_cost.py
│   ├── risk.py
│   ├── report.py
│   ├── state.py                     # State 持久化与审计
│   └── profit_ledger.py             # 净利润、Reserve 与再投资
└── tests/                           # 自动化测试
    ├── test_position.py
    ├── test_ladder.py
    ├── test_cost.py
    ├── test_profit_ledger.py
    ├── test_state.py
    └── test_risk.py
```

## 安装

当前 Phase 1 不需要第三方依赖。准备使用 Python 3.11 或更高版本：

```bash
cd hk-swing-position-manager
python --version
python -m venv .venv
```

激活虚拟环境：

- macOS/Linux：`source .venv/bin/activate`
- Windows PowerShell：`.venv\\Scripts\\Activate.ps1`

等计算模块进入实现阶段后，再按更新后的 `pyproject.toml` 安装依赖：

```bash
python -m pip install -e ".[dev]"
```

## 建议而非执行

Sell Recommendation Ladder 和 Buy Recommendation Ladder 只表示价格区间与数量建议，不代表订单，也不代表已经成交。项目不包含券商 API、直接卖出、直接买入或自动下单接口；投资人需要自行判断、手动下单和记录实际成交结果。Profit Ledger 的实际成交调整只接受投资人提供的成交数据，不会替投资人执行交易。

### 手动交易的区间规则

本项目不再把某个单一价格当作必须执行的触发价。建议使用区间：

```text
SELL Zone: HK$490–498，建议售出 10 股
BUY Zone:  HK$450–460，建议买入 10 股
```

区间含义是：

- 价格进入区间后，投资人自行决定是否手动成交；
- 区间上下界用于估算交易金额、费用和预期结果范围；
- 不假设一定以区间中点成交，也不假设一定成交；
- 价格跳过区间或未成交时，不更新持仓 State；
- 实际成交价偏离建议区间时，记录偏差和风险提示，但仍以投资人提供的实际价格、股数、费用和时间更新 State、Cash Ledger 与 Profit Ledger。

因此报告应优先展示 `price_range` 和 `execution_mode: manual`，而不是单一 `price`。

## 结论优先的报告格式

分析完成后，报告先给出 3–6 行结论，再展示市场分析和原因：

结论只能选择一个动作，购入和售出不能同时出现：

```text
Action: BUY
手动买入区间：HK$450–460
建议购入：8 股，预计交易金额 HK$3,600–3,680
预计手续费：HK$18–20
本次交易后预期净收益/亏损：按实际成交价重新计算
```

或者：

```text
Action: SELL
手动售出区间：HK$490–498
建议售出：8 股，预计交易金额 HK$3,920–3,984
预计手续费：HK$18–20
本次交易后预期收益/亏损：按实际成交价重新计算
```

如果没有明确交易机会：

```text
Action: HOLD / WAIT
不建议购入或售出
本次交易后预期收益/亏损：不适用或无法计算
```

如果缺少可靠价格、手续费或持仓成本，必须显示“无法计算”，不能填入猜测值。BUY、SELL、HOLD、WAIT 只能选择一个；所有 BUY/SELL 都是建议，投资人自行决定，系统不会提交订单。

## 当前如何运行

当前已提供 State 和 Profit Ledger 的 Python API，但尚无实时分析 CLI。可以先运行测试：

```bash
python3 -m unittest discover -s tests -v
```

也可以先阅读：

1. `SKILL.md`：运行边界与输出顺序。
2. `references/`：策略、计算和风险定义。
3. `schemas/input.schema.yaml`：输入格式。
4. `examples/tencent-0700.yaml`：完整输入示例。
5. `schemas/output.schema.yaml`：未来输出格式。

后续实现 CLI 后，将在此处补充类似以下命令（目前不可执行）：

```bash
python -m hk_swing_position_manager analyze --input examples/tencent-0700.yaml
python -m hk_swing_position_manager backtest --input examples/tencent-0700.yaml --data data/0700.HK.csv
```

## 持股成本、市值与未实现盈亏

`PositionState` 现在可以保存并更新：

```text
average_cost
total_cost
current_price
market_value = current_price × total_shares
unrealized_profit_loss = market_value - total_cost
```

如果缺少平均成本或当前价格，市值和未实现盈亏会显示为“无法计算”，不会使用虚构数据。用户后续可以通过 Skill 更新本地 State，例如：

```python
state.update_holding(
    average_cost=450,
    current_price=478.80,
    valuation_as_of="2026-08-07T16:08:00+08:00",
    valuation_source="Yahoo Finance",
    valuation_status="verified",
    reason="Updated from investor-provided holding statement",
)
state.save("state/0700.HK.json")
```

`state/*.json` 已加入 `.gitignore`，持仓成本、市值和收益状态只保存在本地，不会上传到仓库。

## Investor-reported Sale / Buy 与 Cash Ledger

项目不执行订单，但允许投资人把已经完成的交易写入本地 State：

```python
from src.profit_ledger import ProfitLedger

# 售出 10 股后，自动减少 Swing/Total Shares，记录现金变化和已实现盈亏。
ProfitLedger.record_sale(
    state,
    transaction_id="sale-001",
    shares=10,
    price=478.80,
    transaction_cost=25.75,
)

# 投资人之后买回 8 股。
ProfitLedger.record_repurchase(
    state,
    transaction_id="repurchase-001",
    shares=8,
    price=460,
    transaction_cost=25.00,
)

state.save("state/0700.HK.json")
```

售出记录会更新 `total_shares`、`current_swing_shares`、剩余成本基础、`cash_balance`、`realized_profit_loss` 和 `cash_ledger`。如果没有已知成本基础，单笔已实现盈亏会显示为无法计算，但售出股数和现金变化仍会记录。

### 盈利后买回更多股票

可以在实际成交前规划“售出后低价买回更多股数”，但规划不会执行订单：

```python
plan = ProfitLedger.plan_profit_repurchase(
    state,
    sold_shares=10,
    sell_price=500,
    buy_price=400,
    sale_transaction_cost=25,
    estimated_buy_cost_per_share=5,
    max_swing_shares=50,
)
```

规划结果会分别给出：

```text
recommended_repurchase_shares: 12
additional_shares: 2
profit_funded_extra_shares: 2
estimated_net_profit: HK$925
```

只有投资人实际买回后，才使用 `record_repurchase()` 写入 State。额外股数还必须受现金、最大 Swing Position、费用和风险限制约束；没有可验证现金余额时不会猜测可买股数。

## V2 State 与 Profit Ledger 使用方式

State 以 JSON 保存，金额使用字符串保存以避免浮点精度损失。核心 API 位于 `src/state.py` 和 `src/profit_ledger.py`：

```python
from src.profit_ledger import ProfitLedger
from src.state import PositionState

state = PositionState("0700.HK", 345, 300, 45, minimum_core_shares=300)
ProfitLedger.record_trade(
    state,
    transaction_id="trade-001",
    sell_shares=10,
    sell_price=500,
    buy_shares=10,
    buy_price=460,
    transaction_cost=80,
    slippage_cost=10,
)

# Reserve 达标不等于必须买入；必须明确提供 Buy Zone 和趋势许可。
ProfitLedger.reinvest_profit(
    state,
    buy_price=300,
    estimated_cost_per_share=5,
    in_buy_zone=True,
    trend_allows_buy=True,
    support_breakdown=False,
    max_shares=1,
)
state.save("state/0700.HK.json")
```

用户提供实际成交价、费用或净利润时使用 `ProfitLedger.adjust_transaction`；直接修改 Reserve 使用 `state.apply_reserve_adjustment`；更新持仓成本、市值或股数使用 `state.update_holding`。这些操作都会保留 Audit Trail，不会删除历史交易。

## 如何输入股票与持仓

输入文件使用 YAML。最小输入应提供股票代码、市场、货币和持仓拆分：

```yaml
asset:
  ticker: "0700.HK"
  market: "HK"
  currency: "HKD"
position:
  total_shares: 345
  core_shares: 300
  swing_shares: 45
```

可选参数包括分析天数、卖出/买入模式、可用现金、最低 Core 数量、最大回撤、交易费用和滑点。缺失参数将来会使用 `config/default.yaml` 中的默认值，并在报告中列出。

## 如何修改策略参数

请只修改输入文件或默认配置，不要直接修改 `references/` 来改变单次交易。常用参数：

- `analysis_period_days`：默认 180 天。
- `sell_mode`：默认 `adaptive`。
- `buy_mode`：默认 `progressive`。
- `minimum_core_shares`：长期底仓下限。
- `max_capital_drawdown`：最大资金回撤比例。
- `max_single_transaction_ratio`：单笔建议占 Swing Position 的上限；它不会触发任何订单。
- `minimum_net_profit` 与 `minimum_profit_to_cost_ratio`：费用告警阈值。
- `execution_mode`：固定为 `manual`；建议使用价格区间，成交后再根据实际成交数据更新账本。

策略思想不能在未确认的情况下自行改变。

## 费用与 Moomoo 费率

默认配置使用 Moomoo Singapore 与 HKEX 的费用模型占位。真实费率必须从最新官方 Moomoo Singapore 费率页面或用户提供的费率更新；不能把估算值称为 exact fee。费用至少要区分 commission、platform fee、stamp duty、trading fee、transaction levy、settlement fee、GST 和其他适用收费。

如果没有可验证的费率，输出必须标记 `Estimated Transaction Cost`，并降低结果置信度。

## 如何添加新的股票

复制 `examples/tencent-0700.yaml`，修改 `asset.ticker` 和持仓数据即可。不要复制或手工修改市场价格；未来行情模块必须从可靠来源取得并记录来源和时间戳。

## 回测

回测接口计划接收：

- `historical_data`
- `initial_position`
- `core_shares`
- `swing_shares`
- `strategy_parameters`

计划输出总交易次数、盈亏交易数、净收益、交易成本、最大回撤、期末股数、期末现金、策略收益、Buy & Hold 收益和股数增减。回测必须与 Buy & Hold 对比，且不能为了符合预期而修改历史数据。

当前回测尚未实现。

## 开发阶段

1. **Phase 1：** 项目结构、文档、Schema、示例和占位文件（已完成）。
2. **Phase 2：** Position State、Profit Generated Shares、Profit Reserve（已完成基础版本）。
3. **Phase 3：** Profit Ledger、Profit Reinvestment、Manual Adjustment、Audit Trail（已完成基础版本）。
4. **Phase 4：** Transaction cost、Moomoo Fee Model、Slippage、Cost Alert。
5. **Phase 5：** Market analysis、Trend、Support、Resistance。
6. **Phase 6：** Sell Recommendation Ladder、Buy Recommendation Ladder、Adaptive Sell、Progressive Buy。
7. **Phase 7：** Risk control、Drawdown、Position Limits、Breakdown Protection。
8. **Phase 8：** Backtest。
9. **Phase 9：** 不提供 Moomoo Integration；项目永久保持建议模式。

每个阶段都必须运行测试、检查结果、更新 README，并明确报告尚未实现的功能。

## V2 已实现功能

- `PositionState`：Core/Swing 状态、Profit Reserve、累计净利润和 State JSON 持久化。
- `ProfitLedger`：完成交易记录、Gross/Net Profit、Reserve 累积和实际成交人工调整。
- Profit Reinvestment：仅在 Buy Zone、趋势允许、无 Support Breakdown 且通过风险限制时，使用 Reserve 购买整数股。
- Audit Trail：人工修改 Profit Reserve 或实际交易数据时记录修改前后值、时间、原因和来源。
- 原始 `swing_shares` 输入别名仍兼容；V2 推荐 `initial_swing_shares`。

## P0 已实现功能

- Investor-reported sale-only、buy-only 和 repurchase 记录。
- 售出后更新 Swing/Total Shares、剩余成本基础和 Cash Ledger。
- 已知成本基础时计算 realized profit/loss。
- 已知现金余额时阻止超过现金余额的买入记录。
- 记录每笔投资人提供的交易 Audit Trail；不执行订单。

## 当前未实现功能

- 行情数据获取、数据校验与数据源适配
- 趋势、动量、成交量和市场状态判定
- 程序化支撑/阻力区域识别
- 完整 Core/Swing 交易后的区间买卖阶梯、盈利增持分配和资金限制
- FIFO/加权平均成本的完整可配置模型和复杂交易配对
- Sell Recommendation Ladder、Buy Recommendation Ladder 和完整风险参数计算
- Moomoo Singapore 最新费用加载与费用计算
- 滑点、风险控制、情景分析与结构化报告
- 回测、Buy & Hold 对比和 CLI
- 任何经纪商连接、直接卖出、直接买入或自动下单
