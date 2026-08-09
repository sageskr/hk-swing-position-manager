# Position Management

## Required invariant

```text
core_shares >= minimum_core_shares
core_shares + swing_shares <= total_shares
```

用户明确提供的 `total_shares`、`core_shares` 和 `swing_shares` 不一致时必须报错或要求澄清，不能静默修正。若 `core_shares + swing_shares < total_shares`，差额必须标记为未分配仓位，而不是自动归入 Swing。

## Planning sequence

1. 校验非负整数股数和最小交易单位。
2. 确认 Core 下限与初始 Swing 数量。
3. 计算每个 Sell Ladder 层级卖出后的剩余 Swing 股数。
4. 将可用卖出资金、已有现金和滑点/费用纳入 Buy Ladder 预算。
5. 计算每个买回层级后的 Swing 股数、总股数和剩余现金。
6. 输出 `sold_shares`、`repurchased_shares`、`ending_swing_shares` 和 `additional_shares_gained_or_lost`。

## Core protection

所有卖出数量只能来自 Swing Position。若某一层交易会使总持仓低于 Core 下限，必须阻止该层交易并报告原因。即使用户有亏损，也不能默认出售 Core 来筹资。

## Share growth

股数增长只能来自可验证的低价买回结果：

```text
additional_shares_gained_or_lost = ending_swing_shares - initial_swing_shares
```

必须同时报告现金变化、总费用和未成交订单，不能只展示股数增加。