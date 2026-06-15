# -*- coding: utf-8 -*-
"""
数据获取模块 - 直接通过 HTTP 请求获取 A 股日行情数据
"""

import base64
import gzip
import json
import logging
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Tuple

import pandas as pd
import requests

logger = logging.getLogger(__name__)

# .env 路径（密钥配置文件）
_ENV_PATH = Path(__file__).parent.parent.parent / 'stock-market-information' / 'scripts' / '.env'

_TOKEN_VALID_SECONDS = 60
_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def _load_env() -> Dict[str, str]:
    env = {}
    if _ENV_PATH.exists():
        for line in _ENV_PATH.read_text(encoding='utf-8').splitlines():
            if '=' in line and not line.strip().startswith('#'):
                k, v = line.split('=', 1)
                env[k.strip()] = v.strip()
    return env


def _save_env(env: Dict[str, str]):
    lines = []
    if _ENV_PATH.exists():
        for line in _ENV_PATH.read_text(encoding='utf-8').splitlines():
            if not any(line.strip().startswith(k) for k in ['AUTH_TOKEN', '# === Token']):
                lines.append(line)
    lines.extend([
        '',
        '# === Token缓存（自动管理，请勿手动修改）===',
        f'AUTH_TOKEN={env.get("AUTH_TOKEN", "")}',
        f'AUTH_TOKEN_EXPIRE={env.get("AUTH_TOKEN_EXPIRE", "")}',
    ])
    _ENV_PATH.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def _get_token(base_url: str, user_key: str) -> Optional[str]:
    """获取有效 token（优先缓存，过期自动刷新）"""
    env = _load_env()
    cached_token = env.get('AUTH_TOKEN')
    try:
        expire = datetime.strptime(env.get('AUTH_TOKEN_EXPIRE', ''), '%Y-%m-%d %H:%M:%S')
        if cached_token and expire > datetime.now():
            return cached_token
    except (ValueError, TypeError):
        pass

    # 刷新 token
    resp = requests.get(
        f"{base_url}/webservice/foreign_getAuthtoken.htm",
        params={"userKey": user_key},
        headers=_HEADERS,
    )
    token = json.loads(resp.text).get("result")
    if token:
        env.update({
            'AUTH_TOKEN': token,
            'AUTH_TOKEN_EXPIRE': (datetime.now() + timedelta(seconds=_TOKEN_VALID_SECONDS)).strftime('%Y-%m-%d %H:%M:%S'),
        })
        _save_env(env)
    return token


def _fetch_daily_quote(code: str, page: int, page_size: int = 20) -> Optional[Dict]:
    """获取日行情数据（只调用 getStkDayQuoByCond-G）"""
    config = _load_env()
    base_url = os.environ.get('BASE_URL', '').rstrip('/') or config.get('BASE_URL', '').rstrip('/')
    user_key = os.environ.get('CXDA_USER_KEY') or config.get('CXDA_USER_KEY')

    if not base_url or not user_key:
        logger.error("未在 .env 或环境变量中找到 BASE_URL 或 CXDA_USER_KEY")
        return None

    token = _get_token(base_url, user_key)
    if not token:
        logger.error("获取 authToken 失败")
        return None

    params = {
        "authtoken": token,
        "stkCode": code,
        "pageNum": str(page),
        "pageSize": str(page_size),
    }

    resp = requests.get(
        f"{base_url}/webservice/cxdata/getStkDayQuoByCond-G.htm",
        params=params,
        headers=_HEADERS,
    )
    data = json.loads(gzip.decompress(base64.b64decode(resp.text.strip())).decode('utf-8'))

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
