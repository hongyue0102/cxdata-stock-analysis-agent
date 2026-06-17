# A股技术分析专家 Agent

面向 A 股市场的技术分析智能分身，用户只需说"分析 600519"即可获得完整的技术面分析报告。

## 功能

- 获取 A 股日线行情数据（通过财新数据平台）
- 计算技术指标：均线系统、MACD、RSI、乖离率、量能
- Agent LLM 亲自解读每个技术指标，给出 AI 结论
- 生成完整的 Markdown 分析报告

## 使用方式

### ✅ 规范指令（推荐使用，AI 稳定路由到本 Agent）

| 指令 | 说明 |
|---|---|
| `分析 600519` | 股票代码 + 分析关键词 |
| `分析 贵州茅台` | 股票名称 + 分析关键词 |
| `贵州茅台技术面怎么样` | 名称 + "技术面" |
| `帮我看看 300590` | "看看" + 代码 |
| `301292 技术面分析` | 代码 + "技术面分析" |
| `用股票分析agent跑下 600519` | 直接点名 agent |

**关键要素**：指令中必须包含 **股票代码（6位数字）** 或 **具体股票名称**，并配合"分析/技术面/怎么样/看看"等分析意图词。

Agent 会自动：鉴权 → 获取行情 → 计算技术指标 → AI 解读 → 生成报告。

### ❌ 容易误路由的指令（请避免使用）

以下指令**未指定具体股票**，会触发其他 agent 或导致 AI 反问，**不要这样调用本 agent**：

| ❌ 模糊指令 | ⚠️ AI 可能误调用的对象 |
|---|---|
| `看看股票` / `分析下股票` | 不知分析哪只，触发反问 |
| `今天行情怎么样` | 误调主线分析 agent / 通用行情 |
| `市场怎么样` | 误调主线分析 agent |
| `今天该不该买` | 无对应 agent，会乱答 |
| `分析下电子板块` | 误调板块分析 agent |
| `今日主线` | 误调主线分析 agent |
| `分析下港股 0700` | 误调通用行情（本 agent 仅 A 股）|

> 如果使用了上述模糊指令，AI 会主动反问澄清，但会多一次交互——建议直接用规范指令。

### 🔀 与其他 agent 的边界（避免重复调用）

| 用户需求 | 应调用 |
|---|---|
| **A 股单只个股的技术面分析（均线/MACD/RSI/量能）** | **本 agent**（股票技术分析） |
| A股市场整体主线 / 板块强弱对比 / 情绪周期 | cxdata-mainline-analysis-agent |
| 单一板块的深度分析（如只看电子）| 板块分析 agent |
| 个股基本面 / 财报 / 估值 / 公司质地打分 | 公司质地打分 agent |
| 多只股票对比 / 选股 / 排序 | 选股 agent |
| 港股 / 美股 / 期货 / 加密货币 | 对应市场 agent |
| 回测 / 策略 / 仓位管理 | 策略类 agent |

## 前置依赖

1. 安装 Python 依赖：`pip install pandas numpy requests`
2. 首次使用需完成鉴权（**新版 SMS 验证码登录机制**）：
   - 调用 `skills/stock-daily-analysis/scripts/auth.py status` 检查认证状态
   - 未认证时按 AGENT.md 引导用户完成协议确认 + 手机号验证码登录
   - 认证信息持久化在 `~/.cxda-cache/.shared/cxda_auth.json`，**跨所有 cxdata Agent 共享**，无需重复认证
   - 数据源 Skill 已内置在 Agent 中，无需额外下载

## 目录结构

```
cxdata-stock-analysis-agent/
├── AGENT.md                          # Agent 整体人设与执行逻辑
├── SOUL.md                           # 身份、性格、能力边界
├── rules.md                          # 硬性规则
├── config.json                       # 元数据配置
├── skills/
│   ├── cxdata-stock-market-information/  # 内置数据源（空壳：SKILL.md + references）
│   └── stock-daily-analysis/             # 技术分析 Skill
│       ├── SKILL.md                      # Skill 定义（含 frontmatter）
│       ├── requirements.txt
│       └── scripts/
│           ├── analyzer.py               # 主入口
│           ├── data_fetcher.py           # 数据获取（subprocess 调 query.py）
│           ├── trend_analyzer.py         # 技术分析引擎
│           ├── ai_analyzer.py            # 结果整理
│           ├── notifier.py               # 报告输出
│           ├── auth.py / common.py /     # cxdata 官方鉴权四件套（拷自新版 skill）
│           ├── cxda_cache_cli.py / query.py
│           └── prompts/
│               └── analysis_prompt.md
└── README.md
```

## 变更历史

### 2026-06-17 新增 Agent 路由边界与用户使用指引

- **问题**：新设备测试时，AI 在用户指令模糊（如"看看股票"、"今天行情怎么样"）或指令不含具体股票代码/名称时，会误调用主线分析 / Wind / 板块分析等其他 agent，导致股票分析 agent 失效或答非所问
- **方案**（三层防御，覆盖 Claude Code 内调度与 OpenClaw 等中转平台调度两种场景）：
  - **AGENT.md** 顶部新增 Step 0「适用边界判定」：明确 ✅ 命中条件（含 6 位股票代码或具体股票名称 + 分析意图词）/ ❌ 让出场景（市场主线、单一板块、公司基本面、多股对比、其他市场等路由表）/ ⚠️ 模糊指令强制反问（禁止自行路由到其他 agent）
  - **SKILL.md** description 收紧为"仅处理 A股单只个股的技术面分析"，并在顶部加「适用边界（路由判断必读）」表
  - **README.md** 使用方式段重写：✅ 规范指令表（关键词：股票代码 + 分析/技术面/怎么样/看看）+ ❌ 误路由指令表 + 🔀 与其他 agent 边界表

### 2026-06-17 鉴权升级为 cxdata 官方 SMS+协议确认机制（commit 1c38442）

- **data_fetcher.py** 改为 subprocess 调用官方 `query.py`（内置 token 管理、gzip 解码、积分计数、50 次硬限制），不再自行实现 HTTP 鉴权
- 新增 `auth.py / common.py / cxda_cache_cli.py / query.py`（拷自新版 cxdata-stock-market-information skill）
- **AGENT.md** 加 Step 1.5 鉴权前置（terms-check + status + SMS 引导）+ Step 5 session summary
- 数据源 skill 目录改名为 `cxdata-stock-market-information`（SKILL.md/references 同步新版，scripts 空壳避免恢复通用 `api_query.py`）
- 删除老版 `.env.example`（鉴权改为 `~/.cxda-cache/` 共享缓存）

### 2026-06-12 移除通用 api_query.py（commit 9ed84ff）

- **问题**：通过 OpenClaw 执行 agent 时，LLM 看到 `stock-market-information/scripts/api_query.py` 通用脚本，自主调用了 9 个基本面接口，生成超范围的大报告
- **方案**：`data_fetcher.py` 内嵌 token + HTTP 请求，硬编码只调 `getStkDayQuoByCond-G`，删除通用 `api_query.py`

### 2026-06-11 约束 LLM 不得篡改技术指标（commit 8bc2df8）

- **问题**：同一股票两次运行生成的报告数值/结构不同，LLM 自行编造或篡改技术指标
- **方案**：AGENT.md 新增 Step 2 命令B（generate_report 生成数值固定的报告骨架），Step 3/4 加禁止事项

## 免责声明

本 Agent 仅供学习研究使用，不构成任何投资建议。股市有风险，投资需谨慎。
