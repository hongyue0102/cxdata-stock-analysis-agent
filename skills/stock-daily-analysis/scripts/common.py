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

# 凭证加解密（硬依赖，缓解风险3：杜绝任何“无加密执行”分支）。
# 缺失 cryptography 库时直接 ImportError 终止，绝不退化到明文存储。
# requirements.txt 已声明 cryptography，部署环境须 pip install。
import cred_crypto

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

def _safe_env_path(name: str) -> str:
    """读取并校验环境变量取值（缓解环境变量 RCE）。

    拒绝 shell 元字符（; | & $ ` > < 换行等）、空字节，以及路径遍历序列（../）。
    非法值视为未设置，回退默认值。
    """
    value = os.environ.get(name, "")
    if not value:
        return ""
    if any(ch in value for ch in (";", "|", "&", "$", "`", ">", "<", "\n", "\r", "\0")):
        return ""
    # 拒绝路径遍历：含 .. 的取值一律拒绝（缓解 env RCE：绝对路径/相对逃逸指向恶意可执行文件）
    if ".." in value:
        return ""
    return value


def _safe_env_executable(name: str, trusted_dir: Path = None, trusted_name: str = None, name_pattern: str = None) -> str:
    """校验指向可执行文件的环境变量（缓解 env RCE）。

    在 _safe_env_path 基础上额外要求：
    - 必须是绝对路径；
    - 若指定 trusted_dir，则路径必须位于该目录内；
    - 若指定 trusted_name，resolve 后文件名必须精确匹配；
    - 若指定 name_pattern（正则），resolve 后文件名必须匹配（如 python 解释器）。
    不满足则视为未设置，回退默认值。
    """
    value = _safe_env_path(name)
    if not value:
        return ""
    p = Path(value)
    if not p.is_absolute():
        return ""
    try:
        resolved = p.resolve()
    except (ValueError, OSError):
        return ""
    if trusted_dir is not None:
        try:
            resolved.relative_to(trusted_dir.resolve())
        except (ValueError, OSError):
            return ""
    if trusted_name is not None and resolved.name != trusted_name:
        return ""
    if name_pattern is not None:
        import re as _re_mod
        if not _re_mod.match(name_pattern, resolved.name):
            return ""
    return value


def _get_cli_path() -> Path:
    """获取 cxda_cache_cli.py 路径（本地优先，限定在 scripts 目录内）"""
    scripts_dir = Path(__file__).parent
    env_path = _safe_env_executable("CXDA_CACHE_CLI_PATH", trusted_dir=scripts_dir, trusted_name="cxda_cache_cli.py")
    if env_path:
        return Path(env_path)
    return scripts_dir / "cxda_cache_cli.py"


def _get_python_exe() -> str:
    """获取 Python 执行路径（必须绝对路径、文件名匹配 python*，拒绝指向任意可执行文件）"""
    env_python = _safe_env_executable("CXDA_CACHE_PYTHON", name_pattern=r"^python(\d+(\.\d+)*)?$")
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
    workspace = _safe_env_path("CXDA_CACHE_WORKSPACE") \
        or _safe_env_path("CLAUDE_WORKSPACE") \
        or str(Path.home() / ".cxda-cache")

    Path(workspace).mkdir(parents=True, exist_ok=True)
    return workspace


