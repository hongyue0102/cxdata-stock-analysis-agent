# A股技术分析专家 Agent

面向 A 股市场的技术分析智能分身，用户只需说"分析 600519"即可获得完整的技术面分析报告。

## 功能

- 获取 A 股日线行情数据（通过财新数据平台）
- 计算技术指标：均线系统、MACD、RSI、乖离率、量能
- Agent LLM 亲自解读每个技术指标，给出 AI 结论
- 生成完整的 Markdown 分析报告

## 使用方式

对 Agent 说：

- "分析 600519"
- "帮我看看 300590 移为通信"
- "贵州茅台技术面怎么样"

Agent 会自动：获取数据 → 计算指标 → AI 解读 → 生成报告

## 前置依赖

1. 安装 Python 依赖：`pip install pandas numpy requests python-dotenv`
2. 首次运行时自动引导配置密钥：
   - 前往 [财新数据平台](https://yun.ccxe.com.cn/data/Skills) 注册并申请 `CXDA_USER_KEY`（**平台目前处于推广期，可免费试用**）
   - 首次执行分析时会提示输入密钥，自动保存，以后无需再配
   - 数据源 Skill 已内置在 Agent 中，无需额外下载

## 目录结构

```
cxdata-stock-analysis-agent/
├── AGENT.md              # Agent 整体人设与执行逻辑
├── SOUL.md               # 身份、性格、能力边界
├── rules.md              # 硬性规则
├── config.json           # 元数据配置
├── skills/
│   ├── stock-market-information/  # 内置数据源 Skill（财新数据平台 API）
│   │   ├── SKILL.md
│   │   ├── references/            # API 接口文档
│   │   └── scripts/
│   │       ├── api_query.py       # 统一 API 调用工具
│   │       └── .env               # 数据源配置（CXDA_USER_KEY / BASE_URL）
│   └── stock-daily-analysis/     # 技术分析 Skill
│       ├── SKILL.md              # Skill 定义（含 frontmatter）
│       ├── requirements.txt
│       └── scripts/
│           ├── analyzer.py       # 主入口
│           ├── data_fetcher.py   # 数据获取（调用内置 stock-market-information）
│           ├── trend_analyzer.py # 技术分析引擎
│           ├── ai_analyzer.py    # 结果整理
│           ├── notifier.py       # 报告输出
│           ├── .env.example      # 分析参数配置模板
│           └── prompts/
│               └── analysis_prompt.md
└── README.md
```

## 免责声明

本 Agent 仅供学习研究使用，不构成任何投资建议。股市有风险，投资需谨慎。
