# -*- coding: utf-8 -*-
"""
趋势交易分析器 - 基于交易理念的技术分析

核心原则：
1. 严进策略 - 不追高，追求每笔交易成功率
2. 趋势交易 - MA5>MA10>MA20 多头排列，顺势而为
3. 买点偏好 - 在 MA5/MA10 附近回踩买入
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


# ── 输入净化 ──────────────────────────────────────────────────────────

# 控制字符与换行（防日志注入）
_CONTROL_RE = re.compile(r"[\r\n\t\x00-\x1f\x7f]")


def _sanitize_for_log(value) -> str:
    """净化日志输出，剥离换行等控制字符，防止日志注入/伪造审计条目"""
    if value is None:
        return ""
    return _CONTROL_RE.sub(" ", str(value))


class TrendStatus(Enum):
    """趋势状态枚举"""
    STRONG_BULL = "强势多头"
    BULL = "多头排列"
    WEAK_BULL = "弱势多头"
    CONSOLIDATION = "盘整"
    WEAK_BEAR = "弱势空头"
    BEAR = "空头排列"
    STRONG_BEAR = "强势空头"


class VolumeStatus(Enum):
    """量能状态枚举"""
    HEAVY_VOLUME_UP = "放量上涨"
    HEAVY_VOLUME_DOWN = "放量下跌"
    SHRINK_VOLUME_UP = "缩量上涨"
    SHRINK_VOLUME_DOWN = "缩量回调"
    NORMAL = "量能正常"


class BuySignal(Enum):
    """买入信号枚举"""
    STRONG_BUY = "强烈看多"
    BUY = "看多"
    HOLD = "继续跟踪"
    WAIT = "观望"
    SELL = "看空"
    STRONG_SELL = "强烈看空"


class MACDStatus(Enum):
    """MACD状态枚举"""
    GOLDEN_CROSS_ZERO = "零轴上金叉"
    GOLDEN_CROSS = "金叉"
    BULLISH = "多头"
    CROSSING_UP = "上穿零轴"
    CROSSING_DOWN = "下穿零轴"
    BEARISH = "空头"
    DEATH_CROSS = "死叉"


class RSIStatus(Enum):
    """RSI状态枚举"""
    OVERBOUGHT = "超买"
    STRONG_BUY = "强势看多"
    NEUTRAL = "中性"
    WEAK = "弱势"
    OVERSOLD = "超卖"


@dataclass
class TrendAnalysisResult:
    """趋势分析结果"""
    code: str
    
    # 趋势判断
    trend_status: TrendStatus = TrendStatus.CONSOLIDATION
    ma_alignment: str = ""
    trend_strength: float = 0.0
    
    # 均线数据
    ma5: float = 0.0
    ma10: float = 0.0
    ma20: float = 0.0
    ma60: float = 0.0
    current_price: float = 0.0
    
    # 乖离率
    bias_ma5: float = 0.0
    bias_ma10: float = 0.0
    bias_ma20: float = 0.0
    
    # 量能分析
    volume_status: VolumeStatus = VolumeStatus.NORMAL
    volume_ratio_5d: float = 0.0
    volume_trend: str = ""
    
    # 支撑压力
    support_ma5: bool = False
    support_ma10: bool = False
    resistance_levels: List[float] = field(default_factory=list)
    support_levels: List[float] = field(default_factory=list)
    
    # MACD 指标
    macd_dif: float = 0.0
    macd_dea: float = 0.0
    macd_bar: float = 0.0
    macd_status: MACDStatus = MACDStatus.BULLISH
    macd_signal: str = ""
    
    # RSI 指标
    rsi_6: float = 0.0
    rsi_12: float = 0.0
    rsi_20: float = 0.0
    rsi_status: RSIStatus = RSIStatus.NEUTRAL
    rsi_signal: str = ""
    
    # 买入信号
    buy_signal: BuySignal = BuySignal.WAIT
    signal_score: int = 0
    signal_reasons: List[str] = field(default_factory=list)
    risk_factors: List[str] = field(default_factory=list)

    # 量化增强指标
    consecutive_up_days: int = 0
    recent_5d_gain_pct: float = 0.0
    recent_10d_gain_pct: float = 0.0
    ma_convergence: float = 0.0
    prev_ma_convergence: float = 0.0
    price_phase: str = "盘整"
    rsi_overbuy_type: str = "非超买"
    rsi_risk_level: str = "无"
    near_high_pct: float = 0.0
    breakout_signal: str = "远离前高"
    prev_high: float = 0.0
    prev_high_date: str = ""
    ma_support_count: int = 0
    ma_support_success_rate: float = 0.0
    # 供 ai_analyzer 规则计算用
    recent_5d_high: float = 0.0
    latest_pct_chg: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'code': self.code,
            'trend_status': self.trend_status.value,
            'ma_alignment': self.ma_alignment,
            'trend_strength': self.trend_strength,
            'ma5': self.ma5,
            'ma10': self.ma10,
            'ma20': self.ma20,
            'ma60': self.ma60,
            'current_price': self.current_price,
            'bias_ma5': self.bias_ma5,
            'bias_ma10': self.bias_ma10,
            'bias_ma20': self.bias_ma20,
            'volume_status': self.volume_status.value,
            'volume_ratio_5d': self.volume_ratio_5d,
            'volume_trend': self.volume_trend,
            'support_ma5': self.support_ma5,
            'support_ma10': self.support_ma10,
            'buy_signal': self.buy_signal.value,
            'signal_score': self.signal_score,
            'signal_reasons': self.signal_reasons,
            'risk_factors': self.risk_factors,
            'macd_dif': self.macd_dif,
            'macd_dea': self.macd_dea,
            'macd_bar': self.macd_bar,
            'macd_status': self.macd_status.value,
            'macd_signal': self.macd_signal,
            'rsi_6': self.rsi_6,
            'rsi_12': self.rsi_12,
            'rsi_20': self.rsi_20,
            'rsi_status': self.rsi_status.value,
            'rsi_signal': self.rsi_signal,
            # 量化增强指标
            'consecutive_up_days': self.consecutive_up_days,
            'recent_5d_gain_pct': round(self.recent_5d_gain_pct, 2),
            'recent_10d_gain_pct': round(self.recent_10d_gain_pct, 2),
            'ma_convergence': round(self.ma_convergence, 4),
            'prev_ma_convergence': round(self.prev_ma_convergence, 4),
            'price_phase': self.price_phase,
            'rsi_overbuy_type': self.rsi_overbuy_type,
            'rsi_risk_level': self.rsi_risk_level,
            'near_high_pct': round(self.near_high_pct, 2),
            'breakout_signal': self.breakout_signal,
            'prev_high': self.prev_high,
            'prev_high_date': self.prev_high_date,
            'ma_support_count': self.ma_support_count,
            'ma_support_success_rate': round(self.ma_support_success_rate, 2),
            'recent_5d_high': round(self.recent_5d_high, 2),
            'latest_pct_chg': round(self.latest_pct_chg, 2),
        }


def _get_board(code):
    """根据股票代码返回板块: bse(北交所) / gem(创业板) / star(科创板) / main(主板)"""
    if not code:
        return "main"
    prefix = code[:2]
    if prefix in ("83", "87", "88", "92"):
        return "bse"
    elif prefix == "30":
        return "gem"
    elif prefix == "68":
        return "star"
    else:
        return "main"


def _get_limit_pct(code, name=""):
    """根据板块和ST标识返回涨跌停板幅度(%)"""
    board = _get_board(code)
    is_st = "ST" in (name or "")
    if board == "bse":
        return 30
    elif board in ("gem", "star"):
        return 20
    else:
        return 5 if is_st else 10


class StockTrendAnalyzer:
    """
    股票趋势分析器
    
    基于交易理念：
    1. 趋势判断 - MA5>MA10>MA20 多头排列
    2. 乖离率检测 - 不追高，偏离 MA5 超过 5% 不买
    3. 量能分析 - 偏好缩量回调
    4. MACD/RSI 指标分析
    """
    
    BIAS_THRESHOLD = 5.0  # 乖离率阈值
    VOLUME_SHRINK_RATIO = 0.7
    VOLUME_HEAVY_RATIO = 1.5
    MA_SUPPORT_TOLERANCE = 0.02
    
    MACD_FAST = 12
    MACD_SLOW = 20
    MACD_SIGNAL = 9
    
    RSI_SHORT = 6
    RSI_MID = 12
    RSI_LONG = 20
    RSI_OVERBOUGHT = 70
    RSI_OVERSOLD = 30
    
    def analyze(self, df: pd.DataFrame, code: str, name: str = "") -> TrendAnalysisResult:
        """
        分析股票趋势

        Args:
            df: 包含 OHLCV 数据的 DataFrame
            code: 股票代码
            name: 股票名称（用于识别ST股）

        Returns:
            TrendAnalysisResult 分析结果
        """
        result = TrendAnalysisResult(code=code)

        # 根据板块动态计算阈值
        self._limit_pct = _get_limit_pct(code, name)
        self._bias_threshold = self._limit_pct * 0.5
        self._spread_threshold = self._limit_pct * 0.5
        
        if df is None or df.empty or len(df) < 20:
            logger.warning(f"{_sanitize_for_log(code)} 数据不足，无法进行趋势分析")
            result.risk_factors.append("数据不足，无法完成分析")
            return result

        # 技术指标计算改用前复权 OHLC（消除除权除息导致的价格跳空）
        # close_raw 保留原始价，用于 current_price 展示真实成交价
        if 'close_fq' in df.columns:
            df = df.copy()
            df['close_raw'] = df['close']
            df['open_raw'] = df['open']
            df['high_raw'] = df['high']
            df['low_raw'] = df['low']
            df['close'] = df['close_fq']
            df['open'] = df['open_fq']
            df['high'] = df['high_fq']
            df['low'] = df['low_fq']
            logger.info(f"{_sanitize_for_log(code)} 技术指标计算使用前复权价格")
        else:
            logger.warning(f"{_sanitize_for_log(code)} 无前复权字段，技术指标退化为不复权价格")

        # 确保数据按日期排序
        df = df.sort_values('date').reset_index(drop=True)
        
        # 计算指标
        df = self._calculate_mas(df)
        df = self._calculate_macd(df)
        df = self._calculate_rsi(df)
        
        # 获取最新数据
        latest = df.iloc[-1]
        # current_price 用原始真实成交价（前复权价仅用于指标计算）
        result.current_price = float(latest['close_raw'] if 'close_raw' in df.columns else latest['close'])
        result.ma5 = float(latest['MA5'])
        result.ma10 = float(latest['MA10'])
        result.ma20 = float(latest['MA20'])
        result.ma60 = float(latest.get('MA60', 0))
        
        # 分析各项
        self._analyze_trend(df, result)
        self._calculate_bias(result)
        self._analyze_volume(df, result)
        self._analyze_support_resistance(df, result)
        self._analyze_macd(df, result)
        self._analyze_rsi(df, result)
        self._generate_signal(result)
        self._analyze_quantitative_enhancements(df, result)
        
        return result
    
    def _calculate_mas(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算均线"""
        df = df.copy()
        df['MA5'] = df['close'].rolling(window=5, min_periods=1).mean()
        df['MA10'] = df['close'].rolling(window=10, min_periods=1).mean()
        df['MA20'] = df['close'].rolling(window=20, min_periods=1).mean()
        if len(df) >= 20:
            df['MA60'] = df['close'].rolling(window=20, min_periods=1).mean()
        else:
            df['MA60'] = df['MA20']
        return df
    
    def _calculate_macd(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算 MACD 指标"""
        df = df.copy()
        
        ema_fast = df['close'].ewm(span=self.MACD_FAST, adjust=False).mean()
        ema_slow = df['close'].ewm(span=self.MACD_SLOW, adjust=False).mean()
        
        df['MACD_DIF'] = ema_fast - ema_slow
        df['MACD_DEA'] = df['MACD_DIF'].ewm(span=self.MACD_SIGNAL, adjust=False).mean()
        df['MACD_BAR'] = (df['MACD_DIF'] - df['MACD_DEA']) * 2
        
        return df
    
    def _calculate_rsi(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算 RSI 指标"""
        df = df.copy()
        
        for period in [self.RSI_SHORT, self.RSI_MID, self.RSI_LONG]:
            delta = df['close'].diff()
            gain = delta.where(delta > 0, 0)
            loss = -delta.where(delta < 0, 0)
            
            avg_gain = gain.rolling(window=period, min_periods=1).mean()
            avg_loss = loss.rolling(window=period, min_periods=1).mean()
            
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            
            df[f'RSI_{period}'] = rsi.fillna(50)
        
        return df
    
    def _analyze_trend(self, df: pd.DataFrame, result: TrendAnalysisResult) -> None:
        """分析趋势状态"""
        ma5, ma10, ma20 = result.ma5, result.ma10, result.ma20
        
        if ma5 > ma10 > ma20:
            # 检查趋势强度
            if len(df) >= 5:
                prev = df.iloc[-5]
                prev_spread = (prev['MA5'] - prev['MA20']) / prev['MA20'] * 100 if prev['MA20'] > 0 else 0
                curr_spread = (ma5 - ma20) / ma20 * 100 if ma20 > 0 else 0
                
                if curr_spread > prev_spread and curr_spread > self._spread_threshold:
                    result.trend_status = TrendStatus.STRONG_BULL
                    result.ma_alignment = "强势多头排列，均线发散上行"
                    result.trend_strength = 90
                else:
                    result.trend_status = TrendStatus.BULL
                    result.ma_alignment = "多头排列 MA5>MA10>MA20"
                    result.trend_strength = 75
            else:
                result.trend_status = TrendStatus.BULL
                result.ma_alignment = "多头排列 MA5>MA10>MA20"
                result.trend_strength = 75
                
        elif ma5 > ma10 and ma10 <= ma20:
            result.trend_status = TrendStatus.WEAK_BULL
            result.ma_alignment = "弱势多头，MA5>MA10 但 MA10≤MA20"
            result.trend_strength = 55
            
        elif ma5 < ma10 < ma20:
            if len(df) >= 5:
                prev = df.iloc[-5]
                prev_spread = (prev['MA20'] - prev['MA5']) / prev['MA5'] * 100 if prev['MA5'] > 0 else 0
                curr_spread = (ma20 - ma5) / ma5 * 100 if ma5 > 0 else 0
                
                if curr_spread > prev_spread and curr_spread > self._spread_threshold:
                    result.trend_status = TrendStatus.STRONG_BEAR
                    result.ma_alignment = "强势空头排列，均线发散下行"
                    result.trend_strength = 10
                else:
                    result.trend_status = TrendStatus.BEAR
                    result.ma_alignment = "空头排列 MA5<MA10<MA20"
                    result.trend_strength = 25
            else:
                result.trend_status = TrendStatus.BEAR
                result.ma_alignment = "空头排列 MA5<MA10<MA20"
                result.trend_strength = 25
                
        elif ma5 < ma10 and ma10 >= ma20:
            result.trend_status = TrendStatus.WEAK_BEAR
            result.ma_alignment = "弱势空头，MA5<MA10 但 MA10≥MA20"
            result.trend_strength = 40
            
        else:
            result.trend_status = TrendStatus.CONSOLIDATION
            result.ma_alignment = "均线缠绕，趋势不明"
            result.trend_strength = 50
    
    def _calculate_bias(self, result: TrendAnalysisResult) -> None:
        """计算乖离率"""
        price = result.current_price
        
        if result.ma5 > 0:
            result.bias_ma5 = (price - result.ma5) / result.ma5 * 100
        if result.ma10 > 0:
            result.bias_ma10 = (price - result.ma10) / result.ma10 * 100
        if result.ma20 > 0:
            result.bias_ma20 = (price - result.ma20) / result.ma20 * 100
    
    def _analyze_volume(self, df: pd.DataFrame, result: TrendAnalysisResult) -> None:
        """分析量能"""
        if len(df) < 5:
            return
        
        latest = df.iloc[-1]
        vol_5d_avg = df['volume'].iloc[-6:-1].mean()
        
        if vol_5d_avg > 0:
            result.volume_ratio_5d = float(latest['volume']) / vol_5d_avg
        
        # 判断价格变化
        if len(df) >= 2:
            prev_close = df.iloc[-2]['close']
            price_change = (latest['close'] - prev_close) / prev_close * 100
            
            # 量能状态判断
            if result.volume_ratio_5d >= self.VOLUME_HEAVY_RATIO:
                if price_change > 0:
                    result.volume_status = VolumeStatus.HEAVY_VOLUME_UP
                    result.volume_trend = "放量上涨，多头力量强劲"
                else:
                    result.volume_status = VolumeStatus.HEAVY_VOLUME_DOWN
                    result.volume_trend = "放量下跌，注意风险"
            elif result.volume_ratio_5d <= self.VOLUME_SHRINK_RATIO:
                if price_change > 0:
                    result.volume_status = VolumeStatus.SHRINK_VOLUME_UP
                    result.volume_trend = "缩量上涨，上攻动能不足"
                else:
                    result.volume_status = VolumeStatus.SHRINK_VOLUME_DOWN
                    result.volume_trend = "缩量回调，洗盘特征明显"
            else:
                result.volume_status = VolumeStatus.NORMAL
                result.volume_trend = "量能正常"
    
    def _analyze_support_resistance(self, df: pd.DataFrame, result: TrendAnalysisResult) -> None:
        """分析支撑压力位"""
        price = result.current_price
        
        # 检查 MA5 支撑
        if result.ma5 > 0:
            ma5_distance = abs(price - result.ma5) / result.ma5
            if ma5_distance <= self.MA_SUPPORT_TOLERANCE and price >= result.ma5:
                result.support_ma5 = True
                result.support_levels.append(result.ma5)
        
        # 检查 MA10 支撑
        if result.ma10 > 0:
            ma10_distance = abs(price - result.ma10) / result.ma10
            if ma10_distance <= self.MA_SUPPORT_TOLERANCE and price >= result.ma10:
                result.support_ma10 = True
                if result.ma10 not in result.support_levels:
                    result.support_levels.append(result.ma10)
        
        # MA20 作为重要支撑
        if result.ma20 > 0 and price >= result.ma20:
            result.support_levels.append(result.ma20)
        
        # 近期高点作为压力
        if len(df) >= 20:
            recent_high = df['high'].iloc[-20:].max()
            if recent_high > price:
                result.resistance_levels.append(recent_high)
    
    def _analyze_macd(self, df: pd.DataFrame, result: TrendAnalysisResult) -> None:
        """分析 MACD 指标"""
        if len(df) < self.MACD_SLOW:
            result.macd_signal = "数据不足"
            return
        
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        result.macd_dif = float(latest['MACD_DIF'])
        result.macd_dea = float(latest['MACD_DEA'])
        result.macd_bar = float(latest['MACD_BAR'])
        
        # 判断金叉死叉
        prev_dif_dea = prev['MACD_DIF'] - prev['MACD_DEA']
        curr_dif_dea = result.macd_dif - result.macd_dea
        
        is_golden_cross = prev_dif_dea <= 0 and curr_dif_dea > 0
        is_death_cross = prev_dif_dea >= 0 and curr_dif_dea < 0
        is_crossing_up = prev['MACD_DIF'] <= 0 and result.macd_dif > 0
        is_crossing_down = prev['MACD_DIF'] >= 0 and result.macd_dif < 0
        
        if is_golden_cross and result.macd_dif > 0:
            result.macd_status = MACDStatus.GOLDEN_CROSS_ZERO
            result.macd_signal = "⭐ 零轴上金叉，强烈看多信号！"
        elif is_crossing_up:
            result.macd_status = MACDStatus.CROSSING_UP
            result.macd_signal = "⚡ DIF上穿零轴，趋势转强"
        elif is_golden_cross:
            result.macd_status = MACDStatus.GOLDEN_CROSS
            result.macd_signal = "✅ 金叉，趋势向上"
        elif is_death_cross:
            result.macd_status = MACDStatus.DEATH_CROSS
            result.macd_signal = "❌ 死叉，趋势向下"
        elif is_crossing_down:
            result.macd_status = MACDStatus.CROSSING_DOWN
            result.macd_signal = "⚠️ DIF下穿零轴，趋势转弱"
        elif result.macd_dif > 0 and result.macd_dea > 0:
            result.macd_status = MACDStatus.BULLISH
            result.macd_signal = "✓ 多头排列，持续上涨"
        elif result.macd_dif < 0 and result.macd_dea < 0:
            result.macd_status = MACDStatus.BEARISH
            result.macd_signal = "⚠ 空头排列，持续下跌"
        else:
            result.macd_status = MACDStatus.BULLISH
            result.macd_signal = "MACD 中性区域"
    
    def _analyze_rsi(self, df: pd.DataFrame, result: TrendAnalysisResult) -> None:
        """分析 RSI 指标"""
        if len(df) < self.RSI_LONG:
            result.rsi_signal = "数据不足"
            return
        
        latest = df.iloc[-1]
        
        result.rsi_6 = float(latest[f'RSI_{self.RSI_SHORT}'])
        result.rsi_12 = float(latest[f'RSI_{self.RSI_MID}'])
        result.rsi_20 = float(latest[f'RSI_{self.RSI_LONG}'])
        
        rsi_mid = result.rsi_12
        
        if rsi_mid > self.RSI_OVERBOUGHT:
            result.rsi_status = RSIStatus.OVERBOUGHT
            result.rsi_signal = f"⚠️ RSI超买({rsi_mid:.1f}>70)，短期回调风险高"
        elif rsi_mid > 60:
            result.rsi_status = RSIStatus.STRONG_BUY
            result.rsi_signal = f"✅ RSI强势({rsi_mid:.1f})，多头力量充足"
        elif rsi_mid >= 40:
            result.rsi_status = RSIStatus.NEUTRAL
            result.rsi_signal = f"RSI中性({rsi_mid:.1f})，震荡整理中"
        elif rsi_mid >= self.RSI_OVERSOLD:
            result.rsi_status = RSIStatus.WEAK
            result.rsi_signal = f"⚡ RSI弱势({rsi_mid:.1f})，关注反弹"
        else:
            result.rsi_status = RSIStatus.OVERSOLD
            result.rsi_signal = f"⭐ RSI超卖({rsi_mid:.1f}<30)，反弹机会大"
    
    def _generate_signal(self, result: TrendAnalysisResult) -> None:
        """生成买入信号和综合评分"""
        score = 0
        reasons = []
        risks = []
        
        # 趋势评分（30分）
        trend_scores = {
            TrendStatus.STRONG_BULL: 30,
            TrendStatus.BULL: 26,
            TrendStatus.WEAK_BULL: 18,
            TrendStatus.CONSOLIDATION: 12,
            TrendStatus.WEAK_BEAR: 8,
            TrendStatus.BEAR: 4,
            TrendStatus.STRONG_BEAR: 0,
        }
        trend_score = trend_scores.get(result.trend_status, 12)
        score += trend_score
        
        if result.trend_status in [TrendStatus.STRONG_BULL, TrendStatus.BULL]:
            reasons.append(f"✅ {result.trend_status.value}，顺势做多")
        elif result.trend_status in [TrendStatus.BEAR, TrendStatus.STRONG_BEAR]:
            risks.append(f"⚠️ {result.trend_status.value}，不宜做多")
        
        # 乖离率评分（20分）
        bias = result.bias_ma5
        if bias < 0:
            if bias > -self._limit_pct * 0.3:
                score += 20
                reasons.append(f"✅ 价格略低于MA5({bias:.1f}%)，回踩买点")
            elif bias > -self._limit_pct * 0.5:
                score += 16
                reasons.append(f"✅ 价格回踩MA5({bias:.1f}%)，观察支撑")
            else:
                score += 8
                risks.append(f"⚠️ 乖离率过大({bias:.1f}%)，可能破位")
        elif bias < self._limit_pct * 0.2:
            score += 18
            reasons.append(f"✅ 价格贴近MA5({bias:.1f}%)，介入好时机")
        elif bias < self._bias_threshold:
            score += 14
            reasons.append(f"⚡ 价格略高于MA5({bias:.1f}%)，可小仓介入")
        else:
            score += 4
            risks.append(f"❌ 乖离率过高({bias:.1f}%>{self._bias_threshold:.0f}%)，严禁追高！")
        
        # 量能评分（15分）
        volume_scores = {
            VolumeStatus.SHRINK_VOLUME_DOWN: 15,
            VolumeStatus.HEAVY_VOLUME_UP: 12,
            VolumeStatus.NORMAL: 10,
            VolumeStatus.SHRINK_VOLUME_UP: 6,
            VolumeStatus.HEAVY_VOLUME_DOWN: 0,
        }
        vol_score = volume_scores.get(result.volume_status, 8)
        score += vol_score
        
        if result.volume_status == VolumeStatus.SHRINK_VOLUME_DOWN:
            reasons.append("✅ 缩量回调，主力洗盘")
        elif result.volume_status == VolumeStatus.HEAVY_VOLUME_DOWN:
            risks.append("⚠️ 放量下跌，注意风险")
        
        # 支撑评分（10分）
        if result.support_ma5:
            score += 5
            reasons.append("✅ MA5支撑有效")
        if result.support_ma10:
            score += 5
            reasons.append("✅ MA10支撑有效")
        
        # MACD 评分（15分）
        macd_scores = {
            MACDStatus.GOLDEN_CROSS_ZERO: 15,
            MACDStatus.GOLDEN_CROSS: 12,
            MACDStatus.CROSSING_UP: 10,
            MACDStatus.BULLISH: 8,
            MACDStatus.BEARISH: 2,
            MACDStatus.CROSSING_DOWN: 0,
            MACDStatus.DEATH_CROSS: 0,
        }
        macd_score = macd_scores.get(result.macd_status, 5)
        score += macd_score
        
        if result.macd_status in [MACDStatus.GOLDEN_CROSS_ZERO, MACDStatus.GOLDEN_CROSS]:
            reasons.append(f"✅ {result.macd_signal}")
        elif result.macd_status in [MACDStatus.DEATH_CROSS, MACDStatus.CROSSING_DOWN]:
            risks.append(f"⚠️ {result.macd_signal}")
        else:
            reasons.append(result.macd_signal)
        
        # RSI 评分（10分）
        rsi_scores = {
            RSIStatus.OVERSOLD: 10,
            RSIStatus.STRONG_BUY: 8,
            RSIStatus.NEUTRAL: 5,
            RSIStatus.WEAK: 3,
            RSIStatus.OVERBOUGHT: 0,
        }
        rsi_score = rsi_scores.get(result.rsi_status, 5)
        score += rsi_score
        
        if result.rsi_status in [RSIStatus.OVERSOLD, RSIStatus.STRONG_BUY]:
            reasons.append(f"✅ {result.rsi_signal}")
        elif result.rsi_status == RSIStatus.OVERBOUGHT:
            risks.append(f"⚠️ {result.rsi_signal}")
        else:
            reasons.append(result.rsi_signal)
        
        # 综合判断
        result.signal_score = score
        result.signal_reasons = reasons
        result.risk_factors = risks
        
        if score >= 75 and result.trend_status in [TrendStatus.STRONG_BULL, TrendStatus.BULL]:
            result.buy_signal = BuySignal.STRONG_BUY
        elif score >= 60 and result.trend_status in [TrendStatus.STRONG_BULL, TrendStatus.BULL, TrendStatus.WEAK_BULL]:
            result.buy_signal = BuySignal.BUY
        elif score >= 45:
            result.buy_signal = BuySignal.HOLD
        elif score >= 30:
            result.buy_signal = BuySignal.WAIT
        elif result.trend_status in [TrendStatus.BEAR, TrendStatus.STRONG_BEAR]:
            result.buy_signal = BuySignal.STRONG_SELL
        else:
            result.buy_signal = BuySignal.SELL

    def _analyze_quantitative_enhancements(self, df: pd.DataFrame, result: TrendAnalysisResult) -> None:
        """量化增强指标计算"""

        # 1. 连续上涨天数
        if len(df) >= 2:
            count = 0
            for i in range(len(df) - 1, 0, -1):
                if df.iloc[i]['close'] > df.iloc[i - 1]['close']:
                    count += 1
                else:
                    break
            result.consecutive_up_days = count

        # 2. 近5日/10日累计涨幅
        if len(df) >= 6:
            result.recent_5d_gain_pct = (df.iloc[-1]['close'] - df.iloc[-6]['close']) / df.iloc[-6]['close'] * 100
        if len(df) >= 11:
            result.recent_10d_gain_pct = (df.iloc[-1]['close'] - df.iloc[-11]['close']) / df.iloc[-11]['close'] * 100

        # 3. 均线收敛度（MA5/MA10/MA20 的变异系数）
        def _calc_cv(row):
            vals = [row['MA5'], row['MA10'], row['MA20']]
            mean_v = sum(vals) / 3
            if mean_v <= 0:
                return 0.0
            return float(np.std(vals) / mean_v)

        result.ma_convergence = _calc_cv(df.iloc[-1])
        if len(df) >= 6:
            result.prev_ma_convergence = _calc_cv(df.iloc[-6])

        # 4. 价格阶段判断
        if result.trend_status in [TrendStatus.BEAR, TrendStatus.STRONG_BEAR]:
            result.price_phase = "下跌趋势"
        elif (result.ma_convergence < 0.02
              and result.consecutive_up_days <= 3
              and result.recent_10d_gain_pct < self._limit_pct * 0.5):
            result.price_phase = "蓄势"
        elif result.prev_ma_convergence < 0.02 and result.ma_convergence >= 0.02:
            result.price_phase = "发散启动"
        elif result.trend_status in [TrendStatus.BULL, TrendStatus.STRONG_BULL] and result.ma_convergence >= 0.02:
            result.price_phase = "趋势上行"
        else:
            if len(df) >= 5:
                high_5d = df['high'].iloc[-5:].max()
                low_5d = df['low'].iloc[-5:].min()
                close_start = df['close'].iloc[-5]
                close_end = df['close'].iloc[-1]
                volatility = (high_5d - low_5d) / low_5d * 100 if low_5d > 0 else 0
                close_change = abs(close_end - close_start) / close_start * 100 if close_start > 0 else 0
                if volatility > self._limit_pct * 0.5 and close_change < self._limit_pct * 0.2:
                    result.price_phase = "高位震荡"
                else:
                    result.price_phase = "盘整"
            else:
                result.price_phase = "盘整"

        # 5. RSI 超买分类
        if result.rsi_12 <= 70:
            result.rsi_overbuy_type = "非超买"
            result.rsi_risk_level = "无"
        elif result.recent_5d_gain_pct > 8:
            result.rsi_overbuy_type = "暴涨型"
            result.rsi_risk_level = "高风险"
        elif result.consecutive_up_days >= 5 and result.recent_5d_gain_pct > 0:
            avg_daily = result.recent_5d_gain_pct / result.consecutive_up_days
            if avg_daily < 1.5:
                result.rsi_overbuy_type = "连续小阳型"
                result.rsi_risk_level = "低风险"
            else:
                result.rsi_overbuy_type = "温和超买"
                result.rsi_risk_level = "中风险"
        else:
            result.rsi_overbuy_type = "温和超买"
            result.rsi_risk_level = "中风险"

        # 6. 突破信号
        if len(df) >= 20:
            recent = df.iloc[-20:]
            high_idx = recent['high'].idxmax()
            result.prev_high = float(recent.loc[high_idx, 'high'])
            result.prev_high_date = str(recent.loc[high_idx, 'date'])[:10]
            # 近 5 日最高（用于 ai_analyzer 的第一压力位 + 量价规则）
            result.recent_5d_high = float(df['high'].iloc[-5:].max())
            # 当日涨跌幅（用于 ai_analyzer 的量价规则）
            latest_row = df.iloc[-1]
            result.latest_pct_chg = float(latest_row['pct_chg']) if 'pct_chg' in latest_row and latest_row['pct_chg'] == latest_row['pct_chg'] else 0.0
            if result.prev_high > 0:
                # 正值=当前价低于前高（距前高还有多远），负值=已突破前高
                result.near_high_pct = (result.prev_high - result.current_price) / result.prev_high * 100
            if result.near_high_pct <= 0:
                result.breakout_signal = "突破前高"
            elif result.near_high_pct <= 3:
                result.breakout_signal = "接近前高"
            else:
                result.breakout_signal = "远离前高"

        # 7. 均线支撑统计
        if len(df) >= 20:
            recent = df.iloc[-20:]
            support_events = 0
            support_success = 0
            for i in range(1, len(recent)):
                close_i = recent.iloc[i]['close']
                ma5_i = recent.iloc[i]['MA5']
                ma10_i = recent.iloc[i]['MA10']
                near_ma5 = ma5_i > 0 and abs(close_i - ma5_i) / ma5_i <= 0.02
                near_ma10 = ma10_i > 0 and abs(close_i - ma10_i) / ma10_i <= 0.02
                if near_ma5 or near_ma10:
                    support_events += 1
                    if i + 1 < len(recent):
                        if recent.iloc[i + 1]['close'] > close_i:
                            support_success += 1
            result.ma_support_count = support_events
            if support_events > 0:
                result.ma_support_success_rate = support_success / support_events


def analyze_stock(df: pd.DataFrame, code: str, name: str = "") -> TrendAnalysisResult:
    """便捷函数：分析单只股票"""
    analyzer = StockTrendAnalyzer()
    return analyzer.analyze(df, code, name)
