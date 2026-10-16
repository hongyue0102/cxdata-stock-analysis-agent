# -*- coding: utf-8 -*-
"""
CXDA Skill 公共模块
提取各脚本中共用的常量、工具函数、CLI 缓存读写逻辑及接口审计日志。
"""

import base64
import gzip
import json
import os
import posixpath
import re
import subprocess
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Tuple

# 凭证加解密（兼容历史明文与已有 ENCv1 缓存）。
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
TOKEN_REFRESH_SKEW_SECONDS = 10
_TOKEN_MEMORY_CACHE = None

# 渠道参数（Skill生成时自动填充，请勿手动修改）
REQUEST_CHANNEL = "CAXEN"

# 接口调用审计日志（每行一个 JSON；写入缓存工作区 .shared，失败时静默忽略）。
# 日志仅供本地排障/审计使用，不参与任何业务流程，也不会写到 stdout/stderr。
API_CALL_LOG_FILE = "cxda_api_calls.jsonl"
_AUDIT_CONTROL_RE = re.compile(r"[\r\n\t\x00-\x1f\x7f]")
_AUDIT_SENSITIVE_KEYS = frozenset({
    "authtoken", "token", "accesstoken", "access_token",
    "userkey", "user_key", "cxda_user_key", "verifycode", "verify_code",
    "apikey", "api_key", "password", "passwd", "secret", "clientsecret",
    "client_secret", "refresh_token", "authorization", "cookie",
})


def _audit_mask(value, key=None):
    """清理审计字段中的控制字符并脱敏凭证/验证码。

    参数名保留在日志中，便于定位调用；已知敏感字段仅记录 ``****``，
    手机号使用局部掩码，其他字段原样保留（控制字符会被替换为空格）。
    """
    normalized_key = str(key or "").replace("-", "_").lower()
    if normalized_key in _AUDIT_SENSITIVE_KEYS:
        return "****"
    if normalized_key in {"phone", "mobile", "mobilephone", "phone_number"}:
        text = "" if value is None else str(value)
        if len(text) > 7:
            return text[:3] + "****" + text[-4:]
        return "****"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, dict):
        return {str(k): _audit_mask(v, k) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_audit_mask(v, key) for v in value]
    return _AUDIT_CONTROL_RE.sub(" ", str(value))


def _audit_url(url):
    """脱敏 URL 查询串中的凭证，避免非标准调用把密钥写入日志。"""
    text = _AUDIT_CONTROL_RE.sub(" ", str(url or ""))
    try:
        from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
        parsed = urlsplit(text)
        if not parsed.query:
            return text
        query = []
        for key, value in parse_qsl(parsed.query, keep_blank_values=True):
            query.append((key, _audit_mask(value, key)))
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment))
    except Exception:
        return text


