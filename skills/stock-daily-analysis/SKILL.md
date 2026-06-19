---
name: stock-daily-analysis
description: A股技术面分析系统。获取A股单只个股日线行情，计算技术指标（均线、MACD、RSI、乖离率、量能），输出技术面评分和AI结论。仅处理"A股单只个股的技术面分析"，不处理市场主线、板块分析、多只股票对比、其他市场。触发词：股票分析、分析股票、技术面分析、个股分析、XX股票怎么样。
---

# 🎯 适用边界（路由判断必读）

**本 Skill 仅处理**：用户明确要求对 **A股单只个股** 做 **技术面分析**（均线/MACD/RSI/量能等技术指标解读）。

**以下场景必须由其他 Agent/Skill 处理，本 Skill 不得接管**：

| 用户意图 | 正确路由 |
|---|---|
| A股市场整体主线 / 板块强弱 / 情绪周期 | → cxdata-mainline-analysis-agent |
| 分析单一板块（如"电子板块怎么样"）| → 板块分析 agent |
| 个股基本面 / 财报 / 估值 / 公司质地 | → 公司质地打分 agent |
| 多只股票对比 / 选股 | → 选股 agent |
| 港股 / 美股 / 期货 / 加密货币 | → 对应市场 agent |
| 仅查最新价 / K线（不做技术分析）| → Wind / 通用行情 agent |

**当用户指令模糊时**（如"看看股票"、"分析下"、"今天行情怎么样"、"市场怎么样"），**禁止自行选其他 agent 执行**，必须先反问用户：

> 您是想对某只 **A 股个股** 做技术面分析吗？如果是，请告诉我股票代码或名称（如"分析 600519"或"贵州茅台技术面怎么样"），我将立即调用股票分析 agent。如果是市场整体主线、板块分析、其他需求，请明确告知。

**关键提示**：指令必须明确包含 **股票代码（6位数字）** 或 **具体股票名称**，且意图是"分析这只股票"——这是路由到本 Skill 的必要条件。

---

# 执行标准程序 (Recommended Workflow)

当用户要求分析股票时，按以下步骤执行：

## Step 1: 调用分析脚本获取技术指标

使用以下命令获取股票的技术面分析数据：

```bash
cd {Agent目录}/skills/stock-daily-analysis && python3 -c "from scripts.analyzer import analyze_stock; import json; r=analyze_stock('{股票代码}'); print(json.dumps(r, ensure_ascii=False, indent=2, default=str))"
```

> `{Agent目录}` 为本 Agent 解压后的根目录路径。

将 `{股票代码}` 替换为6位数字代码，例如 `600519`、`301292`。

脚本会自动完成：获取行情数据 → 计算技术指标 → 输出 JSON 结果。

## Step 2: 你（Agent LLM）必须亲自解读技术指标

**重要：这一步是你（Agent LLM）必须执行的分析工作，不得跳过。**

### ⚠️ 内容来源严格分工（决定两次报告是否一致）

Step 1 返回的 JSON 中，`ai_analysis` 字段已重构，分为「Python 固定的结构化判断」和「LLM 必须独立完成的解读」。**严格按以下分工执行：**

#### 【Python 固定，LLM 必须原样引用，不得修改/编造/遗漏】

| 字段 | 内容 | LLM 怎么用 |
|---|---|---|
| `technical_indicators.*` | 所有原始数值（MA/RSI/MACD/价位等）| 直接引用，不得编造 |
| `ai_analysis.sentiment_score` | 综合评分 | 直接引用 |
| `ai_analysis.signal_labels` | 信号标签列表（如"多头排列"、"RSI强势"）| 作为解读依据，可改写为通顺文字 |
| `ai_analysis.key_levels` | 4 个关键价位（强支撑/短支撑/第一压力/强压力）| **报告支撑压力表必须用这 4 个价位** |
| `ai_analysis.reasonable_range` | 合理价值区间 (lower, upper) | **AI 结论的合理区间必须用这个**，不得自创 |
| `ai_analysis.risk_points` | 风险点列表（Python 按阈值触发）| **报告"风险提示"段必须逐条列出全部，不得遗漏，不得添加未触发的** |
| `ai_analysis.observation_points` | 关键观察点（Python 给）| 报告"关键观察点"必须涵盖全部 |

