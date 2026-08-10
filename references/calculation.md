# Calculation Contract

本文件描述计算边界，不在 Phase 1 实现交易代码。

## Ladder constraints

Sell Recommendation Ladder（仅为手动建议，不是订单）：

- 2–4 个价格区间层级，每层记录 `lower` 和 `upper`。
- 不把区间中点或边界当作必须成交的精确价格。
- 所有数量来自 Swing Position。
- 阻力越强或越接近目标区域，数量由市场状态与风险配置共同决定。
- Bullish Breakout 时可减少、延迟或重新计算卖出层级。

Progressive Buy Recommendation Ladder（仅为手动建议，不是订单）：

- 2–4 个价格区间层级，每层记录 `lower` 和 `upper`。
- 对按区间上界从高到低排序的层级，股数必须保持不减少。
- 每层要记录价格区间、股数、预计金额范围、费用范围、资金来源和触发条件。
- 受现金、最大回撤、趋势过滤器、Swing 上限和破位保护约束。
- 价格进入区间后由投资人自行判断是否手动成交；只有实际成交记录才更新 State 和 Ledger。
- 售出价高于买回价时，先计算可负担的买回数量，再计算额外股数：

```text
net_sale_proceeds = sold_shares × sell_price - sale_costs
unit_repurchase_cost = buy_price + estimated_buy_cost_per_share
recommended_repurchase_shares = floor((available_cash + net_sale_proceeds) / unit_repurchase_cost)
additional_shares = max(0, recommended_repurchase_shares - sold_shares)
```

- `additional_shares` 必须同时受最大 Swing Position 限制；只有实际买回后才更新 `current_swing_shares`。
- `profit_funded_extra_shares` 只表示由费用后价差利润可覆盖的额外股数，不表示已经成交。

## Position accounting

每笔由投资人提供的实际成交记录至少包括：售出、买入和买回可以独立记录，不要求数量相等。

```text
id, event_type, side, price, shares, gross_value, fees, slippage, net_cash_change, source
```

计划汇总至少包括：

```text
initial_swing_shares
sold_shares
repurchased_shares
ending_swing_shares
additional_shares_gained_or_lost
ending_cash
```

## Profit accounting

投资人提供的售出与之后买回可以组成一个可追踪的 round trip，也可以只记录单独售出或单独买入。不得把建议或未成交计划当作已实现收益；项目不会替投资人执行卖出或买入。

```text
Gross Profit = sell proceeds - repurchase cost
Net Profit = Gross Profit - all applicable transaction costs - slippage
```

实际持仓成本、税务处理和费用归属可能需要用户选择模型，报告必须声明所用假设。手动区间建议只能给出交易金额、费用和净结果的范围；成交后必须以实际成交价重新计算，不能按区间中点结算。

## Backtest contract

回测接口至少接收：

- `historical_data`
- `initial_position`
- `core_shares`
- `swing_shares`
- `strategy_parameters`

至少输出：

- total trades
- winning trades
- losing trades
- net profit
- transaction costs
- maximum drawdown
- ending shares
- ending cash
- strategy return
- buy-and-hold return
- number of shares gained/lost

回测必须避免未来函数，保留数据截止时间，并使用同一费用/滑点模型与 Buy & Hold 公平比较。