def _audit_complete(value):
    """将完整响应转换为可安全写入 JSONL 的结构，保留所有字段和值。"""
    if value is None or isinstance(value, (bool, int, float, str)):
        if isinstance(value, str):
            return _AUDIT_CONTROL_RE.sub(" ", value)
        return value
    if isinstance(value, dict):
        return {str(k): _audit_complete(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_audit_complete(v) for v in value]
    return _AUDIT_CONTROL_RE.sub(" ", str(value))


def _is_full_response_endpoint(url):
    """仅对分页配置接口保留完整响应，避免其它接口响应膨胀审计日志。"""
    try:
        from urllib.parse import urlsplit
        path = (urlsplit(str(url or "")).path or "").rstrip("/")
        return path.endswith("/mall/api_getApiLimitSetting.htm")
    except Exception:
        return False


def log_api_call(method, url, params=None, *, operation=None, success=None,
                 response_code=None, error_type=None, extra=None,
                 response=None, include_response=False):
    """静默追加一条接口调用日志。

    该函数故意永不向调用方抛出异常，日志故障不能改变接口行为。日志写入
    公域缓存文件，利用 ``append_shared_text`` 的 O_APPEND 保证多进程追加时
    每条 JSONL 记录不互相覆盖。``params`` 会保留字段名但自动脱敏敏感值；
    ``include_response=True`` 时额外保留完整响应内容。
    """
    try:
        event = {
            "ts": int(time.time()),
            "method": _AUDIT_CONTROL_RE.sub(" ", str(method or "")),
            "url": _audit_url(url),
            "params": _audit_mask(dict(params or {})),
        }
        if operation:
            event["operation"] = _AUDIT_CONTROL_RE.sub(" ", str(operation))
        if success is not None:
            event["success"] = bool(success)
        if response_code is not None:
            event["response_code"] = _audit_mask(response_code, "response_code")
        if error_type:
            event["error_type"] = _AUDIT_CONTROL_RE.sub(" ", str(error_type))
        if isinstance(extra, dict):
            event["extra"] = _audit_mask(extra)
        if include_response:
            # 分页配置接口要求完整留存响应；此字段不做敏感键掩码，
            # 仅替换控制字符，确保日志中的 JSON 记录结构不被破坏。
            event["response"] = _audit_complete(response)
        # append_shared_text is defined below and resolved when this function runs.
        append_shared_text(API_CALL_LOG_FILE, json.dumps(event, ensure_ascii=False) + "\n")
    except Exception:
        pass


class AuthenticationRequiredError(RuntimeError):
    """无可用认证信息时携带可直接输出给 Agent 的结构化响应。"""

    def __init__(self, response: dict):
        super().__init__(response.get("msg", "需要完成认证"))
        self.response = response


# ── CLI 缓存封装 ──────────────────────────────────────────────────────


def _safe_env_path(name: str) -> str:
    """读取并校验路径类环境变量。

    这些值最终会参与子进程启动或缓存路径拼接，因此不能把 shell 元字符、
    控制字符或路径遍历片段原样带入。非法值按“未设置”处理并回退默认值，
    对现有调用方保持透明。
    """
    value = os.environ.get(name, "")
    if not value:
        return ""
    if any(ch in value for ch in (";", "|", "&", "$", "`", ">", "<", "\n", "\r", "\0")):
        return ""
    if ".." in value:
        return ""
    return value


def _safe_env_executable(name: str, trusted_dir=None, trusted_name: str = None,
                         name_pattern: str = None) -> str:
    """校验环境变量指定的可执行文件或脚本路径。

    路径必须是绝对路径、指向普通文件，并可进一步限制在可信目录或文件名内，
    从而保留 CXDA_CACHE_* 的兼容配置能力，同时阻断环境变量替换解释器/脚本。
    """
    value = _safe_env_path(name)
    if not value:
        return ""
    path = Path(value)
    if not path.is_absolute():
        return ""
    try:
        resolved = path.resolve()
        if not resolved.is_file():
            return ""
    except (OSError, ValueError):
        return ""

    if trusted_dir is not None:
        candidates = trusted_dir if isinstance(trusted_dir, (list, tuple, set)) else [trusted_dir]
        matched = False
        for candidate in candidates:
            try:
                resolved.relative_to(Path(candidate).resolve())
                matched = True
                break
            except (OSError, ValueError):
                continue
        if not matched:
            return ""
    if trusted_name is not None and resolved.name != trusted_name:
        return ""
    if name_pattern is not None and not re.match(name_pattern, resolved.name, re.IGNORECASE):
        return ""
    return str(resolved)


def _python_trusted_dirs():
    """返回常见 Python 安装目录及当前解释器目录。"""
    dirs = [
        "/usr/bin", "/usr/local/bin", "/usr/sbin", "/usr/local/sbin",
        "/bin", "/sbin", "/opt/homebrew/bin", "/usr/local/opt",
        "/opt/python", "/opt",
    ]
    if os.name == "nt":
        for env_name in ("ProgramFiles", "ProgramFiles(x86)", "LocalAppData"):
            root = os.environ.get(env_name)
            if root:
                dirs.extend((str(Path(root) / "Python"), str(Path(root) / "Programs" / "Python")))
    try:
        current_dir = str(Path(sys.executable).resolve().parent)
        if current_dir not in dirs:
            dirs.append(current_dir)
    except (OSError, ValueError):
        pass
    return dirs


def _get_cli_path() -> Path:
    """获取 cxda_cache_cli.py 路径（仅允许当前 scripts 目录内的同名脚本）。"""
    scripts_dir = Path(__file__).resolve().parent
    env_path = _safe_env_executable(
        "CXDA_CACHE_CLI_PATH",
        trusted_dir=scripts_dir,
        trusted_name="cxda_cache_cli.py",
    )
    if env_path:
        return Path(env_path)
    return scripts_dir / "cxda_cache_cli.py"


def _get_python_exe() -> str:
    """获取 Python 执行路径（环境变量仅接受可信 Python 可执行文件）。"""
    env_python = _safe_env_executable(
        "CXDA_CACHE_PYTHON",
        trusted_dir=_python_trusted_dirs(),
        name_pattern=r"^python(\d+(\.\d+)*)?(\.exe)?$",
    )
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
    candidate = (
        _safe_env_path("CXDA_CACHE_WORKSPACE")
        or _safe_env_path("CLAUDE_WORKSPACE")
        or str(Path.home() / ".cxda-cache")
    )
    try:
        path = Path(candidate).expanduser()
        if not path.is_absolute():
            return str(Path.home() / ".cxda-cache")
        resolved = path.resolve()
        home = Path.home().resolve()
        critical = (
            "/etc", "/bin", "/sbin", "/usr", "/boot", "/dev", "/proc", "/sys",
            "/var", "/lib", "/lib64", "/Library", "/System",
        )
        value = str(resolved)
        if any(value == item or value.startswith(item + os.sep) for item in critical):
            return str(Path.home() / ".cxda-cache")
        if resolved == home:
            return str(home / ".cxda-cache")
        try:
            resolved.relative_to(home)
        except ValueError:
            return str(Path.home() / ".cxda-cache")
        resolved.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(resolved, 0o700)
        except OSError:
            pass
        return str(resolved)
    except (OSError, ValueError):
        return str(Path.home() / ".cxda-cache")


def _build_child_env() -> dict:
    """构造缓存 CLI 的最小环境，避免危险变量注入和无关敏感变量泄露。"""
    allowed_exact = {
        "PATH", "HOME", "USER", "USERNAME", "USERPROFILE", "LOGNAME",
        "LANG", "TERM", "TMPDIR", "TEMP", "TMP", "SHELL", "PWD",
        "HOSTNAME", "HOST", "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT",
        "HOMEDRIVE", "HOMEPATH", "APPDATA", "LOCALAPPDATA", "PROGRAMDATA",
        "CLAUDE_WORKSPACE",
    }
    blocked_exact = {
        "PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP", "PYTHONINSPECT",
        "PYTHONDEBUG", "PYTHONDONTWRITEBYTECODE", "PYTHONNOUSERSITE",
        "LD_PRELOAD", "LD_LIBRARY_PATH", "LD_DEBUG",
        "DYLD_INSERT_LIBRARIES", "DYLD_LIBRARY_PATH",
    }
    env = {}
    for key, value in os.environ.items():
        upper = key.upper()
        if upper in blocked_exact:
            continue
        if upper in allowed_exact or upper.startswith("LC_") or upper.startswith("CXDA_CACHE_"):
            env[key] = value
    env["CXDA_CACHE_WORKSPACE"] = _get_workspace()
    return env


def _cli_call(command: str, subcommand: str = None, args: list = None,
              raw_output: bool = False, stdin_input: str = None) -> dict:
    """
    调用 cxda_cache_cli.py CLI

    Args:
        command: 主命令（auth, shared, read, write 等）
        subcommand: 子命令（get, set, read, write 等）
        args: 额外参数列表
        raw_output: 是否返回原始输出
        stdin_input: 通过 stdin 传入内容，避免凭证/缓存内容出现在进程参数中

    Returns:
        CLI 返回的 JSON 字典
    """
    args = args or []
    cmd = [_get_python_exe(), str(_get_cli_path()), command]
    if subcommand:
        cmd.append(subcommand)
    cmd.extend(args)

    try:
        result = subprocess.run(
            cmd,
            input=stdin_input,
            capture_output=True,
            text=True,
            timeout=30,
            env=_build_child_env(),
        )
        stdout = result.stdout.strip() if result.stdout else ""

        if raw_output:
            if result.returncode != 0 and not stdout:
                return {"success": False, "error": "CLI 调用失败"}
            return {"success": True, "content": stdout}

        if stdout:
            try:
                return json.loads(stdout)
            except json.JSONDecodeError:
                if result.returncode != 0:
                    return {"success": False, "error": "CLI 调用失败"}
                return {"success": True, "content": stdout}
        if result.returncode != 0:
            return {"success": False, "error": "CLI 调用失败"}
        return {"success": False, "error": "Empty output"}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "CLI 调用超时"}
    except FileNotFoundError:
        return {"success": False, "error": "CLI 可执行文件不存在"}
    except Exception as exc:
        return {"success": False, "error": "CLI 调用失败：{}".format(type(exc).__name__)}


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
            "msg": "用户尚未接受服务协议，请按认证流程展示协议并在用户同意后执行 auth.py terms-accept",
            "status": "terms_not_accepted",
            "data": "",
        }
    return True, {}


