# -*- coding: utf-8 -*-
"""
数据获取模块 - 直接调用 common.py / query.py 函数获取 A 股日行情数据

鉴权说明：
    认证状态由 common.py 自动管理（读取 ~/.cxda-cache/.shared/cxda_auth.json，跨 agent 共享）。
    若未认证，需先由 Agent 引导用户完成 auth.py 鉴权流程。

性能优化：
    原版通过 subprocess 调用 query.py（每次启动新 Python 进程，重复导入模块），
    本版改为直接 import common.py / query.py 的函数，消除 subprocess 开销。
    analyze_stock() 一次执行从 6 次 subprocess 降为 0，节省约 3-6 秒。
"""

import json
import logging
import re
import sys
from pathlib import Path
from typing import Optional, Dict, Tuple

import pandas as pd

logger = logging.getLogger(__name__)

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

# 直接导入 common.py 和 query.py 的函数（不再走 subprocess）
from common import (
    BASE_URL,
    HEADERS,
    PROXIES,
    REQUEST_CHANNEL,
    ensure_token,
    http_get,
    check_terms_accepted,
    get_user_key,
    get_platform_show_billing_info,
)
import query as _query_mod


# ── 输入净化 ──────────────────────────────────────────────────────────

_CONTROL_RE = re.compile(r"[\r\n\t\x00-\x1f\x7f]")


def _sanitize_for_log(value) -> str:
    """净化日志输出，剥离换行等控制字符"""
    if value is None:
        return ""
    return _CONTROL_RE.sub(" ", str(value))


# ── 股票代码校验 ──────────────────────────────────────────────────────

def normalize_code(stock_code: str) -> Tuple[Optional[str], str]:
    """
    规范化股票代码，返回 (market, code)。
    market: 'a' / 'b' / 'hk' / 'us' / None（非法）
    """
    if not stock_code or not isinstance(stock_code, str):
        return None, ""
    code = stock_code.strip().upper()
    if not code:
        return None, ""

    # A 股：6 位纯数字（000/001/002/003/300/301/600/601/603/605/688/689/920）
    # B 股：900（上交所）/ 200（深交所）
    if re.match(r'^\d{6}$', code):
        if code.startswith(('900', '200')):
            return 'b', code
        return 'a', code

    # 港股：HK + 数字 或 5 位数字
    if code.startswith('HK'):
        num = code[2:]
        if num.isdigit():
            return 'hk', num.zfill(5)
    if re.match(r'^\d{4,5}$', code):
        return 'hk', code.zfill(5)

    # 美股：字母代码
    if re.match(r'^[A-Z]{1,5}$', code):
        return 'us', code

    return None, code


# ── 接口调用（直接函数调用，不再走 subprocess）─────────────────────────

# 进程内分页大小缓存
_LOCAL_PAGE_SIZE_CACHE: Dict[str, int] = {}


def _normalize_max_page_size(value) -> Optional[int]:
    """将 maxPageSize 转成正整数"""
    if value is None or isinstance(value, bool):
        return None
    try:
        text = str(value).strip()
        if text == "":
            return None
        number = int(float(text))
        return number if number > 0 else None
    except (ValueError, TypeError):
        return None


def _get_api_max_page_size(api_id: str, params: dict = None) -> int:
    """直接调用 query.py 的函数获取接口最大分页（不再 subprocess）"""
    cache_key = "{}:{}".format(api_id, json.dumps(params or {}, sort_keys=True))
    if cache_key in _LOCAL_PAGE_SIZE_CACHE:
        return _LOCAL_PAGE_SIZE_CACHE[cache_key]

    token = ensure_token()
    session_id = _query_mod._get_or_create_session_id() if hasattr(_query_mod, '_get_or_create_session_id') else None
    max_page_size = _query_mod._get_api_max_page_size(api_id, params or {}, session_id, token)
    if max_page_size is None:
        raise RuntimeError("查询接口最大分页失败")

    _LOCAL_PAGE_SIZE_CACHE[cache_key] = max_page_size
    return max_page_size


