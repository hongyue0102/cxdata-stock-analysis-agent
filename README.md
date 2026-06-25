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

### 2026-06-25 对齐同事官方积分机制（jsonl 追加日志）+ 保留全部安全加固

同事 6-24 提供官方最新四件套（query/common/cxda_cache_cli/auth），积分统计采用更优的 **jsonl 追加日志机制**（取代旧的 JSON 读改写 + _ledger_lock 文件锁）。本次对齐官方机制，同时保留之前做的全部安全加固。

**积分机制（对齐同事官方版）：**
- 记账改为 `append_shared_text` 追加到 `cxda_session_calls.jsonl`，天然并发安全，无需文件锁
- 会话隔离用 `session_id`（uuid）；query.py 积分逻辑与同事版 diff 0（完全一致）
- 移除 _ledger_lock；analyzer.py 的 session start/summary 流程保留

**安全加固（全部保留）：**
- SSRF url 白名单、filename 校验、凭证加密（cred_crypto）、文件权限 0o600/0o700、异常脱敏、workspace 校验、cli 路径遍历防护
- api_main 白名单（覆盖后补回）
- B 股排除（data_fetcher normalize_code）

**环境**：.venv 安装 cryptography（凭证加密依赖）

**验证**：完整取数 jsonl 记账正常；安全防护 11 项全在；积分记账函数与同事版逐字节一致

### 2026-06-24 安全扫描 6 条风险修复（按客户要求）

客户扫描命中 6 条输入验证/凭证类风险，逐条核实后全部修复：

| # | 风险 | 修复 |
|---|---|---|
| 1 | cmd_package 的 --api-main SQLi | `query.py` cmd_package 开头加 `^[A-Za-z0-9_-]+$` 白名单校验，与 api_id 一致，拒绝 SQL 注入 payload；顶部补 import re |
| 2/3 | verify/send-code 异常泄露 url（含验证码/手机号）| `auth.py` 新增 `_safe_net_error(e)`，网络异常只返回异常类型名，剥离含 phone/verifyCode 的 url；send-code、verify 两处 except 改用 |
| 4 | 凭证文件权限过松（默认 0o644）| `cxda_cache_cli.py` 新增 `_secure_write_text`（os.open 指定 0o600），shared_write/私域 write 改用它；5 处 mkdir 加 `mode=0o700` |
| 5 | get/save_shared_json 路径遍历 | `common.py` 新增 `_validate_shared_filename`，filename 只允许字母数字下划线连字符点（CLI 侧 _validate_filename 已有防护，入口层双保险）|
| 6 | http_get SSRF | `common.py` http_get 加 url 白名单，必须以 BASE_URL 开头（官方 cxdata 域名），拒绝其他 host |

**验证**：6 条防护端到端测试通过（api;DROP 拒绝、../etc 拒绝且正常名不误伤、evil.com 拒绝、异常不含手机号/验证码、文件权限 0o600）

### 2026-06-24 排除 B 股（仅分析 A 股）

- **问题**：`normalize_code` 对 6 位数字代码统一判成 'a'（A股），**不识别 B 股**。用户传 B 股代码（上交所 900 开头、深交所 200 开头）会被当 A 股查询、生成报告，与本 agent「仅分析 A 股」定位不符。
- **修复**：`data_fetcher.py` `normalize_code` 增加 B 股识别——900/200 开头判成 'b' 市场，由 `get_daily_data` 的 `market != 'a'` 校验拒绝（日志提示「仅支持 A 股，为 b 市场代码」）。
- **验证**：900901/200002 识别为 b 并被拒绝返回 None；600000/000001/688478/920083/AAPL/00700 不误伤。

### 2026-06-24 积分记账并发安全 + session 规范流程（同步主线 agent）

- **query.py** 同步主线 agent 的 `_ledger_lock` 文件锁修复：给 `_record_call_if_billable` 和 `_guard_before_billable_api_call` 的「读-改-写」整个临界区加 flock 排他锁，根治并发 subprocess 互相覆盖导致积分记账丢失（同源工具，保持一致；当前本 agent 虽串行查单股不触发，但防患未然）
- **analyzer.py** `analyze_stocks` 加 session 规范流程：开头 `session start` 重置账本，结尾 `session summary` 输出本轮消耗；积分消耗以 session summary 返回为准，不由 AI 自行统计
- 说明：本 agent 是逐股查询（单股 pageSize=20），不存在主线 agent 的「pageSize 写死 10000」问题，故未做 pageSize 动态化