def save_auth(data: dict):
    """保存认证数据到缓存（合并更新）。

    存储形态以落盘前已有的 CXDA_USER_KEY 为准：
    - 历史明文用户继续使用明文，不自动迁移，保证旧版 Skill 仍可读取；
    - 已有 ENCv1 密文的用户继续使用密文；
    - 尚无 CXDA_USER_KEY 的新用户，首次 userKey 与后续 authtoken 均使用密文。
    """
    if not isinstance(data, dict):
        raise TypeError("认证数据必须是对象")

    payload = dict(data)
    credential_fields = ("CXDA_USER_KEY", "authtoken")
    if any(isinstance(payload.get(field), str) and payload.get(field)
           for field in credential_fields):
        existing_auth = get_cached_auth()
        if not isinstance(existing_auth, dict):
            existing_auth = {}
        existing_user_key = existing_auth.get("CXDA_USER_KEY", "")
        use_encryption = not (
            isinstance(existing_user_key, str)
            and existing_user_key
            and not existing_user_key.startswith(cred_crypto.ENC_PREFIX)
        )

        if use_encryption:
            for field in credential_fields:
                value = payload.get(field)
                if not isinstance(value, str) or not value:
                    continue
                if value == existing_auth.get(field):
                    # 未修改的已有密文原样保留；即使当前机器特征变化导致暂时
                    # 无法解密，也不能把它二次加密或降级为明文。
                    continue
                if value.startswith(cred_crypto.ENC_PREFIX):
                    plaintext, _ = cred_crypto.decrypt(value)
                    if not plaintext:
                        raise ValueError("无效的 ENCv1 凭证: {}".format(field))
                    continue
                payload[field] = cred_crypto.encrypt(value)

    # 通过 stdin 传递密钥，避免出现在 ps/process list；CLI 仍兼容旧 --data 形式。
    _cli_call("auth", "set", stdin_input=json.dumps(payload, ensure_ascii=False))
    global _TOKEN_MEMORY_CACHE
    if "authtoken" in payload or "CXDA_USER_KEY" in payload:
        _TOKEN_MEMORY_CACHE = None
    try:
        get_user_key.cache_clear()
    except (AttributeError, NameError):
        pass


