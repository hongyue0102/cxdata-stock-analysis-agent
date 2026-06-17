# -*- coding: utf-8 -*-
"""
CXDA Skill 公共模块
提取各脚本中共用的常量、工具函数、CLI 缓存读写逻辑。
"""

import base64
import gzip
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Tuple

# ── Windows 编码修复 ──────────────────────────────────────────────────
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# ── 常量 ──────────────────────────────────────────────────────────────
BASE_URL = "https://cxapi.ccxe.com.cn/cxda"

PROXIES = {
    "http": None,
    "https": None,
}

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

TOKEN_VALID_SECONDS = 300  # authtoken 缓存 300 秒

# 渠道参数（Skill生成时自动填充，请勿手动修改）
REQUEST_CHANNEL = "CAXEN"


# ── CLI 缓存封装 ──────────────────────────────────────────────────────

def _get_cli_path() -> Path:
    """获取 cxda_cache_cli.py 路径（本地优先）"""
    env_path = os.environ.get("CXDA_CACHE_CLI_PATH")
    if env_path:
        return Path(env_path)
    return Path(__file__).parent / "cxda_cache_cli.py"


def _get_python_exe() -> str:
    """获取 Python 执行路径"""
    env_python = os.environ.get("CXDA_CACHE_PYTHON")
    if env_python:
        return env_python
    return sys.executable


def _get_workspace() -> str:
    """
    获取工作空间路径

    优先级：
    1. CXDA_CACHE_WORKSPACE 环境变量
    2. CLAUDE_WORKSPACE 环境变量
    3. 默认 ~/.cxda-cache
    """
    workspace = os.environ.get("CXDA_CACHE_WORKSPACE") \
        or os.environ.get("CLAUDE_WORKSPACE") \
        or str(Path.home() / ".cxda-cache")

    Path(workspace).mkdir(parents=True, exist_ok=True)
    return workspace