def _call_api_direct(api_id: str, params: dict) -> Optional[Dict]:
    """直接调用 query.py 的 run_api 函数完成 API 查询（不再 subprocess）。

    股票分析只调2次API，无并发锁竞争问题，保留 show_billing_info=True 确保积分记账。
    """
    _query_mod._validate_api_id(api_id)

    accepted, error_response = check_terms_accepted()
    if not accepted:
        logger.error("服务协议未接受")
        return None

    try:
        token = ensure_token()
        show_billing = get_platform_show_billing_info()
        result = _query_mod.run_api(
            api_id,
            params,
            token=token,
            include_summary=show_billing,
            show_billing_info=show_billing,
        )
        return result
    except Exception as e:
        logger.error(f"API 调用失败 [{api_id}]: {_sanitize_for_log(str(e))}")
        return None


def _fetch_daily_quote(code: str, page: int, page_size: int) -> Optional[Dict]:
    """获取原始不复权日行情（getStkDayQuoByCond-G）"""
    data = _call_api_direct("getStkDayQuoByCond-G", {
        "stkCode": code,
        "pageNum": str(page),
        "pageSize": str(page_size),
    })
    if data is None:
        return None
    if data.get('code') == '10000':
        return data
    logger.error(f"API 返回错误: {_sanitize_for_log(data.get('msg', 'unknown'))}")
    return None


def _fetch_fq_quote(code: str, page: int, page_size: int) -> Optional[Dict]:
    """获取前复权日行情（getDStkPriceMidDivByCond-G），仅 OHLC + 均价"""
    data = _call_api_direct("getDStkPriceMidDivByCond-G", {
        "stkCode": code,
        "pageNum": str(page),
        "pageSize": str(page_size),
    })
    if data is None:
        return None
    if data.get('code') == '10000':
        return data
    logger.error(f"API 返回错误: {_sanitize_for_log(data.get('msg', 'unknown'))}")
    return None


# ── 涨停价计算 ────────────────────────────────────────────────────────

def _get_limit_pct(code: str, name: str) -> float:
    """获取涨跌幅限制（%）：ST 5%，创业板/科创板 20%，其余 10%"""
    is_st = bool(name and ('ST' in name.upper() or '*ST' in name.upper()))
    if is_st:
        return 5.0

    board = None
    if code.startswith(('300', '301')):
        board = 'gem'
    elif code.startswith('688'):
        board = 'star'
    elif code.startswith(('600', '601', '603', '605')):
        board = 'sh_main'
    elif code.startswith(('000', '001', '002', '003')):
        board = 'sz_main'

    if board in ('gem', 'star'):
        return 20.0
    else:
        return 10.0


def is_b_share(code: str) -> bool:
    """B 股识别：上交所 900 开头、深交所 200 开头"""
    return code.startswith(('900', '200'))


# ── 主函数 ────────────────────────────────────────────────────────────