# ── 公域 JSON 文件读写（跨 Skill 共享，如会话账本） ──────────────────────

_SHARED_FILENAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
_ALL_DOTS_RE = re.compile(r"^\.+$")


def _validate_shared_filename(filename: str) -> str:
    """校验共享文件名，阻断路径遍历和命令参数注入。"""
    if (
        not isinstance(filename, str)
        or not filename
        or not _SHARED_FILENAME_RE.fullmatch(filename)
        or _ALL_DOTS_RE.fullmatch(filename)
        or ".." in filename
    ):
        raise ValueError("非法公域文件名（仅允许安全文件名）: {!r}".format(filename))
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
    """写入公域 JSON 文件（覆盖写，内容经 stdin 传递）。"""
    filename = _validate_shared_filename(filename)
    result = _cli_call(
        "shared", "write", [filename],
        stdin_input=json.dumps(data, ensure_ascii=False),
    )
    if not isinstance(result, dict) or result.get("success") is not True:
        raise RuntimeError("写入共享 JSON 失败")


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
    """写入公域文本文件（覆盖写，内容经 stdin 传递）。"""
    filename = _validate_shared_filename(filename)
    result = _cli_call("shared", "write", [filename], stdin_input=content)
    if not isinstance(result, dict) or result.get("success") is not True:
        raise RuntimeError("写入共享文本失败")