### 2026-06-23 修复安全扫描命中的路径遍历/RCE/XSS/日志注入风险（commit 3f38c49）

- **问题**：安全扫描命中 6 条风险项，均为潜在风险（当前调用入口 filename 硬编码不可直接利用），但属纵深防御应加固
- **修复**（4 文件，纯安全加固，无业务逻辑改动）：
  - `cxda_cache_cli.py`：新增 `_validate_filename` 与 `_check_within_workspace`，拦截 `../` / 绝对路径 / 盘符逃逸；workspace 环境变量校验 `..` 段
  - `common.py`：新增 `_validate_exec_path`，校验 `CXDA_CACHE_PYTHON` / `CXDA_CACHE_CLI_PATH`（必须绝对路径、不含 `..`、文件存在，CLI_PATH 需 `.py` 后缀）与 workspace 环境变量，非法时回退安全默认值，防环境变量注入 RCE
  - `analyzer.py`：新增 `_sanitize_for_markdown` / `_sanitize_for_log`，净化拼入 markdown 报告的 code/name（防 XSS）与日志中的 code（防日志注入）
  - `trend_analyzer.py`：logger 中的 code 经 `_sanitize_for_log` 净化
- **验证**：4 文件 `py_compile` 通过；`../../etc/passwd` 等路径遍历被拦截，正常读写不受影响

### 2026-06-19 修复 RSI 字段名与计算周期不一致（commit dfc8f65）

- **问题**：`RSI_LONG` 常量已是 20，但字段名、报告显示文案仍为 24（历史遗留），导致报告中显示 `RSI(24)` 但实际算的是 `RSI(20)`，与 20 天行情数据对不上
- **修复**：3 个文件 5 处统一改为 20
  - `trend_analyzer.py`：dataclass 字段 `rsi_24` → `rsi_20`（含 to_dict / 赋值处）
  - `analyzer.py`：报告模板 `RSI(24)` → `RSI(20)`，`tech.get('rsi_24')` → `rsi_20`
  - `SKILL.md`：占位符 `rsi_24` → `rsi_20`
- 验证：`analyze_stock('600519')` 输出 rsi_6/12/20 均正常，rsi_24 字段已移除

### 2026-06-18 技术指标计算改用前复权行情接口（commit d2b2988）

- **问题**：旧逻辑用不复权行情算技术指标，除权除息日会出现虚假跳空，导致均线/MACD/RSI 失真
- **数据用途分工**（按市场分析惯例）：
  - 近 20 日展示 + 最新行情 + 昨收价 → `getStkDayQuoByCond-G`（不复权）
  - 技术指标计算（均线/MACD/RSI/BIAS）→ `getDStkPriceMidDivByCond-G`（前复权）
- **实现**：
  - `data_fetcher.py`：`_run_query` 加 `api_id` 参数；新增 `_fetch_fq_quote`；`get_daily_data` 同时拉两份数据，按 date 合并 `open_fq/high_fq/low_fq/close_fq`；前复权拉取失败时退化用不复权
  - `trend_analyzer.py`：`analyze` 入口把 OHLC 替换为前复权版本（保留 `*_raw`），下游所有指标计算代码不用改；`current_price` 用 `close_raw` 展示真实成交价
- **验证**：工商银行 5/12 除权数据 close=7.48 vs close_fq=7.31，差异 0.17 元正是除权调整

### 2026-06-18 修复安全扫描命中的 SSRF 风险（commit 5690893）

- 扫描命中 3 条，核实后只有 1 条真实存在
- **SSRF**（真实）：`query.py cmd_api` 中 `api_id` 直接拼接到 URL path，存在 path traversal 风险 → 加正则白名单 `^[A-Za-z0-9_-]+$`；`cmd_page_size` 同步加（防御深度）
- **.env 注入 SSRF**（误报）：扫描器引用的 `_setup_key_interactively` 函数和 `api_query.py` 文件早在 6/12 commit `9ed84ff` 已删除
- **环境变量 RCE**（误报）：`SKI_STOCK_MARKET_INFO_PATH` / `SKILL_DIR` / `API_QUERY_SCRIPT` 在当前代码中不存在
- 与主线 agent commit `3fff527` 保持同构修复

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
