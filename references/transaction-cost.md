# Transaction Cost

## Fee source policy

默认经纪商为 Moomoo Singapore、市场为 HKEX、货币为 HKD。费率不能永久硬编码：实现阶段应优先加载最新官方 Moomoo Singapore 费率，并记录来源、有效时间和抓取时间。

如果无法取得官方费率：

1. 使用用户提供的费率；或
2. 使用配置中的估算费率，并把状态标记为 `estimated`。

估算费用必须显示为 `Estimated Transaction Cost`，不能标记为 exact。

## Components

按适用性计算并分别展示：

- commission
- platform fee
- stamp duty
- trading fee
- transaction levy
- settlement fee
- applicable GST
- other applicable charges
- slippage cost

法规或平台费率发生变化时，应更新配置和来源记录，而不是在计算代码中散落常量。

## Round-level metrics

每一轮交易至少输出：

```text
Gross Profit
Transaction Cost
Net Profit = Gross Profit - Transaction Cost
Cost Ratio = Transaction Cost / Gross Profit
Minimum Effective Spread
```

当 `Gross Profit <= 0` 时，Cost Ratio 不应伪造为 0；应标记为 `undefined` 或 `not_meaningful` 并建议不交易。

## Alerts

默认阈值：

- `< 30%`：GREEN
- `30%–50%`：YELLOW
- `>= 50%`：RED

同时在以下情况告警：

- `Net Profit < minimum_net_profit`
- `Gross Profit / Transaction Cost < minimum_profit_to_cost_ratio`
- 费率或成交价格只是估算
- 滑点可能使净收益转负

交易成本模型仅用于决策模拟，不代表实际结算账单。