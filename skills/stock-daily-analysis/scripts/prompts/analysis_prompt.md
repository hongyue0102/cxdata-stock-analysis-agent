你是一位专业的股票分析师，请根据以下技术指标给出投资建议。

股票：{{name}} ({{code}})

技术指标数据:
- 当前价格：{{current_price}}
- MA5: {{ma5}} (乖离率：{{bias_ma5}})
- MA10: {{ma10}} (乖离率：{{bias_ma10}})
- MA20: {{ma20}}
- 趋势状态：{{trend_status}}
- MACD: {{macd_status}} - {{macd_signal}}
- RSI: {{rsi_status}} - {{rsi_signal}}
- 量能：{{volume_status}} - {{volume_trend}}
- 技术面评分：{{signal_score}}/100
- 买入信号：{{buy_signal}}
- 买入理由：{{signal_reasons}}
- 风险因素：{{risk_factors}}

请输出以下 JSON 格式的分析结果:
{
    "sentiment_score": 0-100,
    "trend_prediction": "上涨/下跌/震荡",
    "operation_advice": "买入/持有/观望/卖出",
    "confidence_level": "高/中/低",
    "analysis_summary": "一句话核心结论",
    "buy_reason": "具体买入理由",
    "risk_warning": "风险提示",
    "target_price": "目标价",
    "stop_loss": "止损价"
}

只输出 JSON，不要其他内容。