def _cli_call(command: str, subcommand: str = None, args: list = None, raw_output: bool = False, stdin_input: str = None) -> dict:
    """
    调用 cxda_cache_cli.py CLI

    Args:
        command: 主命令（auth, shared, read, write 等）
        subcommand: 子命令（get, set, read, write 等）
        args: 额外参数列表
        raw_output: 是否返回原始输出
        stdin_input: 通过 stdin 传入的内容（用于传敏感数据，避免出现在进程列表，缓解风险2）

    Returns:
        CLI 返回的 JSON 字典

    安全（缓解风险3）：异常时不把完整 cmd（可能含敏感参数）放入 error，只返回脱敏的类型信息。
    安全（缓解火山风险1+2）：环境变量白名单传递，只传子进程必需变量，
    拒绝 PYTHONPATH/PYTHONHOME/LD_PRELOAD 等危险变量和敏感变量泄露给子进程。
    """
    args = args or []
    cmd = [_get_python_exe(), str(_get_cli_path()), command]
    if subcommand:
        cmd.append(subcommand)
    cmd.extend(args)

    # 环境变量白名单：只传子进程必需变量，阻断 PYTHONPATH/LD_PRELOAD 等 RCE 向量，
    # 同时避免 AWS_*、DATABASE_URL 等敏感变量泄露给子进程（火山风险1+2）
    _ENV_WHITELIST_PREFIXES = (
        "PATH", "HOME", "USER", "USERNAME", "LOGNAME", "LANG", "LC_",
        "TERM", "TMPDIR", "TEMP", "TMP", "SHELL", "PWD",
        "CXDA_CACHE_", "CLAUDE_WORKSPACE",
        "HOSTNAME", "HOST",
    )
    _ENV_BLACKLIST_EXACT = {
        "PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP", "PYTHONINSPECT",
        "PYTHONDEBUG", "PYTHONDONTWRITEBYTECODE", "PYTHONNOUSERSITE",
        "LD_PRELOAD", "LD_LIBRARY_PATH", "DYLD_INSERT_LIBRARIES",
        "DYLD_LIBRARY_PATH", "LD_DEBUG",
    }
    env = {}
    for k, v in os.environ.items():
        if k in _ENV_BLACKLIST_EXACT:
            continue
        if any(k.startswith(prefix) for prefix in _ENV_WHITELIST_PREFIXES):
            env[k] = v
    env.setdefault("CXDA_CACHE_WORKSPACE", _get_workspace())

    try:
        result = subprocess.run(
            cmd,
            input=stdin_input,
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )
        stdout = result.stdout.strip() if result.stdout else ""

        if raw_output:
            return {"success": True, "content": stdout}

        if stdout:
            try:
                return json.loads(stdout)
            except json.JSONDecodeError:
                return {"success": True, "content": stdout}
        return {"success": False, "error": "Empty output"}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "CLI 调用超时"}
    except FileNotFoundError:
        return {"success": False, "error": "CLI 可执行文件不存在"}
    except Exception as e:
        # 脱敏：不返回可能含敏感参数的完整命令行，只返回异常类型名（缓解风险3）
        return {"success": False, "error": "CLI 调用失败：{}".format(type(e).__name__)}


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
    """保存认证数据到缓存（合并更新）。

    CXDA_USER_KEY 落盘前统一加密（缓解风险3：明文存储），所有调用方无需各自处理。
    安全：数据通过 stdin 传给 CLI，不作为命令行参数，避免出现在进程列表（缓解风险2）。
    cred_crypto 为硬依赖（顶部 import），不存在无加密分支。

    加密判定改用"尝试解密+前缀+解密成功"三重验证（替代 is_encrypted 纯前缀检查），
    防止后端返回的明文 key 恰好以 "ENCv1:" 开头时被误判为已加密而明文落盘（火山风险1）。
    仅当 key 有 EN Cv1: 前缀且 decrypt 返回非空明文时，才视为已加密形态跳过。
    """
    if isinstance(data, dict) and data.get("CXDA_USER_KEY"):
        key = data["CXDA_USER_KEY"]
        already_encrypted = False
        if key.startswith(cred_crypto._ENC_PREFIX):
            decrypted, _ = cred_crypto.decrypt(key)
            if decrypted:
                already_encrypted = True
        if not already_encrypted:
            data = {**data, "CXDA_USER_KEY": cred_crypto.encrypt(key)}
    _cli_call("auth", "set", stdin_input=json.dumps(data, ensure_ascii=False))


# ── 公域 JSON 文件读写（跨 Skill 共享，如会话账本） ──────────────────────

import re as _re
# filename 只允许 字母/数字/下划线/连字符/点（缓解路径遍历）
_SHARED_FILENAME_RE = _re.compile(r'^[A-Za-z0-9_.\-]+$')


def _validate_shared_filename(filename: str) -> str:
    """校验公域文件名格式（缓解路径遍历）。CLI 侧已有防护，此处入口层双保险。"""
    if not isinstance(filename, str) or not filename or not _SHARED_FILENAME_RE.match(filename):
        raise ValueError(f"非法公域文件名（仅允许字母数字下划线连字符点）: {filename!r}")
    return filename


def get_shared_json(filename: str) -> dict:
    """
    读取公域 JSON 文件，文件不存在或解析失败时返回空字典。

    注意：cxda_cache_cli.py 的 `shared read` 成功时直接输出文件内容（JSON），
    失败时输出 {"success": false, "error": ...}，此处据此区分。
    """
    filename = _validate_shared_filename(filename)
    result = _cli_call("shared", "read", [filename])
    if isinstance(result, dict):
        if result.get("success") is False and "error" in result:
            return {}
        return result
    return {}


