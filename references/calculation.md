# Calculation Contract

本文件描述计算边界，不在 Phase 1 实现交易代码。

## Ladder constraints

Sell Ladder：

- 2–4 个价格层级。
- 所有数量来自 Swing Position。
- 阻力越强或越接近目标区域，数量由市场状态与风险配置共同决定。
- Bullish Breakout 时可减少、延迟或重新计算卖出层级。

Progressive Buy Ladder：

- 2–4 个价格层级。
- 对按价格从高到低排序的层级，股数必须保持不减少。
- 每层要记录目标价、股数、预计金额、费用、资金来源和触发条件。
- 受现金、最大回撤、趋势过滤器、Swing 上限和破位保护约束。

## Position accounting

每笔成交记录至少包括：

```text
side, price, shares, gross_value, fees, slippage, net_cash_change, source
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

卖出与之后买回组成一个可追踪的 round trip。不得把未成交计划当作已实现收益。

```text
Gross Profit = sell proceeds - repurchase cost
Net Profit = Gross Profit - all applicable transaction costs - slippage
```

实际持仓成本、税务处理和费用归属可能需要用户选择模型，报告必须声明所用假设。

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