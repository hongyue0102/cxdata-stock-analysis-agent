# -*- coding: utf-8 -*-
"""
数据获取模块 - 调用内置的 stock-market-information skill 获取 A 股行情数据

通过调用同级的 stock-market-information skill 的 api_query.py 获取日行情数据。
"""

import json
import logging
import os
import subprocess
import sys
from typing import Optional, Dict, Tuple

import pandas as pd

logger = logging.getLogger(__name__)

# 内置的 stock-market-information skill 路径
_DEFAULT_SKILL_DIR = os.path.normpath(os.path.join(
    os.path.dirname(__file__), '..', '..', 'stock-market-information'
))
SKILL_DIR = os.environ.get('SKI_STOCK_MARKET_INFO_PATH', _DEFAULT_SKILL_DIR)

# api_query.py 路径
API_QUERY_SCRIPT = os.path.join(SKILL_DIR, 'scripts', 'api_query.py')

# .env 路径
_ENV_FILE = os.path.join(SKILL_DIR, 'scripts', '.env')


def _setup_key_interactively():
    """首次运行时交互式引导用户配置密钥，自动写入 .env"""
    print("未配置 CXDA_USER_KEY，首次使用需要设置密钥。")
    print("前往 https://yun.ccxe.com.cn/data/Skills 申请（推广期可免费试用）")
    print()
    try:
        user_key = input("请输入你的 CXDA_USER_KEY: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\n已取消。请手动在 skills/stock-market-information/scripts/.env 中配置密钥。")
        return False
    if not user_key:
        print("未输入密钥，退出。")
        return False
    with open(_ENV_FILE, "w", encoding="utf-8") as f:
        f.write("BASE_URL=http://cxapi.ccxe.com.cn/cxda\n")
        f.write(f"CXDA_USER_KEY={user_key}\n")
    print(f"✓ 密钥已保存到 {_ENV_FILE}，下次无需再配")
    print()
    return True


def _check_data_source() -> Optional[str]:
    """检查内置数据源 skill 是否可用，不可用则返回错误提示"""
    if not os.path.isfile(API_QUERY_SCRIPT):
        return (
            f"内置数据源脚本不存在: {API_QUERY_SCRIPT}\n"
            "请确认 skills/stock-market-information 目录完整。"
        )
    if not os.path.exists(_ENV_FILE):
        # 首次配置引导
        if not _setup_key_interactively():
            return (
                "请在 skills/stock-market-information/scripts/.env 中配置 CXDA_USER_KEY。\n"
                "密钥申请地址: https://yun.ccxe.com.cn/data/Skills （平台推广期，可免费试用）"
            )
    # 检查 .env 中是否真的有密钥
    with open(_ENV_FILE, encoding="utf-8") as f:
        content = f.read()
    if "your_user_key_here" in content or "CXDA_USER_KEY" not in content:
        if not _setup_key_interactively():
            return (
                "请在 skills/stock-market-information/scripts/.env 中配置 CXDA_USER_KEY。\n"
                "密钥申请地址: https://yun.ccxe.com.cn/data/Skills （平台推广期，可免费试用）"
            )
    return None


def _call_api(api_id: str, params: Dict[str, str]) -> Optional[Dict]:
    """
    调用内置 stock-market-information skill 的 api_query.py 获取数据

    Args:
        api_id: 接口标识
        params: 请求参数字典

    Returns:
        API 返回的 JSON 数据，失败返回 None
    """
    error = _check_data_source()
    if error:
        logger.error(error)
        return None

    # 构建命令行参数
    args = [sys.executable, API_QUERY_SCRIPT, api_id]
    for k, v in params.items():
        args.append(f"{k}={v}")

    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=os.path.join(SKILL_DIR, 'scripts'),
        )

        if result.returncode != 0:
            logger.error(f"api_query.py 执行失败: {result.stderr.strip()}")
            return None

        output = result.stdout.strip()
        if not output:
            logger.error("api_query.py 无输出")
            return None

        data = json.loads(output)

        if 'error' in data:
            logger.error(f"API 返回错误: {data['error']}")
            return None

        if data.get('code') == '10000':
            return data
        else:
            logger.error(f"API 返回错误: {data.get('msg', 'unknown')}")
            return None

    except subprocess.TimeoutExpired:
        logger.error("api_query.py 执行超时")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"api_query.py 输出解析失败: {e}")
        return None
    except Exception as e:
        logger.error(f"api_query.py 调用异常: {e}")
        return None


def _is_etf_code(stock_code: str) -> bool:
    """判断是否为 ETF 代码"""
    etf_prefixes = ('51', '52', '56', '58', '15', '16', '18')
    return stock_code.startswith(etf_prefixes) and len(stock_code) == 6


def normalize_code(stock_code: str) -> tuple:
    """
    标准化股票代码

    Returns:
        tuple: (market, code)
        - market: 'a', 'hk', 'us'
        - code: 标准化后的代码
    """
    code = stock_code.strip()

    if code.isdigit() and len(code) == 6:
        return 'a', code

    import re
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
    获取股票日线数据（通过内置 stock-market-information skill）

    Args:
        stock_code: 股票代码（仅支持 A 股）
        days: 获取天数（API 返回全量数据，此参数用于截取）

    Returns:
        (DataFrame, 股票名称) 元组，DataFrame 包含 OHLCV 数据，失败返回 None
    """
    # 检查数据源是否可用
    data_source_error = _check_data_source()
    if data_source_error:
        logger.error(data_source_error)
        return None

    market, code = normalize_code(stock_code)

    if market != 'a':
        logger.warning(f"stock-market-information 仅支持 A 股，{stock_code} 为 {market} 市场代码")
        return None

    # 多页请求拼接数据（API 每页返回 20 条）
    pages_needed = max(1, (days + 19) // 20)
    all_results = []

    for page in range(1, pages_needed + 1):
        data = _call_api('getStkDayQuoByCond-G', {
            'stkCode': code,
            'pageNum': str(page),
            'pageSize': '20',
        })
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

    # 提取股票名称（取最新一条数据中的名称）
    all_results.sort(key=lambda x: x.get('TRADE_DATE', ''), reverse=True)
    name = all_results[0].get('STK_SHORT_NAME', stock_code)

    # 去重（按 TRADE_DATE）
    seen = set()
    unique = []
    for r in all_results:
        dt = r.get('TRADE_DATE', '')
        if dt not in seen:
            seen.add(dt)
            unique.append(r)

    # 转换为 DataFrame
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

    # 删除不需要的列
    keep_cols = ['date', 'open', 'high', 'low', 'close', 'volume', 'amount', 'pct_chg', 'pre_close']
    df = df[[c for c in keep_cols if c in df.columns]]

    df = df.dropna(subset=['close', 'volume'])
    df = df.sort_values('date', ascending=True).reset_index(drop=True)

    if days and len(df) > days:
        df = df.tail(days).reset_index(drop=True)

    return df, name
