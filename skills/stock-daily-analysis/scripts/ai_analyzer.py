# -*- coding: utf-8 -*-
"""
技术面分析结果整理模块

将技术指标结构化输出，供外层 Agent LLM 做决策。
"""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class AIAnalyzer:
    """技术面分析结果整理器"""

    def analyze(self, code: str, name: str, technical_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        基于技术指标生成结构化分析结果

        Args:
            code: 股票代码
            name: 股票名称
            technical_data: 技术指标数据

        Returns:
            基于技术面的分析结果字典
        """
        return self._default_analysis_from_tech(technical_data)

    def _default_analysis_from_tech(self, tech: Dict[str, Any]) -> Dict[str, Any]:
        """基于技术面的默认分析"""
        score = tech.get('signal_score', 50)
        buy_signal = tech.get('buy_signal', '观望')

        return {
            'sentiment_score': score,
            'trend_prediction': tech.get('trend_status', '震荡'),
            'operation_advice': buy_signal,
            'confidence_level': '高' if score >= 70 else '中' if score >= 50 else '低',
            'analysis_summary': ' | '.join(tech.get('signal_reasons', []))[:100],
            'buy_reason': ', '.join(tech.get('signal_reasons', [])),
            'risk_warning': ' | '.join(tech.get('risk_factors', [])),
            'target_price': '',
            'stop_loss': '',
            'price_disclaimer': '若假设不成立，实际价格可能显著偏离。投资者应根据自身风险承受能力独立决策。'
        }