def append_shared_text(filename: str, content: str):
    """追加写入公域文本文件（内容经 stdin 传递）。"""
    filename = _validate_shared_filename(filename)
    result = _cli_call("shared", "append", [filename], stdin_input=content)
    if not isinstance(result, dict) or result.get("success") is not True:
        raise RuntimeError("追加共享文本失败")


@contextmanager
def shared_file_lock(filename: str, timeout: float = 30.0):
    """获取跨 Skill、跨进程共享锁，供会话等多文件事务使用。"""
    filename = _validate_shared_filename(filename)
    from cxda_cache_cli import CacheManager

    manager = CacheManager(Path(_get_workspace()))
    with manager.shared_lock(filename, timeout=timeout):
        yield


# ── 跨 Skill 平台策略 ────────────────────────────────────────────────

PLATFORM_CONFIG_FILE = "cxda_platform_config.json"
SHOW_BILLING_INFO_KEY = "show_billing_info"
BILLING_INFO_VISIBLE_CHANNELS = frozenset({"ZORPHE","CAXEN"})


def get_platform_show_billing_info() -> bool:
    """
    读取跨 Skill 共享的平台计费信息展示策略。

    该策略同时控制积分消耗、套餐额度和 50 次调用确认。
    共享配置中的显式值优先；缺失、损坏或值非法时根据 REQUEST_CHANNEL
    生成缺省值：集合 BILLING_INFO_VISIBLE_CHANNELS 中的渠道展示，其他渠道隐藏。
    调用方不要在长会话中缓存结果，应在每次业务命令开始时重新读取。
    """
    platform_config = get_shared_json(PLATFORM_CONFIG_FILE)
    value = platform_config.get(SHOW_BILLING_INFO_KEY) if isinstance(platform_config, dict) else None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in ("true", "1", "on", "show", "visible"):
            return True
        if normalized in ("false", "0", "off", "hide", "hidden"):
            return False
    return str(REQUEST_CHANNEL or "").strip().upper() in BILLING_INFO_VISIBLE_CHANNELS


# ── CXDA_USER_KEY 管理 ───────────────────────────────────────────────

_LEGACY_USER_KEY_RE = re.compile(r"^[A-Za-z0-9_-]{1,256}$")


def _is_legacy_safe_user_key(key: str) -> bool:
    """兼容历史/测试环境中的短 userKey，但仍拒绝所有危险字符。"""
    return isinstance(key, str) and bool(_LEGACY_USER_KEY_RE.fullmatch(key))


