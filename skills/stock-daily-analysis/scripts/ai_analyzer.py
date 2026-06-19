# -*- coding: utf-8 -*-
"""
技术面分析结果整理模块

职责分工：
- technical_indicators 字段：原始指标数据（由 trend_analyzer 计算），LLM 解读的数据来源
- 本模块输出：基于 technical_indicators 派生的结构化判断（关键价位/合理区间/风险点/观察点）
- LLM 任务：把本模块输出的结构化判断写成通顺段落，不得自创关键判断

为什么删除 analysis_summary / buy_reason / risk_warning：
  这些字段是 Python 拼接的成句，LLM 看到会直接抄跳过解读。
  改为输出原始标签（signal_labels/risk_labels）+ 派生结构化判断，
  LLM 必须自己组织语言。
"""

import logging
from typing import Dict, Any, List, Tuple

logger = logging.getLogger(__name__)


def _safe_float(val, default=0.0) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


class AIAnalyzer:
    """技术面分析结果整理器"""

    def analyze(self, code: str, name: str, technical_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        基于 technical_indicators 派生结构化判断，供 LLM 引用。

        输出字段：
          - sentiment_score / trend_prediction / confidence_level / signal_labels / risk_labels
          - key_levels: 4 个关键价位（Python 算，LLM 必须引用）
          - reasonable_range: 合理价值区间（Python 算，LLM 必须引用）
          - risk_points: 风险点列表（Python 按阈值触发，LLM 必须全列）
          - observation_points: 关键观察点（Python 给模板，LLM 必须涵盖）
        """
        tech = technical_data or {}
        score = _safe_float(tech.get('signal_score', 50))
        buy_signal = tech.get('buy_signal', '观望')

        return {
            # 评分与方向（Python 固定）
            'sentiment_score': score,
            'trend_prediction': tech.get('trend_status', '震荡'),
            'operation_advice': buy_signal,
            'confidence_level': '高' if score >= 70 else '中' if score >= 50 else '低',

            # 信号标签（改名为 labels，明确是"标签"不是"成句"）
            'signal_labels': tech.get('signal_reasons', []),
            'risk_labels': tech.get('risk_factors', []),

            # 派生结构化判断（关键：决定两次报告一致性）
            'key_levels': self._calc_key_levels(tech),
            'reasonable_range': self._calc_reasonable_range(tech, buy_signal),
            'risk_points': self._trigger_risk_points(tech),
            'observation_points': self._gen_observation_points(tech, buy_signal),
        }

    def _calc_key_levels(self, tech: Dict[str, Any]) -> Dict[str, float]:
        """4 个关键价位：强支撑 / 短支撑 / 第一压力 / 强压力"""
        return {
            'strong_support': round(_safe_float(tech.get('ma20')), 2),
            'short_support': round(_safe_float(tech.get('ma5')), 2),
            'first_resistance': round(_safe_float(tech.get('recent_5d_high')), 2),
            'strong_resistance': round(_safe_float(tech.get('prev_high')), 2),
        }

    def _calc_reasonable_range(self, tech: Dict[str, Any], buy_signal: str) -> Tuple[float, float]:
        """合理价值区间，按趋势方向动态计算"""
        ma5 = _safe_float(tech.get('ma5'))
        ma10 = _safe_float(tech.get('ma10'))
        ma20 = _safe_float(tech.get('ma20'))
        current = _safe_float(tech.get('current_price'))
        first_resistance = _safe_float(tech.get('recent_5d_high'))

        if buy_signal in ('看多', '强烈看多'):
            lower, upper = ma5, first_resistance
        elif buy_signal == '看空':
            lower, upper = ma20, ma5
        else:  # 观望 / 震荡
            if ma5 > current:
                lower, upper = ma10, ma5
            else:
                lower, upper = ma10, first_resistance

        # 兜底：若上下限异常（如 upper <= lower），退化用 ma20 ~ ma5
        if upper <= lower:
            lower, upper = ma20, ma5 if ma5 > ma20 else ma20 * 1.05

        return (round(lower, 2), round(upper, 2))

    def _trigger_risk_points(self, tech: Dict[str, Any]) -> List[str]:
        """按阈值触发风险点，所有命中的都进入列表"""
        points: List[str] = []

        rsi_6 = _safe_float(tech.get('rsi_6'))
        bias_ma20 = _safe_float(tech.get('bias_ma20'))
        volume_ratio = _safe_float(tech.get('volume_ratio_5d'))
        latest_pct = _safe_float(tech.get('latest_pct_chg'))
        near_high_pct = _safe_float(tech.get('near_high_pct'))
        prev_high = _safe_float(tech.get('prev_high'))
        prev_high_date = tech.get('prev_high_date', '')
        support_rate = _safe_float(tech.get('ma_support_success_rate'))
        support_count = _safe_float(tech.get('ma_support_count'))
        macd_bar = _safe_float(tech.get('macd_bar'))
        recent_5d_gain = _safe_float(tech.get('recent_5d_gain_pct'))
        consecutive_up = _safe_float(tech.get('consecutive_up_days'))

        # RSI 超买超卖
        if rsi_6 >= 80:
            points.append(f'RSI(6)={rsi_6:.1f} 严重超买')
        elif rsi_6 >= 70:
            points.append(f'RSI(6)={rsi_6:.1f} 进入超买区')
        elif rsi_6 <= 20:
            points.append(f'RSI(6)={rsi_6:.1f} 严重超卖')
        elif rsi_6 <= 30:
            points.append(f'RSI(6)={rsi_6:.1f} 进入超卖区')

        # MA20 乖离
        if bias_ma20 >= 10:
            points.append(f'MA20 乖离 {bias_ma20:.1f}%，价格严重偏离中期均值')
        elif bias_ma20 >= 5:
            points.append(f'MA20 乖离 {bias_ma20:.1f}%，价格偏离中期均值较大')
        elif bias_ma20 <= -10:
            points.append(f'MA20 乖离 {bias_ma20:.1f}%，价格严重跌破中期均值')

        # 量价配合
        if volume_ratio < 0.8 and abs(latest_pct) < 1:
            points.append(f'价滞量缩（量比 {volume_ratio:.2f}），多头动能衰减')
        if volume_ratio > 2.0 and latest_pct > 5:
            points.append(f'放量暴涨（量比 {volume_ratio:.2f}），警惕高位出货')

        # 前高压力
        if 0 < near_high_pct <= 3:
            points.append(f'距前高 {prev_high:.2f}（{prev_high_date}）仅 {near_high_pct:.1f}%，套牢盘压力临近')
        elif near_high_pct <= 0 and prev_high > 0:
            points.append(f'已突破前高 {prev_high:.2f}（{prev_high_date}），上方无近端压力')

        # MA 支撑
        if support_count >= 3 and support_rate < 0.5:
            points.append(f'MA 支撑成功率仅 {support_rate:.0%}（{int(support_count)} 次测试），支撑偏弱')

        # MACD 反转
        if macd_bar < 0:
            points.append('MACD 绿柱，多头动能不足')

        # 涨幅过大
        if recent_5d_gain >= 15:
            points.append(f'近 5 日涨幅 {recent_5d_gain:.1f}%，短期涨幅过大')
        if consecutive_up >= 5:
            points.append(f'连涨 {int(consecutive_up)} 日，技术性回调概率上升')

        return points

    def _gen_observation_points(self, tech: Dict[str, Any], buy_signal: str) -> List[str]:
        """基于信号组合生成观察点模板"""
        obs: List[str] = []
        ma5 = _safe_float(tech.get('ma5'))
        ma20 = _safe_float(tech.get('ma20'))
        prev_high = _safe_float(tech.get('prev_high'))
        near_high_pct = _safe_float(tech.get('near_high_pct'))
        rsi_6 = _safe_float(tech.get('rsi_6'))
        macd_status = tech.get('macd_status', '')
        volume_status = tech.get('volume_status', '')

        if buy_signal in ('看多', '强烈看多'):
            obs.append(f'价格能否在 MA5({ma5:.2f}) 企稳')
        if 0 < near_high_pct <= 5:
            obs.append(f'能否突破前高 {prev_high:.2f}（距 {near_high_pct:.1f}%）')
        if rsi_6 > 70:
            obs.append('RSI(6) 是否回落到 70 以下')
        elif rsi_6 < 30:
            obs.append('RSI(6) 是否回升到 30 以上')
        if macd_status in ('多头', 'BULLISH'):
            obs.append('MACD 红柱能否维持或放大')
        if '缩量' in str(volume_status) or 'SHRINK' in str(volume_status).upper():
            obs.append('量能是否恢复到 5 日均量以上')
        obs.append(f'MA20({ma20:.2f}) 是否被有效跌破（趋势反转信号）')

        return obs
