# -*- coding: utf-8 -*-
"""
数据获取模块 - 通过 query.py 统一 CLI 调用获取 A 股日行情数据

鉴权说明：
    认证状态由 query.py/auth.py 自动管理（读取 ~/.cxda-cache/.shared/cxda_auth.json，跨 agent 共享）。
    若未认证，需先由 Agent 引导用户完成 auth.py 鉴权流程。
"""

import json
import logging
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional, Dict, Tuple

import pandas as pd

logger = logging.getLogger(__name__)

_SCRIPT_DIR = Path(__file__).resolve().parent
_QUERY_SCRIPT = _SCRIPT_DIR / "query.py"


def _run_query(code: str, page: int, page_size: int = 20) -> Optional[Dict]:
    """通过 subprocess 调用 query.py api，返回解析后的 dict。"""
    cmd = [
        sys.executable,
        str(_QUERY_SCRIPT),
        "api",
        "getStkDayQuoByCond-G",
        f"stkCode={code}",
        f"pageNum={page}",
        f"pageSize={page_size}",
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(_SCRIPT_DIR),
        )
    except subprocess.TimeoutExpired:
        logger.error("query.py 调用超时")
        return None

    if result.returncode != 0:
        logger.error(f"query.py 退出码 {result.returncode}, stderr: {result.stderr[:200]}")
        return None

    stdout = result.stdout.strip()
    if not stdout:
        logger.error("query.py 无输出")
        return None

    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as e:
        logger.error(f"query.py 响应解析失败: {e}")
        return None

    # 处理特殊状态
    status = data.get("status")
    if status == "confirmation_required":
        logger.warning("触发 50 次硬限制，需先执行 query.py session confirm")
        return None
    if status in ("failed", "terms_not_accepted"):
        logger.error(f"鉴权失败: {data.get('error', '未知错误')}")
        return None

    return data


def _fetch_daily_quote(code: str, page: int, page_size: int = 20) -> Optional[Dict]:
    """获取日行情数据（只调用 getStkDayQuoByCond-G）"""
    data = _run_query(code, page, page_size)
    if data is None:
        return None

    if data.get('code') == '10000':
        return data

    logger.error(f"API 返回错误: {data.get('msg', 'unknown')}")
    return None


def normalize_code(stock_code: str) -> tuple:
    code = stock_code.strip()
    if code.isdigit() and len(code) == 6:
        return 'a', code
    if re.match(r'^[A-Z]{1,5}(\.[A-Z])?$', code.upper()):
        return 'us', code.upper()
    if code.lower().startswith('hk'):
        numeric_part = code[2:]
        if numeric_part.isdigit():
            return 'hk', numeric_part.zfill(5)
    if code.isdigit() and len(code) == 5:
        return 'hk', code.zfill(5)
    return 'a', code


def get_daily_data(stock_code: str, days: int = 20) -> Optional[Tuple[pd.DataFrame, str]]:
    """
    获取股票日线数据

    Returns:
        (DataFrame, 股票名称) 元组，失败返回 None
    """
    market, code = normalize_code(stock_code)
    if market != 'a':
        logger.warning(f"仅支持 A 股，{stock_code} 为 {market} 市场代码")
        return None

    # 多页拼接
    pages_needed = max(1, (days + 19) // 20)
    all_results = []

    for page in range(1, pages_needed + 1):
        data = _fetch_daily_quote(code, page)
        if not data:
            break
        results = data.get('result', [])
        if not results:
            break
        all_results.extend(results)
        if len(results) < 20:
            break

    if not all_results:
        logger.warning(f"{stock_code} 无日行情数据")
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

    keep_cols = ['date', 'open', 'high', 'low', 'close', 'volume', 'amount', 'pct_chg', 'pre_close']
    df = df[[c for c in keep_cols if c in df.columns]]
    df = df.dropna(subset=['close', 'volume'])
    df = df.sort_values('date', ascending=True).reset_index(drop=True)

    if days and len(df) > days:
        df = df.tail(days).reset_index(drop=True)

    return df, name