def _cli_call(command: str, subcommand: str = None, args: list = None, raw_output: bool = False) -> dict:
    """
    调用 cxda_cache_cli.py CLI

    Args:
        command: 主命令（auth, shared, read, write 等）
        subcommand: 子命令（get, set, read, write 等）
        args: 额外参数列表
        raw_output: 是否返回原始输出

    Returns:
        CLI 返回的 JSON 字典
    """
    args = args or []
    cmd = [_get_python_exe(), str(_get_cli_path()), command]
    if subcommand:
        cmd.append(subcommand)
    cmd.extend(args)

    env = os.environ.copy()
    env.setdefault("CXDA_CACHE_WORKSPACE", _get_workspace())

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, env=env)
        stdout = result.stdout.strip() if result.stdout else ""

        if raw_output:
            return {"success": True, "content": stdout}

        if stdout:
            try:
                return json.loads(stdout)
            except json.JSONDecodeError:
                return {"success": True, "content": stdout}
        return {"success": False, "error": "Empty output"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ── 认证数据读写 ──────────────────────────────────────────────────────

def get_cached_auth() -> dict:
    """从缓存读取认证数据"""
    result = _cli_call("auth", "get")
    if result and isinstance(result, dict):
        if result.get("success") is not None:
            return result.get("data", {})
        elif "error" not in result:
            return result
    return {}


def check_terms_accepted() -> Tuple[bool, dict]:
    """
    检查用户是否已接受服务协议
    
    Returns:
        (accepted, error_response): accepted=True 时可继续，False 时返回结构化错误
    """
    auth = get_cached_auth()
    accepted = auth.get("terms_accepted", False)
    if not accepted:
        return False, {
            "code": "10500",
            "msg": "用户尚未接受服务协议，请先通过 auth.py terms-check 和 terms-accept 完成协议确认",
            "status": "terms_not_accepted",
            "data": "",
        }
    return True, {}


def save_auth(data: dict):
    """保存认证数据到缓存（合并更新）"""
    _cli_call("auth", "set", ["--data", json.dumps(data, ensure_ascii=False)])


# ── 公域 JSON 文件读写（跨 Skill 共享，如会话账本） ──────────────────────

def get_shared_json(filename: str) -> dict:
    """
    读取公域 JSON 文件，文件不存在或解析失败时返回空字典。

    注意：cxda_cache_cli.py 的 `shared read` 成功时直接输出文件内容（JSON），
    失败时输出 {"success": false, "error": ...}，此处据此区分。
    """
    result = _cli_call("shared", "read", [filename])
    if isinstance(result, dict):
        if result.get("success") is False and "error" in result:
            return {}
        return result
    return {}


def save_shared_json(filename: str, data: dict):
    """写入公域 JSON 文件（覆盖写）"""
    _cli_call("shared", "write", [filename, "--content", json.dumps(data, ensure_ascii=False)])


# ── CXDA_USER_KEY 管理 ───────────────────────────────────────────────

def get_user_key() -> str:
    """
    获取 CXDA_USER_KEY

    优先级：
    1. 环境变量 CXDA_USER_KEY
    2. 缓存中的 CXDA_USER_KEY
    """
    env_key = os.environ.get("CXDA_USER_KEY")
    if env_key:
        return env_key

    auth = get_cached_auth()
    return auth.get("CXDA_USER_KEY", "")


def mask_user_key(key: str) -> str:
    """脱敏 CXDA_USER_KEY，只保留前4后4字符"""
    if not key or len(key) <= 8:
        return "****"
    return key[:4] + "****" + key[-4:]


def set_user_key(key: str):
    """将 CXDA_USER_KEY 写入缓存"""
    save_auth({"CXDA_USER_KEY": key})


# ── Token 管理 ────────────────────────────────────────────────────────

def get_cached_token():
    """
    获取缓存的有效 token，返回 (token, need_refresh)
    """
    auth = get_cached_auth()

    try:
        expire_str = auth.get("authtoken_expire", "")
        token = auth.get("authtoken", "")
        if not token:
            return None, True

        expire = datetime.strptime(expire_str, '%Y-%m-%d %H:%M:%S')
        remaining = expire - datetime.now()
        if remaining <= timedelta(0):
            return None, True  # 已过期
        else:
            return token, False  # 有效
    except Exception:
        return None, True


def cache_token(token: str):
    """缓存 token"""
    auth = get_cached_auth()
    auth.update({
        'authtoken': token,
        'authtoken_expire': (datetime.now() + timedelta(seconds=TOKEN_VALID_SECONDS)).strftime('%Y-%m-%d %H:%M:%S'),
    })
    save_auth(auth)


def fetch_new_token() -> str:
    """获取新 token"""
    import requests

    user_key = get_user_key()
    if not user_key:
        return ""

    try:
        params = {"userKey": user_key}
        if REQUEST_CHANNEL:
            params["requestChannel"] = REQUEST_CHANNEL
        resp = requests.get(
            f"{BASE_URL}/webservice/foreign_getAuthtoken.htm",
            params=params,
            headers=HEADERS,
            proxies=PROXIES
        )
        token = json.loads(resp.text).get("result")
        if token:
            cache_token(token)
        return token or ""
    except Exception:
        return ""


def ensure_token() -> str:
    """
    确保有有效 token（缓存未过期直接用，否则刷新）

    Returns:
        有效的 authtoken 字符串

    Raises:
        SystemExit: 无 userKey 或获取 token 失败时打印错误并退出
    """
    user_key = get_user_key()
    if not user_key:
        output_error("未找到 CXDA_USER_KEY，请先通过 auth.py 完成认证")
        sys.exit(1)

    token, need_refresh = get_cached_token()
    if need_refresh:
        token = fetch_new_token()
        if not token:
            output_error("获取 authToken 失败")
            sys.exit(1)

    return token


# ── HTTP 请求封装 ─────────────────────────────────────────────────────

def http_get(url: str, params: dict = None, include_channel: bool = True) -> dict:
    """
    统一 HTTP GET 请求（含 gzip + base64 解码）

    Args:
        url: 完整请求 URL
        params: 查询参数
        include_channel: 是否自动附加 requestChannel 参数（默认 True）

    Returns:
        解析后的 JSON 数据字典
    """
    import requests

    params = dict(params or {})
    if include_channel and REQUEST_CHANNEL:
        params["requestChannel"] = REQUEST_CHANNEL

    resp = requests.get(url, params=params, headers=HEADERS, proxies=PROXIES)

    # 尝试 gzip + base64 解码
    try:
        data = json.loads(gzip.decompress(base64.b64decode(resp.text.strip())).decode('utf-8'))
        return data
    except Exception:
        # 非 gzip 数据，直接 JSON 解析
        return json.loads(resp.text)


# ── 输出工具 ──────────────────────────────────────────────────────────

def output_json(data, indent=4):
    """统一 JSON 输出"""
    print(json.dumps(data, indent=indent, ensure_ascii=False))


def output_error(msg):
    """统一错误输出"""
    print(json.dumps({"error": msg, "status": "failed"}, ensure_ascii=False))
