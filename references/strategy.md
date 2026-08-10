# Strategy Definition

## Purpose

策略的目标不是预测顶部或底部，而是在用户已有港股持仓中划出受控的 Swing Position，并利用价格区域生成卖出与买回建议。长期 Core Position 不参与常规波段交易；项目不执行任何交易。

## Position roles

- **Core Position**：长期持有的底仓。除非用户明确授权，否则不能卖出。
- **Swing Position**：可以在 Resistance 附近获得分批卖出建议、在 Support 附近获得分批买回建议的仓位。
- **Available cash**：可用于买回的现金。卖出所得是否可以再投资由 `swing_capital_source` 和 `reinvest_profit` 决定。

## Decision principles

1. 先校验持仓不变量，再做交易计划。
2. 价格区间优于单一价格点，层级数量为 2–4 层；每层必须有 lower/upper 边界。
3. 越接近强 Resistance Zone，卖出倾向越强；越接近强 Support Zone，买入倾向越强。手动交易不要求在某一个精确价格成交。
4. 买入数量可以随价格降低而增加，但不得违反资金、回撤、仓位和趋势限制。
5. 震荡区间适合正常执行；趋势突破需要减少机械交易。
6. 重大支撑跌破是保护资本的触发器，不是自动加仓信号。
7. 每个动作都必须通过费用后收益检验；区间建议应计算结果上下界，不划算时输出 WAIT。
8. 价格进入建议区间只表示达到人工评估条件；实际成交、成交价和费用必须由投资人提供，未成交不得更新 State。

## Market regime behavior

- `bullish`：保留更多 Swing Position，卖出层级更保守；突破后重新评估阻力。
- `sideways`：可按计划执行分批卖出和 Progressive Buy。
- `bearish`：降低或暂停买入，优先保护 Core 和现金。
- `transitional`：缩小交易规模，等待结构确认，明确说明不确定性。

## Forbidden behavior

- 直接下单、直接卖出、直接买入或假装已经成交。
- 把价格区间的边界、中点或任意单一价格描述为必须执行价格。
- 将未经验证的市场价格、历史数据或费率当作事实。
- 因为价格更低就无限补仓。
- 用 Swing Position 弥补 Core Position 的亏损。
- 忽略滑点、费用、最小交易单位或资金限制。
- 为了让示例盈利而修改数据或参数。

策略本身若需变更，必须先记录 Problem、Why it matters、Possible solutions 和 Recommended option，并等待用户确认。