#### 【LLM 必须独立完成的部分】

1. **每个指标的"含义解读"**：用通顺文字说明数据含义（如"多头排列意味着趋势结构健康，多头力量主导"）
2. **数据串联**：把 Python 给的数据/价位/区间写成连贯段落，措辞可自由
3. **综合 AI 结论**：基于 signal_labels + risk_points 综合判断"看多/谨慎看多/观望/看空"，给出一段总结
4. **看多理由改写**：signal_labels 是标签，LLM 必须把每条标签扩展为完整句子（如把"多头排列"扩成"MA5>MA10>MA20，多头排列，趋势结构健康"）

#### 【LLM 严禁做的事】

- ❌ 编造 `technical_indicators` 里没有的数值
- ❌ 自创合理区间（必须用 `reasonable_range`）
- ❌ 自创关键价位（必须用 `key_levels`）
- ❌ 添加 `risk_points` 里没有的风险点（如 Python 没触发"量价背离"，LLM 不得自己说）
- ❌ 漏掉 `risk_points` 里的任何一条
- ❌ 直接复用已删除的字段（`analysis_summary` / `buy_reason` / `risk_warning` 不再返回）

### 你需要完成的分析：

1. **AI结论**：看多 / 谨慎看多 / 观望 / 看空（基于 signal_labels 和 risk_points 综合判断，**不是直接抄 operation_advice**）
2. **合理价值区间**：直接引用 `reasonable_range`，必要时解释为什么是这个区间
3. **风险警示区间**：基于 `key_levels.strong_resistance`（强压力位上方）和 `key_levels.strong_support`（强支撑位下方）
4. **关键观察点**：涵盖 `observation_points` 全部条目，措辞可调
5. **每个技术指标下写 AI 解读**：每条含「数据值 + 含义 + 推论」三段（不得只列数据）
6. **看多理由**：把 signal_labels 每条扩展为完整句子，结合近 20 日走势
7. **风险提示**：把 risk_points 全部列出（一条不漏），可补充上下文说明

### 你需要重点关注的字段：

- `signal_score`：综合评分（0-100），>=60 偏积极，<45 偏谨慎
- `trend_status`：趋势判断（强势多头/多头排列/弱势多头/盘整/弱势空头/空头排列/强势空头）
- `bias_ma5`：乖离率，绝对值 >5% 提示短期偏离过大
- `macd_status`：金叉/死叉/多头/空头
- `rsi_status`：超买(>70)/强势看多/中性/弱势/超卖(<30)
- `volume_status`：放量上涨/缩量回调/放量下跌 等
- `signal_reasons`：看多理由列表（参考但不照搬）
- `risk_factors`：风险因素列表（参考但不照搬）
- `price_phase`：价格阶段（蓄势/发散启动/趋势上行/高位震荡/下跌趋势/盘整）
- `consecutive_up_days`：连续上涨天数
- `recent_5d_gain_pct`：近5日涨幅%
- `ma_convergence`：均线收敛度（<0.02为收敛，>=0.02为发散）
- `rsi_overbuy_type`：RSI超买类型（暴涨型/连续小阳型/温和超买/非超买）
- `rsi_risk_level`：RSI风险等级（高风险/中风险/低风险/无）
- `breakout_signal`：突破信号（突破前高/接近前高/远离前高）
- `near_high_pct`：距前高百分比（负值=在前高下方）
- `prev_high`：近20日最高价
- `prev_high_date`：前高日期
- `ma_support_count`：近20日均线支撑次数
- `ma_support_success_rate`：支撑后次日上涨概率

### AI 解读规则（必须基于量化标签，不要主观猜测）