def get_daily_data(stock_code: str, days: int = 20) -> Optional[Tuple[pd.DataFrame, str]]:
    """
    获取股票日线数据（原始不复权 + 前复权 OHLC）

    数据用途分工：
      - 原始不复权（open/high/low/close/volume/amount/pct_chg/pre_close）→ 用于报告展示
      - 前复权（open_fq/high_fq/low_fq/close_fq）→ 用于技术指标计算（均线/MACD/RSI/BIAS）

    Returns:
        (DataFrame, 股票名称) 元组，失败返回 None。
    """
    market, code = normalize_code(stock_code)
    safe_stock_code = _sanitize_for_log(stock_code)
    if market is None:
        logger.warning(f"非法股票代码格式：{safe_stock_code}")
        return None
    if market != 'a':
        logger.warning(f"仅支持 A 股，{safe_stock_code} 为 {_sanitize_for_log(market)} 市场代码")
        return None

    # 动态查询接口最大分页（直接函数调用）
    try:
        daily_page_size = _get_api_max_page_size("getStkDayQuoByCond-G", {"stkCode": code})
        fq_page_size = _get_api_max_page_size("getDStkPriceMidDivByCond-G", {"stkCode": code})
    except Exception as e:
        logger.error(f"动态获取分页上限失败：{_sanitize_for_log(str(e))}")
        return None

    # 多页拼接（不复权）
    pages_needed = max(1, (days + daily_page_size - 1) // daily_page_size)
    all_results = []

    for page in range(1, pages_needed + 1):
        data = _fetch_daily_quote(code, page, daily_page_size)
        if not data:
            break
        results = data.get('result', [])
        if not results:
            break
        all_results.extend(results)
        if len(results) < daily_page_size:
            break

    if not all_results:
        logger.warning(f"{safe_stock_code} 无日行情数据")
        return None

    # 股票名称
    all_results.sort(key=lambda x: x.get('TRADE_DATE', ''), reverse=True)
    name = all_results[0].get('STK_SHORT_NAME', stock_code)

    # 去重
    seen = set()
    unique = []
    for r in all_results:
        dt = r.get('TRADE_DATE', '')
        if dt not in seen:
            seen.add(dt)
            unique.append(r)

    df = pd.DataFrame(unique)

    column_mapping = {
        'TRADE_DATE': 'date',
        'OPEN_PRICE': 'open',
        'CLOSE_PRICE': 'close',
        'HIGH_PRICE': 'high',
        'LOW_PRICE': 'low',
        'TRADE_VOL': 'volume',
        'TRADE_AMUT': 'amount',
        'PRICE_LIMIT': 'pct_chg',
        'PRE_CLOSE_PRICE': 'pre_close',
    }

    df = df.rename(columns=column_mapping)
    df['date'] = pd.to_datetime(df['date'])

    for col in ['open', 'high', 'low', 'close', 'volume', 'amount', 'pct_chg', 'pre_close']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # 拉取前复权数据（getDStkPriceMidDivByCond-G），按 date 对齐合并到 df
    fq_pages_needed = max(1, (days + fq_page_size - 1) // fq_page_size)
    fq_results = []
    for page in range(1, fq_pages_needed + 1):
        fq_data = _fetch_fq_quote(code, page, fq_page_size)
        if not fq_data:
            break
        results = fq_data.get('result', [])
        if not results:
            break
        fq_results.extend(results)
        if len(results) < fq_page_size:
            break

    if fq_results:
        fq_df = pd.DataFrame(fq_results)
        fq_column_mapping = {
            'END_DATE': 'date',
            'OPEN_PRICE_BRE': 'open_fq',
            'CLOSE_PRICE_BRE': 'close_fq',
            'HIGH_PRICE_BRE': 'high_fq',
            'LOW_PRICE_BRE': 'low_fq',
        }
        fq_df = fq_df.rename(columns=fq_column_mapping)
        if 'date' in fq_df.columns:
            fq_df['date'] = pd.to_datetime(fq_df['date'])
            for col in ['open_fq', 'high_fq', 'low_fq', 'close_fq']:
                if col in fq_df.columns:
                    fq_df[col] = pd.to_numeric(fq_df[col], errors='coerce')
            # 按 date 去重，保留最新
            fq_df = fq_df.drop_duplicates(subset=['date'], keep='first')
            # 合并到主 df
            df = df.merge(fq_df[['date', 'open_fq', 'high_fq', 'low_fq', 'close_fq']],
                          on='date', how='left')
            logger.info(f"{safe_stock_code} 已合并前复权 OHLC，用于技术指标计算")
    else:
        logger.warning(f"{safe_stock_code} 前复权数据获取失败，技术指标将使用不复权数据")

    # 前复权缺失时退化用不复权
    for col_fq, col_raw in [('open_fq', 'open'), ('high_fq', 'high'), ('low_fq', 'low'), ('close_fq', 'close')]:
        if col_fq not in df.columns:
            df[col_fq] = df[col_raw]

    # 按日期降序（最新在前）
    df = df.sort_values('date', ascending=False).reset_index(drop=True)

    # 只取需要的天数
    df = df.head(days)

    # 截断后恢复升序（最旧在前，最新在后），确保 iloc[-1] 取到最新行情
    df = df.sort_values('date').reset_index(drop=True)

    return df, name
