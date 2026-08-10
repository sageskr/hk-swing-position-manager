# Risk Control

## Hard limits

- Core Position 不得低于 `minimum_core_shares`。
- Swing 仓位不得超过 `max_swing_position_ratio` 规定的组合/目标比例。
- 买入总额不得超过可用现金与允许的卖出所得。
- 单笔交易不得超过 `max_single_transaction_ratio`。
- 每个手动建议使用价格区间；区间内实际成交仍由投资人决定，不能把区间边界或中点视为强制执行价。
- Progressive Buy 必须满足价格越低股数不减少；无法满足资金限制时截断或取消后续层级。

## Trend filter

当市场状态为 `bearish`、主要 Support 被有效跌破、或数据证据冲突时，应暂停或缩小买入。不能仅因价格下跌而继续加仓。有效破位的判定方式必须在实现阶段记录（例如收盘确认、成交量确认和回测参数），不可隐式处理。

## Drawdown

`max_capital_drawdown` 是硬性保护参数。计划中的最坏情景损失超过该值时，必须减少买入、暂停计划或输出 WAIT；不得用增加资金绕过限制。

## Scenarios

每个情景必须包含：

- `trigger`
- `expected_market_behavior`
- `recommended_action`
- `risk`

### Bull

突破主要 Resistance 且有结构/成交量确认：减少或延迟卖出，保留部分 Swing，重新计算阻力。

### Base

在 Support 与 Resistance 之间震荡：按成本检验后的阶梯计划分批执行，保留现金缓冲。

### Bear

跌破主要 Support 且得到确认：停止机械补仓，保护 Core 和现金，等待重新站回关键区域或重新分析。

## Risk wording

报告必须区分事实、假设和建议；不得保证收益。重大数据缺失、流动性不足、公司事件、停牌、跳空或市场制度变化都应成为风险警告候选项。