@lru_cache(maxsize=1)
def get_user_key() -> str:
    """
    获取 CXDA_USER_KEY

    优先级：
    1. 环境变量 CXDA_USER_KEY
    2. 缓存中的 CXDA_USER_KEY（兼容明文和 ENCv1 密文，不改写存储形态）
    """
    env_key = os.environ.get("CXDA_USER_KEY")
    if env_key and _is_legacy_safe_user_key(env_key):
        return env_key

    auth = get_cached_auth()
    stored = auth.get("CXDA_USER_KEY", "")
    if not isinstance(stored, str) or not stored:
        return ""

    # 只对已有密文透明解密；历史明文直接使用且绝不回写，保证旧版 Skill
    # 继续能够读取同一份共享认证缓存。
    if stored.startswith(cred_crypto.ENC_PREFIX):
        plaintext, _ = cred_crypto.decrypt(stored)
        if not plaintext or not _is_legacy_safe_user_key(plaintext):
            return ""
        return plaintext

    if not _is_legacy_safe_user_key(stored):
        return ""
    return stored


def mask_user_key(key: str) -> str:
    """脱敏 CXDA_USER_KEY，只保留前4后4字符"""
    if not key or len(key) <= 8:
        return "****"
    return key[:4] + "****" + key[-4:]


# ── Token 管理 ────────────────────────────────────────────────────────

def get_cached_token():
    """
    获取缓存的有效 token，返回 (token, need_refresh)

    兼容明文和 ENCv1 密文：已有密文在运行时透明解密，明文直接使用；
    两种形态都不会因读取或刷新 token 被自动迁移、改写。
    """
    global _TOKEN_MEMORY_CACHE
    if isinstance(_TOKEN_MEMORY_CACHE, dict):
        token = _TOKEN_MEMORY_CACHE.get("token")
        expire = _TOKEN_MEMORY_CACHE.get("expire")
        if (
            token
            and isinstance(expire, datetime)
            and expire - datetime.now() > timedelta(seconds=TOKEN_REFRESH_SKEW_SECONDS)
        ):
            return token, False
        _TOKEN_MEMORY_CACHE = None

    auth = get_cached_auth()

    try:
        expire_str = auth.get("authtoken_expire", "")
        stored_token = auth.get("authtoken", "")
        if not stored_token:
            return None, True

        # 只对已有密文透明解密；历史明文直接使用且绝不回写。
        if isinstance(stored_token, str) and stored_token.startswith(cred_crypto.ENC_PREFIX):
            token, _ = cred_crypto.decrypt(stored_token)
            if not token:
                return None, True
        else:
            token = stored_token

        expire = datetime.strptime(expire_str, '%Y-%m-%d %H:%M:%S')
        remaining = expire - datetime.now()
        if remaining <= timedelta(seconds=TOKEN_REFRESH_SKEW_SECONDS):
            return None, True  # 已过期
        else:
            _TOKEN_MEMORY_CACHE = {"token": token, "expire": expire}
            return token, False  # 有效
    except Exception:
        return None, True


def cache_token(token: str):
    """缓存 token"""
    global _TOKEN_MEMORY_CACHE
    auth = get_cached_auth()
    expire = datetime.now() + timedelta(seconds=TOKEN_VALID_SECONDS)
    auth.update({
        'authtoken': token,
        'authtoken_expire': expire.strftime('%Y-%m-%d %H:%M:%S'),
    })
    save_auth(auth)
    _TOKEN_MEMORY_CACHE = {"token": token, "expire": expire}


def fetch_new_token() -> str:
    """获取新 token（敏感 userKey 通过 HTTPS POST body 传递）。"""
    user_key = get_user_key()
    if not user_key:
        return ""

    try:
        data = {"userKey": user_key}
        if REQUEST_CHANNEL:
            data["requestChannel"] = REQUEST_CHANNEL
        resp_data = http_post_form(
            f"{BASE_URL}/webservice/foreign_getAuthtoken.htm",
            data=data,
            include_channel=False,
        )
        token = resp_data.get("result") if isinstance(resp_data, dict) else None
        if token:
            cache_token(token)
        return token or ""
    except Exception:
        return ""


