# Market Analysis

## Analysis window

默认分析最近 180 个日历/交易数据周期，实际窗口由可用数据和 `analysis_period_days` 决定。报告必须说明实际使用的起止日期、数据频率、数据来源和缺失情况。

## Required inputs

至少考虑：

- OHLC（开、高、低、收）
- Volume
- recent highs/lows
- swing highs/lows
- moving averages
- price structure
- momentum
- volume behavior

不能只用单个技术指标决定趋势。指标缺失时要降低置信度并说明原因。

## Regime classification

输出至少一个 `bullish`、`sideways`、`bearish` 或 `transitional` 状态，并说明证据：

- **bullish**：高点和低点抬高，价格结构偏强，均线/动量/成交量至少有多项支持。
- **bearish**：高点和低点下移，价格结构偏弱，反弹承压且成交量或动量不支持。
- **sideways**：价格在可识别区间内反复运行，突破缺乏持续确认。
- **transitional**：趋势证据冲突或正处于结构切换，不能可靠归入前三者。

实现阶段应保留组成分数或证据列表，而不是只返回一个不可解释的标签。

## Data integrity

每个数据集应包含：

```yaml
source: provider-or-user
as_of: "YYYY-MM-DDTHH:MM:SSZ"
status: verified | user_provided | estimated | unavailable
frequency: daily
```

数据无法验证、过期或明显不完整时，不得编造价格层级；可以只输出观察框架和 WAIT 建议。