def save_shared_json(filename: str, data: dict):
    """写入公域 JSON 文件（覆盖写）。内容经 stdin 传，不进命令行（避免进程列表暴露）。"""
    filename = _validate_shared_filename(filename)
    _cli_call("shared", "write", [filename], stdin_input=json.dumps(data, ensure_ascii=False))


def get_shared_text(filename: str) -> str:
    """
    读取公域文本文件，文件不存在时返回空字符串。

    JSONL 只有单行时会被普通 _cli_call 当作 JSON 解析，因此这里使用 raw_output。
    """
    filename = _validate_shared_filename(filename)
    result = _cli_call("shared", "read", [filename], raw_output=True)
    if not isinstance(result, dict):
        return ""

    content = result.get("content") or ""
    if content:
        try:
            parsed = json.loads(content)
            if isinstance(parsed, dict) and parsed.get("success") is False and "error" in parsed:
                return ""
        except json.JSONDecodeError:
            pass
    return content


def save_shared_text(filename: str, content: str):
    """写入公域文本文件（覆盖写）。内容经 stdin 传，不进命令行。"""
    filename = _validate_shared_filename(filename)
    _cli_call("shared", "write", [filename], stdin_input=content)


def append_shared_text(filename: str, content: str):
    """追加写入公域文本文件。内容经 stdin 传，不进命令行。"""
    filename = _validate_shared_filename(filename)
    _cli_call("shared", "append", [filename], stdin_input=content)


# ── CXDA_USER_KEY 管理 ───────────────────────────────────────────────

def get_user_key() -> str:
    """
    获取 CXDA_USER_KEY

    优先级：
    1. 环境变量 CXDA_USER_KEY
    2. 缓存中的 CXDA_USER_KEY（加密存储，读取时透明解密；老明文自动迁移）
    """
    env_key = os.environ.get("CXDA_USER_KEY")
    if env_key:
        return env_key

    auth = get_cached_auth()
    stored = auth.get("CXDA_USER_KEY", "")
    if not stored:
        return ""
    plaintext, needs_migration = cred_crypto.decrypt(stored)
    if needs_migration and plaintext:
        try:
            set_user_key(plaintext)
        except Exception:
            pass
    return plaintext


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

    安全（缓解风险6 SSRF）：校验 url 的 scheme/host/path，只允许官方域名且 path
    必须以 BASE_URL 的 path 前缀开头（/cxda/），拒绝跨 path 访问（如 /cxdaevil/）。
    """
    import requests
    from urllib.parse import urlparse, unquote
    import posixpath

    # SSRF 防护：scheme/host/path 三重校验 + path 规范化，防止 /cxda/../admin 绕过（缓解 SSRF）
    base = urlparse(BASE_URL)
    parsed = urlparse(url) if isinstance(url, str) else None
    # 先解码 URL 编码（防 %2e%2e 绕过），再规范化 path，消除 ../ 、// 等逃逸序列
    norm_path = posixpath.normpath(unquote(parsed.path)) if parsed else ""
    if (
        not parsed
        or parsed.scheme != base.scheme
        or parsed.netloc != base.netloc
        or not norm_path.startswith(base.path + "/")
    ):
        # 脱敏：不回显完整 url（可能含敏感参数，缓解风险7）
        raise ValueError("拒绝非白名单 URL 请求（仅允许官方 cxdata 接口路径）")

    params = dict(params or {})
    if include_channel and REQUEST_CHANNEL:
        params["requestChannel"] = REQUEST_CHANNEL

    try:
        resp = requests.get(url, params=params, headers=HEADERS, proxies=PROXIES, timeout=30)
    except Exception:
        # 脱敏：不抛含 url 的原始异常（缓解风险7）
        raise RuntimeError("网络请求失败")

    # 尝试 gzip + base64 解码
    try:
        data = json.loads(gzip.decompress(base64.b64decode(resp.text.strip())).decode('utf-8'))
        return data
    except Exception:
        # 非 gzip 数据，直接 JSON 解析
        try:
            return json.loads(resp.text)
        except Exception:
            raise RuntimeError("响应解析失败")


# ── 输出工具 ──────────────────────────────────────────────────────────

def output_json(data, indent=4):
    """统一 JSON 输出"""
    print(json.dumps(data, indent=indent, ensure_ascii=False))


def output_error(msg):
    """统一错误输出"""
    print(json.dumps({"error": msg, "status": "failed"}, ensure_ascii=False))
