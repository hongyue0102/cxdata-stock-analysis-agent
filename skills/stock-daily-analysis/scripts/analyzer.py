# -*- coding: utf-8 -*-
"""
股票每日分析 - 主入口模块

整合数据获取、技术分析和报告生成
提供简单的调用接口
"""

import logging
import os
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# 导入模块
from scripts.data_fetcher import get_daily_data
from scripts.trend_analyzer import StockTrendAnalyzer, _get_limit_pct
from scripts.ai_analyzer import AIAnalyzer
from scripts.notifier import AnalysisReport, format_analysis_report, format_dashboard_report


def load_config() -> Dict[str, Any]:
    """从环境变量加载配置"""
    return {
        "data": {
            "days": int(os.environ.get("DATA_DAYS", "20")),
        },
        "analysis": {
            "bias_threshold": float(os.environ.get("ANALYSIS_BIAS_THRESHOLD", "5.0")),
            "volume_shrink_ratio": float(os.environ.get("ANALYSIS_VOLUME_SHRINK_RATIO", "0.7")),
            "volume_heavy_ratio": float(os.environ.get("ANALYSIS_VOLUME_HEAVY_RATIO", "1.5")),
        },
    }


def analyze_stock(code: str, config: Optional[Dict] = None) -> Dict[str, Any]:
    """
    分析单只股票

    Args:
        code: 股票代码 (如 '600519', 'AAPL', '00700')
        config: 配置字典，可选

    Returns:
        包含技术分析结果的字典
    """
    if config is None:
        config = load_config()

    logger.info(f"开始分析股票: {code}")

    # 获取历史数据和股票名称（仅使用日行情接口）
    days = config.get('data', {}).get('days', 20)
    result = get_daily_data(code, days=days)

    if result is None:
        logger.error(f"无法获取 {code} 的数据")
        return {
            'code': code,
            'name': code,
            'error': '数据获取失败',
            'technical_indicators': {},
            'ai_analysis': {'operation_advice': '数据不足', 'sentiment_score': 0}
        }

    df, name = result

    if df.empty:
        logger.error(f"无法获取 {code} 的数据")
        return {
            'code': code,
            'name': name,
            'error': '数据获取失败',
            'technical_indicators': {},
            'ai_analysis': {'operation_advice': '数据不足', 'sentiment_score': 0}
        }

    # 技术分析
    analyzer = StockTrendAnalyzer()
    trend_result = analyzer.analyze(df, code, name)

    # 整理技术指标 + 生成供外层 Agent LLM 使用的 prompt
    ai_analyzer = AIAnalyzer()
    ai_result = ai_analyzer.analyze(code, name, trend_result.to_dict())

    # 整合结果
    result = {
        'code': code,
        'name': name,
        'technical_indicators': trend_result.to_dict(),
        'ai_analysis': ai_result
    }

    logger.info(f"{code} 分析完成，技术面评分: {ai_result.get('sentiment_score', trend_result.signal_score)}")
    return result


def analyze_stocks(codes: List[str], config: Optional[Dict] = None) -> List[Dict[str, Any]]:
    """
    分析多只股票

    Args:
        codes: 股票代码列表
        config: 配置字典，可选

    Returns:
        分析结果列表
    """
    results = []
    for code in codes:
        try:
            result = analyze_stock(code, config)
            results.append(result)
        except Exception as e:
            logger.error(f"分析 {code} 时出错: {e}")
            results.append({
                'code': code,
                'name': code,
                'error': str(e),
                'ai_analysis': {'operation_advice': '分析失败', 'sentiment_score': 0}
            })

    return results


def _fmt_num(val, decimals=2):
    """格式化数字"""
    if val is None:
        return 'N/A'
    return f"{val:.{decimals}f}"


def _fmt_volume(val):
    """格式化成交量（万）"""
    if val is None:
        return 'N/A'
    return f"{int(val / 10000)}万"


def _fmt_amount(val):
    """格式化成交额（亿）"""
    if val is None:
        return 'N/A'
    return f"{val / 100000000:.2f}亿"


def _fmt_pct(val):
    """格式化涨跌幅"""
    if val is None:
        return 'N/A'
    sign = '+' if val > 0 else ''
    return f"{sign}{val:.2f}%"