def ensure_token(emit_error: bool = True) -> str:
    """
    确保有有效 token（缓存未过期直接用，否则刷新）

    Returns:
        有效的 authtoken 字符串

    Raises:
        SystemExit: 无 userKey 或获取 token 失败时输出 authentication_required 并退出
    """
    user_key = get_user_key()
    if not user_key:
        response = {
            "code": "10500",
            "msg": "未找到 CXDA_USER_KEY，请先通过 auth.py 完成认证",
            "status": "authentication_required",
            "data": "",
        }
        if emit_error:
            output_json(response)
            sys.exit(1)
        raise AuthenticationRequiredError(response)

    token, need_refresh = get_cached_token()
    if need_refresh:
        token = fetch_new_token()
        if not token:
            response = {
                "code": "10500",
                "msg": "获取 authToken 失败，请重新完成认证后重试",
                "status": "authentication_required",
                "data": "",
            }
            if emit_error:
                output_json(response)
                sys.exit(1)
            raise AuthenticationRequiredError(response)

    return token


# ── HTTP 请求封装 ─────────────────────────────────────────────────────

_MAX_GZIP_DECOMPRESSED = 32 * 1024 * 1024
_MAX_ENCODED_RESPONSE = 64 * 1024 * 1024


def _validate_official_url(url: str):
    """SSRF 防护：只允许官方 HTTPS 域名及 /cxda/ 下的接口路径。"""
    from urllib.parse import unquote, urlparse

    base = urlparse(BASE_URL)
    parsed = urlparse(url) if isinstance(url, str) else None
    if not parsed:
        raise ValueError("拒绝非白名单 URL 请求")
    try:
        parsed_port = parsed.port
        base_port = base.port
    except ValueError:
        raise ValueError("拒绝非白名单 URL 请求")
    # urlparse 对省略端口的 HTTPS 返回 None；显式 :443 与省略 :443 应等价，
    # 否则合法官方 URL 会因书写方式不同被误拒绝。
    parsed_effective_port = (
        parsed_port if parsed_port is not None
        else (443 if parsed.scheme.lower() == "https" else 80)
    )
    base_effective_port = (
        base_port if base_port is not None
        else (443 if base.scheme.lower() == "https" else 80)
    )
    raw_path = (parsed.path or "").replace("\\", "/")
    norm_path = posixpath.normpath(unquote(raw_path))
    if (
        parsed.scheme.lower() != base.scheme.lower()
        or parsed.hostname is None
        or parsed.hostname.lower() != (base.hostname or "").lower()
        or parsed_effective_port != base_effective_port
        or parsed.username is not None
        or parsed.password is not None
        or not norm_path.startswith((base.path or "") + "/")
        or norm_path.startswith("//")
    ):
        raise ValueError("拒绝非白名单 URL 请求（仅允许官方 cxdata 接口路径）")


def _decode_response(resp) -> dict:
    """解码 gzip+base64 响应，并限制解压后的最大体积。"""
    import io

    text = resp.text.strip() if isinstance(resp.text, str) else ""
    if len(text) > _MAX_ENCODED_RESPONSE:
        raise RuntimeError("响应体过大")

    try:
        # 兼容 MIME/代理可能插入的普通换行，同时继续由 validate=True 拒绝
        # 非 Base64 字符；不使用 validate=False，避免静默吞掉任意垃圾字节。
        compact_text = text.translate(str.maketrans("", "", " \t\r\n"))
        raw = base64.b64decode(compact_text, validate=True)
        with gzip.GzipFile(fileobj=io.BytesIO(raw), mode="rb") as gz:
            chunks = []
            total = 0
            while True:
                chunk = gz.read(min(65536, _MAX_GZIP_DECOMPRESSED - total + 1))
                if not chunk:
                    break
                total += len(chunk)
                if total > _MAX_GZIP_DECOMPRESSED:
                    raise RuntimeError("响应体过大，拒绝解压")
                chunks.append(chunk)
        return json.loads(b"".join(chunks).decode("utf-8"))
    except RuntimeError:
        raise
    except Exception:
        try:
            return json.loads(text)
        except Exception:
            raise RuntimeError("响应解析失败")