#### 均线解读（基于 price_phase）
- `price_phase=蓄势` → "均线收敛（收敛度{ma_convergence}），三线趋近，蓄势等待方向选择。近{consecutive_up_days}日连涨，10日涨幅{recent_10d_gain_pct}%"
- `price_phase=发散启动` → "均线黏合后开始发散（从{prev_ma_convergence}扩至{ma_convergence}），趋势启动信号"
- `price_phase=趋势上行` → "均线多头排列且发散（收敛度{ma_convergence}），趋势上行中"
- `price_phase=高位震荡` → "股价在近期高位震荡（近5日高低波动>5%但收盘变化<2%），方向不明"
- `price_phase=下跌趋势` → "均线空头排列，下跌趋势中"
- `price_phase=盘整` → "均线缠绕，盘整整理中"

#### RSI 解读（基于 rsi_overbuy_type）
- `rsi_overbuy_type=暴涨型` → "RSI={rsi_12}超买，近5日涨幅{recent_5d_gain_pct}%，短期获利盘较大，回调风险高（{rsi_risk_level}）"
- `rsi_overbuy_type=连续小阳型` → "RSI={rsi_12}超买，但近{consecutive_up_days}日连续小阳推高，属于温和蓄势而非暴涨见顶（{rsi_risk_level}）"
- `rsi_overbuy_type=温和超买` → "RSI={rsi_12}超买，需关注量能配合（{rsi_risk_level}）"
- `rsi_overbuy_type=非超买` → 正常描述RSI值和状态

#### 突破解读（基于 breakout_signal）
- `breakout_signal=突破前高` → "已突破近20日高点{prev_high}（{prev_high_date}），上方空间打开"
- `breakout_signal=接近前高` → "距前高{prev_high}（{prev_high_date}）仅{abs(near_high_pct)}%，突破则打开空间"
- `breakout_signal=远离前高` → 不特别提及突破

#### 支撑解读（基于 ma_support_count）
- `ma_support_count >= 3 且 ma_support_success_rate >= 0.6` → "近20日均线支撑{ma_support_count}次，成功率{ma_support_success_rate}，支撑有效"
- `ma_support_count >= 1 且 ma_support_success_rate < 0.5` → "近20日均线支撑{ma_support_count}次但成功率仅{ma_support_success_rate}，支撑偏弱"
- `ma_support_count = 0` → 不特别提及支撑统计

## Step 3: 生成完整报告并保存

将 Step 1 的技术指标数据和 Step 2 你自己的分析整合为完整的 Markdown 报告。

报告格式：