def generate_report(code: str, config: Optional[Dict] = None) -> str:
    """
    生成完整的 markdown 分析报告

    必须成功获取行情数据才能生成报告，否则返回错误信息。

    Args:
        code: 股票代码
        config: 配置字典，可选

    Returns:
        markdown 格式的完整分析报告
    """
    if config is None:
        config = load_config()

    days = config.get('data', {}).get('days', 20)

    # 1. 获取行情数据 — 失败则直接报错
    data_result = get_daily_data(code, days=days)
    if data_result is None:
        return f"❌ 无法获取 {code} 的行情数据，请检查数据源配置后重试。"

    df, name = data_result
    if df.empty:
        return f"❌ {code} ({name}) 行情数据为空，无法生成报告。"

    # 2. 技术分析
    trend_analyzer = StockTrendAnalyzer()
    trend_result = trend_analyzer.analyze(df, code, name)
    tech = trend_result.to_dict()

    # 3. 整理技术面结果
    ai_analyzer = AIAnalyzer()
    ai_result = ai_analyzer.analyze(code, name, tech)

    # 4. 最新行情
    latest = df.iloc[-1]
    report_date = str(latest['date'])[:10]

    # 5. 支撑压力位
    support_levels = []
    resistance_levels = []
    recent_high = df['high'].max()
    if tech.get('support_ma5'):
        support_levels.append((tech['ma5'], 'MA5 支撑有效'))
    if tech.get('support_ma10'):
        support_levels.append((tech['ma10'], 'MA10 支撑有效'))
    if tech.get('ma20'):
        support_levels.append((tech['ma20'], 'MA20 重要支撑'))
    resistance_levels.append((recent_high, f'近期高点 ({df.loc[df["high"].idxmax(), "date"].strftime("%m-%d")})'))

    # 6. 组装报告
    today = datetime.now().strftime('%Y-%m-%d')
    lines = []

    lines.append(f"# {code} {name} 股票分析报告")
    lines.append("")
    lines.append(f"> 生成时间: {today} | 数据来源: 财新数据平台 | 分析工具: A股技术分析系统")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 核心结论
    lines.append("## 核心结论")
    lines.append("")
    lines.append("| 项目 | 结果 |")
    lines.append("|------|------|")
    lines.append(f"| **AI结论** | {ai_result.get('operation_advice', 'N/A')} |")
    lines.append(f"| **综合评分** | {ai_result.get('sentiment_score', 0)}/100 |")
    lines.append(f"| **趋势判断** | {ai_result.get('trend_prediction', 'N/A')} |")
    lines.append(f"| **置信度** | {ai_result.get('confidence_level', 'N/A')} |")
    lines.append("")
    summary = ai_result.get('analysis_summary', '')
    if summary:
        lines.append(f"**一句话结论**: {summary}")
        lines.append("")
    lines.append("---")
    lines.append("")

    # 最新行情
    lines.append(f"## 最新行情 ({report_date})")
    lines.append("")
    lines.append("| 指标 | 数值 |")
    lines.append("|------|------|")
    lines.append(f"| 收盘价 | {_fmt_num(latest.get('close'))} |")
    lines.append(f"| 涨跌幅 | {_fmt_pct(latest.get('pct_chg'))} |")
    lines.append(f"| 开盘价 | {_fmt_num(latest.get('open'))} |")
    lines.append(f"| 最高价 | {_fmt_num(latest.get('high'))} |")
    lines.append(f"| 最低价 | {_fmt_num(latest.get('low'))} |")
    lines.append(f"| 成交量 | {_fmt_volume(latest.get('volume'))} |")
    lines.append(f"| 成交额 | {_fmt_amount(latest.get('amount'))} |")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 技术面分析
    lines.append("## 技术面分析")
    lines.append("")
    lines.append("### 均线系统")
    lines.append("")
    lines.append("| 均线 | 数值 | 乖离率 |")
    lines.append("|------|------|--------|")
    if 'ma5' in tech:
        lines.append(f"| MA5 | {_fmt_num(tech['ma5'])} | {_fmt_pct(tech.get('bias_ma5', 0))} |")
    if 'ma10' in tech:
        lines.append(f"| MA10 | {_fmt_num(tech['ma10'])} | {_fmt_pct(tech.get('bias_ma10', 0))} |")
    if 'ma20' in tech:
        lines.append(f"| MA20 | {_fmt_num(tech['ma20'])} | {_fmt_pct(tech.get('bias_ma20', 0))} |")
    lines.append("")
    lines.append(f"- **趋势状态**: {tech.get('trend_status', 'N/A')} ({tech.get('ma_alignment', '')})")
    lines.append(f"- **趋势强度**: {tech.get('trend_strength', 0)}/100")
    lines.append("")

    # MACD
    lines.append("### MACD 指标")
    lines.append("")
    lines.append("| 指标 | 数值 |")
    lines.append("|------|------|")
    lines.append(f"| DIF | {_fmt_num(tech.get('macd_dif', 0), 3)} |")
    lines.append(f"| DEA | {_fmt_num(tech.get('macd_dea', 0), 3)} |")
    lines.append(f"| MACD柱 | {_fmt_num(tech.get('macd_bar', 0), 3)} |")
    lines.append("")
    lines.append(f"- **MACD状态**: {tech.get('macd_status', 'N/A')}")
    lines.append(f"- **信号**: {tech.get('macd_signal', 'N/A')}")
    lines.append("")

    # RSI
    lines.append("### RSI 指标")
    lines.append("")
    lines.append("| 周期 | 数值 |")
    lines.append("|------|------|")
    lines.append(f"| RSI(6) | {_fmt_num(tech.get('rsi_6', 0))} |")
    lines.append(f"| RSI(12) | {_fmt_num(tech.get('rsi_12', 0))} |")
    lines.append(f"| RSI(20) | {_fmt_num(tech.get('rsi_20', 0))} |")
    lines.append("")
    lines.append(f"- **RSI状态**: {tech.get('rsi_status', 'N/A')} (RSI12 = {_fmt_num(tech.get('rsi_12', 0))})")
    lines.append(f"- **信号**: {tech.get('rsi_signal', 'N/A')}")
    lines.append("")

    # 量能
    lines.append("### 量能分析")
    lines.append("")
    lines.append("| 指标 | 数值 |")
    lines.append("|------|------|")
    lines.append(f"| 量能状态 | {tech.get('volume_status', 'N/A')} |")
    lines.append(f"| 5日量比 | {_fmt_num(tech.get('volume_ratio_5d', 0))} |")
    lines.append(f"| 量能趋势 | {tech.get('volume_trend', 'N/A')} |")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 支撑压力位
    lines.append("## 支撑与压力位")
    lines.append("")
    lines.append("| 类型 | 价位 | 依据 |")
    lines.append("|------|------|------|")
    for price, reason in support_levels:
        lines.append(f"| 支撑位 | {_fmt_num(price)} | {reason} |")
    for price, reason in resistance_levels:
        lines.append(f"| 压力位 | {_fmt_num(price)} | {reason} |")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 看多理由
    buy_reason = ai_result.get('buy_reason', '')
    if buy_reason:
        lines.append("## 看多理由")
        lines.append("")
        lines.append(f"- {buy_reason}")
        lines.append("")

    # 风险提示
    risk_warning = ai_result.get('risk_warning', '')
    if risk_warning:
        lines.append("## 风险提示")
        lines.append("")
        lines.append(f"- {risk_warning}")
        lines.append("")

    lines.append("---")
    lines.append("")

    # 近20日行情走势
    lines.append(f"## 近{days}日行情走势")
    lines.append("")
    lines.append("| 日期 | 开盘 | 最高 | 最低 | 收盘 | 涨跌幅 | 成交量 | 成交额 |")
    lines.append("|------|------|------|------|------|--------|--------|--------|")

    pct_highlight = _get_limit_pct(code, name) * 0.5
    for _, row in df.iloc[::-1].iterrows():
        date_str = str(row['date'])[:10]
        date_short = date_str[5:]
        close_str = f"**{_fmt_num(row['close'])}**"
        pct = row.get('pct_chg', 0) or 0
        pct_str = _fmt_pct(pct)
        if abs(pct) >= pct_highlight:
            pct_str = f"**{_fmt_pct(pct)}**"
        lines.append(
            f"| {date_short} | {_fmt_num(row['open'])} | {_fmt_num(row['high'])} | "
            f"{_fmt_num(row['low'])} | {close_str} | {pct_str} | "
            f"{_fmt_volume(row['volume'])} | {_fmt_amount(row['amount'])} |"
        )

    lines.append("")
    lines.append("---")
    lines.append("")

    lines.append("*免责声明: 本报告由 A股技术分析系统自动生成，基于公开市场数据和技术面分析，仅供学习研究参考，不构成任何投资建议。股市有风险，投资需谨慎。*")

    return "\n".join(lines)


def print_analysis(codes: List[str]) -> None:
    """
    分析股票并打印报告

    Args:
        codes: 股票代码列表
    """
    results = analyze_stocks(codes)

    # 转换为报告格式并打印
    reports = []
    for result in results:
        if 'error' not in result:
            from scripts.notifier import create_report_from_result
            report = create_report_from_result(result)
            reports.append(report)

    if reports:
        print("\n" + format_dashboard_report(reports))

        # 打印每个股票的详细报告
        for report in reports:
            print("\n" + format_analysis_report(report))
    else:
        print("没有可显示的报告")

