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

    def _calc_key_levels(self, tech: Dict[str, Any]) -> Dict[str, Any]:
        """4 个关键价位 + 依据说明：强支撑 / 短支撑 / 第一压力 / 强压力

        角色按价格 vs 均线动态判定（不再无脑把 MA20 当支撑）：
        - 价格【下方】的均线 → 支撑（离价最近=短支撑，最远=强支撑）
        - 价格【上方】的均线 → 压力（离价最近=第一压力，最远=强压力）
        这样多头排列时 MA20 自然成为强支撑，空头排列时 MA20 成为强压力，
        与实际价位的支撑/压力含义一致。

        返回：
          strong_support / short_support / first_resistance / strong_resistance: 价位(float)
          level_notes: dict，每个 key 对应的依据文字（供骨架展示）
        """
        current = _safe_float(tech.get('current_price'))
        ma5 = _safe_float(tech.get('ma5'))
        ma10 = _safe_float(tech.get('ma10'))
        ma20 = _safe_float(tech.get('ma20'))
        recent_5d_high = _safe_float(tech.get('recent_5d_high'))
        prev_high = _safe_float(tech.get('prev_high'))
        prev_high_date = tech.get('prev_high_date', '')

        # 三条均线按相对价格分到支撑/压力池（忽略与价格几乎重合的线，阈值 0.1%）
        eps = abs(current) * 0.001 if current else 0.01
        supports = []   # [(价位, 名称)] 价格下方的线
        resistances = []  # [(价位, 名称)] 价格上方的线
        for price, name in ((ma20, 'MA20'), (ma10, 'MA10'), (ma5, 'MA5')):
            if price <= 0:
                continue
            if price < current - eps:
                supports.append((price, name))
            elif price > current + eps:
                resistances.append((price, name))
            # 与价格几乎重合的线不计入，避免噪声

        # 支撑：离价最近=短支撑，最远=强支撑
        supports.sort(key=lambda x: x[0], reverse=True)  # 价高者离价近
        short_support_p, short_support_n = (supports[0] if supports else (0.0, ''))
        strong_support_p, strong_support_n = (supports[-1] if supports else (0.0, ''))

        # 均线压力：离价最近=第一压力，最远=强压力
        resistances.sort(key=lambda x: x[0])  # 价低者离价近
        ma_resist_first_p, ma_resist_first_n = (resistances[0] if resistances else (0.0, ''))
        ma_resist_strong_p, ma_resist_strong_n = (resistances[-1] if resistances else (0.0, ''))

        # 第一压力：取「均线近端压力」与「近 5 日高点」中较低者（先碰到的）
        first_candidates = [(p, n) for p, n in [(ma_resist_first_p, ma_resist_first_n), (recent_5d_high, '近 5 日最高')] if p > 0]
        first_candidates.sort(key=lambda x: x[0])
        first_resistance_p, first_resistance_n = (first_candidates[0] if first_candidates else (0.0, ''))

        # 强压力：取「均线远端压力」与「前高」中较高者（最难突破的）
        strong_candidates = [(p, n) for p, n in [(ma_resist_strong_p, ma_resist_strong_n), (prev_high, '前高（套牢盘）')] if p > 0]
        strong_candidates.sort(key=lambda x: x[0], reverse=True)
        strong_resistance_p, strong_resistance_n = (strong_candidates[0] if strong_candidates else (0.0, ''))

        # 注意：支撑位可能缺失（如价格跌破所有均线时，下方无均线支撑），
        # 此时显示为空，不硬凑反向价位——那会把压力误标成支撑。
        return {
            'strong_support': round(strong_support_p, 2) if strong_support_p else None,
            'short_support': round(short_support_p, 2) if short_support_p else None,
            'first_resistance': round(first_resistance_p, 2) if first_resistance_p else None,
            'strong_resistance': round(strong_resistance_p, 2) if strong_resistance_p else None,
            'level_notes': {
                'strong_support': f'{strong_support_n} 支撑' if strong_support_n else '下方无均线支撑',
                'short_support': f'{short_support_n} 支撑' if short_support_n else '下方无均线支撑',
                'first_resistance': first_resistance_n if first_resistance_n else '上方无明显压力',
                'strong_resistance': strong_resistance_n if strong_resistance_n else '上方无明显压力',
            },
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
        if support_count >= 3 and support_rate <= 0.5:
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
