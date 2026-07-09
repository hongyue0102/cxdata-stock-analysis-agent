# -*- coding: utf-8 -*-
"""
通知/输出处理模块
负责格式化分析报告并输出结果
"""

import logging
import re
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

_CONTROL_RE = re.compile(r"[\r\n\t\x00-\x1f\x7f]")


def _sanitize(value) -> str:
    """净化用户/API 可控字段：剥离控制字符并转义 HTML 特殊字符，防止 XSS。"""
    if value is None:
        return ""
    cleaned = _CONTROL_RE.sub(" ", str(value))
    return (cleaned.replace("&", "&amp;")
                   .replace("<", "&lt;")
                   .replace(">", "&gt;")
                   .replace('"', "&quot;"))


@dataclass
class AnalysisReport:
    """分析报告数据结构"""
    code: str
    name: str
    sentiment_score: int
    trend_prediction: str
    operation_advice: str
    decision_type: str
    confidence_level: str
    technical_summary: Dict[str, Any]
    ai_analysis: Optional[str] = None
    risk_warning: str = ""
    buy_reason: str = ""
    support_levels: List[float] = None
    resistance_levels: List[float] = None
    
    def __post_init__(self):
        if self.support_levels is None:
            self.support_levels = []
        if self.resistance_levels is None:
            self.resistance_levels = []


def format_analysis_report(report: AnalysisReport) -> str:
    """
    格式化分析报告为文本
    
    Args:
        report: 分析报告数据
        
    Returns:
        格式化后的报告文本
    """
    lines = [
        f"{'='*50}",
        f"📊 {_sanitize(report.name)} ({_sanitize(report.code)}) 分析报告",
        f"{'='*50}",
        "",
        f"【核心结论】",
        f"  AI结论: {_sanitize(report.operation_advice)}",
        f"  趋势预测: {_sanitize(report.trend_prediction)}",
        f"  情绪评分: {report.sentiment_score}/100",
        f"  置信度: {_sanitize(report.confidence_level)}",
        "",
        f"【技术面分析】",
    ]
    
    # 技术指标
    tech = report.technical_summary
    if 'current_price' in tech:
        lines.append(f"  当前价格: {tech.get('current_price', 'N/A')}")
    
    if 'ma5' in tech and isinstance(tech['ma5'], (int, float)):
        lines.append(f"  MA5: {tech['ma5']:.2f} (乖离率: {tech.get('bias_ma5', 0):+.2f}%)")
    if 'ma10' in tech and isinstance(tech['ma10'], (int, float)):
        lines.append(f"  MA10: {tech['ma10']:.2f} (乖离率: {tech.get('bias_ma10', 0):+.2f}%)")
    if 'ma20' in tech and isinstance(tech['ma20'], (int, float)):
        lines.append(f"  MA20: {tech['ma20']:.2f}")
    
    if 'trend_status' in tech:
        lines.append(f"  趋势状态: {_sanitize(tech.get('trend_status', 'N/A'))}")
    
    if 'volume_status' in tech:
        lines.append(f"  量能状态: {_sanitize(tech.get('volume_status', 'N/A'))}")
    
    if 'macd_status' in tech:
        lines.append(f"  MACD: {_sanitize(tech.get('macd_status', 'N/A'))}")
    
    if 'rsi_status' in tech:
        lines.append(f"  RSI: {_sanitize(tech.get('rsi_status', 'N/A'))}")
    
    lines.append("")
    
    # 支撑压力位
    if report.support_levels:
        lines.append(f"【支撑位】")
        for level in report.support_levels[:3]:
            lines.append(f"  - {level:.2f}")
        lines.append("")
    
    if report.resistance_levels:
        lines.append(f"【压力位】")
        for level in report.resistance_levels[:3]:
            lines.append(f"  - {level:.2f}")
        lines.append("")
    
    # 看多理由
    if report.buy_reason:
        lines.append(f"【看多理由】")
        lines.append(f"  {_sanitize(report.buy_reason)}")
        lines.append("")
    
    # 风险警告
    if report.risk_warning:
        lines.append(f"【风险提示】")
        lines.append(f"  {_sanitize(report.risk_warning)}")
        lines.append("")
    
    # AI 分析
    if report.ai_analysis:
        lines.append(f"【AI 分析】")
        lines.append(f"  {_sanitize(report.ai_analysis)}")
        lines.append("")
    
    lines.append(f"{'='*50}")
    
    return "\n".join(lines)