def _decode_json_response(resp) -> dict:
    """解析普通 JSON 响应，并限制响应体最大体积。"""
    text = resp.text.strip() if isinstance(resp.text, str) else ""
    if len(text) > _MAX_ENCODED_RESPONSE:
        raise RuntimeError("响应体过大")
    try:
        return json.loads(text)
    except Exception:
        raise RuntimeError("响应解析失败")


def http_get(url: str, params: dict = None, include_channel: bool = True,
             operation: str = None) -> dict:
    """
    统一 HTTP GET 请求（含 gzip + base64 解码及静默审计记录）

    Args:
        url: 完整请求 URL
        params: 查询参数
        include_channel: 是否自动附加 requestChannel 参数（默认 True）
        operation: 可选的审计操作名

    Returns:
        解析后的 JSON 数据字典
    """
    import requests

    _validate_official_url(url)
    params = dict(params or {})
    if include_channel and REQUEST_CHANNEL:
        params["requestChannel"] = REQUEST_CHANNEL

    request_params = dict(params)
    full_response = _is_full_response_endpoint(url)
    try:
        resp = requests.get(
            url,
            params=request_params,
            headers=HEADERS,
            proxies=PROXIES,
            timeout=30,
            verify=True,
            allow_redirects=False,
        )
    except Exception as exc:
        log_api_call(
            "GET", url, request_params, operation=operation,
            success=False, error_type=type(exc).__name__,
        )
        raise RuntimeError("网络请求失败")
    try:
        data = _decode_response(resp)
    except Exception as exc:
        if full_response:
            log_api_call(
                "GET", url, request_params, operation=operation,
                success=False, error_type=type(exc).__name__,
                response=getattr(resp, "text", ""), include_response=True,
            )
        else:
            log_api_call(
                "GET", url, request_params, operation=operation,
                success=False, error_type=type(exc).__name__,
            )
        raise
    response_code = data.get("code") if isinstance(data, dict) else None
    if full_response:
        log_api_call(
            "GET", url, request_params, operation=operation,
            success=True, response_code=response_code,
            response=data, include_response=True,
        )
    else:
        log_api_call(
            "GET", url, request_params, operation=operation,
            success=True, response_code=response_code,
        )
    return data


def http_post_form(url: str, data: dict = None, include_channel: bool = True,
                   operation: str = None) -> dict:
    """统一 HTTPS POST 表单请求，解析普通 JSON 并静默记录调用。"""
    import requests

    _validate_official_url(url)
    form = dict(data or {})
    if include_channel and REQUEST_CHANNEL:
        form["requestChannel"] = REQUEST_CHANNEL
    full_response = _is_full_response_endpoint(url)
    try:
        resp = requests.post(
            url,
            data=form,
            headers={
                **HEADERS,
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            },
            proxies=PROXIES,
            timeout=30,
            verify=True,
            allow_redirects=False,
        )
    except Exception as exc:
        log_api_call(
            "POST", url, form, operation=operation,
            success=False, error_type=type(exc).__name__,
        )
        raise RuntimeError("网络请求失败")
    try:
        response_data = _decode_json_response(resp)
    except Exception as exc:
        if full_response:
            log_api_call(
                "POST", url, form, operation=operation,
                success=False, error_type=type(exc).__name__,
                response=getattr(resp, "text", ""), include_response=True,
            )
        else:
            log_api_call(
                "POST", url, form, operation=operation,
                success=False, error_type=type(exc).__name__,
            )
        raise
    response_code = response_data.get("code") if isinstance(response_data, dict) else None
    if full_response:
        log_api_call(
            "POST", url, form, operation=operation,
            success=True, response_code=response_code,
            response=response_data, include_response=True,
        )
    else:
        log_api_call(
            "POST", url, form, operation=operation,
            success=True, response_code=response_code,
        )
    return response_data


# ── 输出工具 ──────────────────────────────────────────────────────────

def output_json(data, indent=4):
    """统一 JSON 输出"""
    print(json.dumps(data, indent=indent, ensure_ascii=False))


def output_error(msg):
    """统一错误输出"""
    print(json.dumps({"error": msg, "status": "failed"}, ensure_ascii=False))
