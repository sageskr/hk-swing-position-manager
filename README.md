# HK Swing Position Manager

港股持仓波段交易决策辅助 Skill。它帮助用户把已有持仓拆分为长期 Core Position 与可交易 Swing Position，在不减少长期底仓的前提下，模拟上涨分批卖出、下跌分批买回，并比较交易成本与净收益。

> **重要：当前是 Phase 1。** 本阶段只完成项目架构、策略文档、Schema 和示例，尚未连接行情、尚未进行计算，也绝不会自动下单。所有结果在实现完成并经过测试前都不应视为投资建议。

## 项目是什么

- 默认平台：Moomoo Singapore
- 默认市场：Hong Kong Stock Exchange
- 默认货币：HKD
- 目标：生成 Market Analysis、Trading Plan、Buy/Sell Ladder、费用估算、净收益模拟和风险警告
- 原则：Core Position 优先保护；净收益优先于毛收益；重大支撑跌破后停止机械补仓

本项目是决策辅助工具，不是自动交易机器人。最终交易决定、订单确认和风险承担由用户负责。

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
│   └── output.schema.yaml           # 输出契约
├── examples/
│   └── tencent-0700.yaml            # Tencent 0700.HK 输入示例
├── src/                             # 后续 Python 实现（当前为占位）
│   ├── market_data.py
│   ├── trend.py
│   ├── support_resistance.py
│   ├── position.py
│   ├── ladder.py
│   ├── transaction_cost.py
│   ├── risk.py
│   └── report.py
└── tests/                           # 后续自动化测试（当前为占位）
    ├── test_position.py
    ├── test_ladder.py
    ├── test_cost.py
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

## 当前如何运行

Phase 1 暂无可执行分析命令。可以先阅读：

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
- `max_single_transaction_ratio`：单笔交易占 Swing Position 的上限。
- `minimum_net_profit` 与 `minimum_profit_to_cost_ratio`：费用告警阈值。

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

1. **Phase 1：** 项目结构、文档、Schema、示例和占位文件（当前）。
2. **Phase 2：** Position 与 Ladder calculation。
3. **Phase 3：** Transaction cost。
4. **Phase 4：** Market analysis。
5. **Phase 5：** Risk control。
6. **Phase 6：** Backtest。
7. **Phase 7：** Moomoo integration（仍禁止自动下单，除非另行确认）。

每个阶段都必须运行测试、检查结果、更新 README，并明确报告尚未实现的功能。

## 当前未实现功能

- 行情数据获取、数据校验与数据源适配
- 趋势、动量、成交量和市场状态判定
- 程序化支撑/阻力区域识别
- Core/Swing 校验与仓位变化计算
- 买卖阶梯和资金限制
- Moomoo Singapore 最新费用加载与费用计算
- 滑点、风险控制、情景分析与结构化报告
- 回测、Buy & Hold 对比和 CLI
- 任何经纪商连接或自动下单