```markdown
# {代码} {名称} 股票分析报告

> 生成时间: {日期} | 数据来源: 财新数据平台 | 分析工具: A股技术分析系统 + AI 分析

---

## 核心结论

| 项目 | 结果 |
|------|------|
| **AI结论** | {你在 Step 2 的综合结论} |
| **综合评分** | {signal_score}/100 |
| **趋势判断** | {trend_status}（{你的补充说明}） |
| **置信度** | {你判断的高/中/低} |

**一句话结论**: {你的一句话核心结论}

---

## 最新行情

{从 technical_indicators 中提取 current_price 等}

---

## 技术面分析

### 均线系统
{ma5/ma10/ma20 + 乖离率}
- **趋势状态**: {trend_status}（{ma_alignment}）
- **价格阶段**: {price_phase}（均线收敛度: {ma_convergence}）
- **AI 解读**: 根据上方"均线解读"模板，基于 price_phase 输出对应描述

### MACD 指标
{macd_status + macd_signal}
- **AI 解读**: 基于 macd_status 和 macd_signal 描述当前状态

### RSI 指标
{rsi_6/rsi_12/rsi_20 + rsi_status + rsi_overbuy_type + rsi_risk_level}
- **AI 解读**: 根据上方"RSI 解读"模板，基于 rsi_overbuy_type 输出对应描述

### 量能分析
{volume_status + volume_ratio_5d}
- **AI 解读**: 基于 volume_status 描述量价配合情况

### 突破与压力
| 指标 | 数值 |
|------|------|
| 近20日最高价 | {prev_high}（{prev_high_date}） |
| 距前高 | {near_high_pct}% |
| 突破信号 | {breakout_signal} |
- **AI 解读**: 根据上方"突破解读"模板，基于 breakout_signal 输出对应描述

---

## 支撑与压力位

| 类型 | 价位 | 依据 |
|------|------|------|
| 强支撑 | {价位} | {依据} |
| 短支撑 | {价位} | {依据} |
| 第一压力 | {价位} | {依据} |
| 强压力 | {价位} | {依据} |

**均线支撑统计**: 近20日支撑{ma_support_count}次，成功率{ma_support_success_rate}
- **AI 解读**: 根据上方"支撑解读"模板输出

---

## AI 结论

| 项目 | 内容 |
|------|------|
| **合理价值区间** | {AI 生成的合理价值区间} |
| **风险警示区间** | {AI 生成的风险警示区间} |
| **关键观察点** | {你认为需要关注的要点} |

### 看多理由
{你基于技术指标和行情走势的综合分析}

### 风险提示
{你基于技术指标和行情走势的风险分析}

---

## 近{N}日行情走势

{从 Step 1 返回数据中提取近 20 日行情表}

---

*免责声明: 本报告技术指标由 A股技术分析系统自动生成，AI 分析部分基于技术面数据，仅供学习研究参考，不构成任何投资建议。股市有风险，投资需谨慎。*
```

**报告保存位置**: `{项目根目录}/stock-analysis/{代码}_{名称}_分析报告_{日期}.md`

---

# 配置说明

## 数据源
本技能已内置 `stock-market-information` 数据源 skill，无需额外安装。

配置文件位于 `skills/stock-market-information/scripts/.env`，需填写：
- `CXDA_USER_KEY`：财新数据平台用户密钥
  - 前往 [财新数据平台](https://yun.ccxe.com.cn/data/Skills) 注册并申请（**平台目前处于推广期，可免费试用**）
- `BASE_URL`：API 基础地址（默认 `http://cxapi.ccxe.com.cn/cxda`）

## 可选参数
通过环境变量配置（或复制 `scripts/.env.example` 为 `scripts/.env` 自定义）：
```
DATA_DAYS=20
ANALYSIS_BIAS_THRESHOLD=5.0
ANALYSIS_VOLUME_SHRINK_RATIO=0.7
ANALYSIS_VOLUME_HEAVY_RATIO=1.5
```
不配置时使用默认值，不影响使用。

---

# 故障排除

- **数据源未配置**: 检查 `skills/stock-market-information/scripts/.env` 中是否配置了 `CXDA_USER_KEY` 和 `BASE_URL`。如无密钥，前往 [财新数据平台](https://yun.ccxe.com.cn/data/Skills) 申请（推广期可免费试用）
- **ModuleNotFoundError**: 需要安装依赖 → `pip install pandas numpy requests python-dotenv`
- **数据获取失败**: 检查 `skills/stock-market-information/scripts/.env` 配置，确认网络连接正常
- **只支持 A 股**: 港股/美股代码会返回"数据获取失败"

---

# 返回数据格式参考

```python
{
    'code': '600519',
    'name': '贵州茅台',
    'technical_indicators': {
        'trend_status': '强势多头',
        'ma5': 1500.0, 'ma10': 1480.0, 'ma20': 1450.0,
        'bias_ma5': 2.5,
        'macd_status': '金叉',
        'rsi_status': '强势看多',
        'buy_signal': '看多',
        'signal_score': 75,
        'signal_reasons': [...],
        'risk_factors': [...]
    },
    'ai_analysis': {
        'sentiment_score': 75,
        'operation_advice': '看多',
        'confidence_level': '高',
        'analysis_summary': '...',
        'buy_reason': '...',
        'risk_warning': '...'
    }
}
```