def format_dashboard_report(reports: List[AnalysisReport]) -> str:
    """
    格式化决策仪表盘报告（多股票汇总）
    
    Args:
        reports: 分析报告列表
        
    Returns:
        格式化的仪表盘报告
    """
    if not reports:
        return "暂无分析报告"
    
    # 统计
    buy_count = sum(1 for r in reports if r.decision_type == 'buy')
    hold_count = sum(1 for r in reports if r.decision_type == 'hold')
    sell_count = sum(1 for r in reports if r.decision_type == 'sell')
    
    lines = [
        f"{'='*60}",
        f"📊 股票分析决策仪表盘",
        f"{'='*60}",
        "",
        f"分析股票数: {len(reports)} 只",
        f"🟢 看多: {buy_count}  🟡 观望: {hold_count}  🔴 看空: {sell_count}",
        "",
        f"{'='*60}",
    ]
    
    for report in reports:
        emoji = "🟢" if report.decision_type == 'buy' else "🟡" if report.decision_type == 'hold' else "🔴"
        lines.append(f"{emoji} {_sanitize(report.name)} ({_sanitize(report.code)})")
        lines.append(f"   结论: {_sanitize(report.operation_advice)} | 评分: {report.sentiment_score}/100")
        lines.append(f"   趋势: {_sanitize(report.trend_prediction)}")
        
        # 添加关键技术指标
        tech = report.technical_summary
        key_info = []
        
        if 'bias_ma5' in tech:
            key_info.append(f"乖离率: {tech['bias_ma5']:+.1f}%")
        if 'macd_status' in tech:
            key_info.append(f"MACD: {_sanitize(tech['macd_status'])}")
        
        if key_info:
            lines.append(f"   关键指标: {' | '.join(key_info)}")
        
        lines.append("")
    
    lines.append(f"{'='*60}")
    
    return "\n".join(lines)


def create_report_from_result(result: Dict[str, Any]) -> AnalysisReport:
    """
    从分析结果字典创建报告对象
    
    Args:
        result: 分析结果字典
        
    Returns:
        AnalysisReport 对象
    """
    technical = result.get('technical_indicators', {})
    ai_result = result.get('ai_analysis', {})
    
    # 确定决策类型
    advice = ai_result.get('operation_advice', '观望')
    if advice in ['看多', '加仓', '强烈看多']:
        decision_type = 'buy'
    elif advice in ['看空', '减仓', '强烈看空']:
        decision_type = 'sell'
    else:
        decision_type = 'hold'
    
    return AnalysisReport(
        code=result.get('code', ''),
        name=result.get('name', ''),
        sentiment_score=ai_result.get('sentiment_score', 50),
        trend_prediction=ai_result.get('trend_prediction', '震荡'),
        operation_advice=advice,
        decision_type=decision_type,
        confidence_level=ai_result.get('confidence_level', '中'),
        technical_summary=technical,
        ai_analysis=ai_result.get('analysis_summary', ''),
        risk_warning=ai_result.get('risk_warning', ''),
        buy_reason=ai_result.get('buy_reason', ''),
        support_levels=technical.get('support_levels', []),
        resistance_levels=technical.get('resistance_levels', []),
    )


def print_report(report: AnalysisReport) -> None:
    """打印分析报告到控制台"""
    print(format_analysis_report(report))


def print_dashboard(reports: List[AnalysisReport]) -> None:
    """打印决策仪表盘到控制台"""
    print(format_dashboard_report(reports))
