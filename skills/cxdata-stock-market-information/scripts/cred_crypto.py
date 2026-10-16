# -*- coding: utf-8 -*-
"""
凭证加解密模块（兼容历史明文与 CXDA_USER_KEY / authtoken 的 ENCv1 密文）。

设计：
- 使用 cryptography 库的 Fernet 加解密凭证（AES128-CBC + HMAC）。
- 密钥由本机特征（hostname + 登录用户名 + machine-id）**加上一份用户私有 pepper 文件**
  经 PBKDF2HMAC 派生。pepper 存放于 ~/.cxda-cache/.cred_pepper.bin，
  权限 0o600（O_NOFOLLOW + O_EXCL 首次创建，仅当前用户可读）。
  引入 pepper 之后，同机其他用户即使能读到密文文件、也知道 host/user/machine-id
  这些公开属性，因为无法读到 pepper 文件本身，无法派生出正确密钥（缓解水平越权）。
- common.save_auth 根据已有 CXDA_USER_KEY 的存储形态决定是否加密：历史明文
  保持明文，已有密文保持密文，尚无 userKey 的新用户使用密文。
- get_user_key/get_cached_token 透明解密 ENCv1，并兼容读取历史明文。

依赖：加解密 ENCv1 凭证需要 cryptography；部署环境须按父目录 requirements.txt
安装依赖。

注意：本机特征派生只能防「肉眼直读」和「文件被拷走离线破解」，
无法防御已获得本机同用户执行权限的攻击者（那种场景下任何本地加密都无意义）。
"""

import base64
import json
import os
import platform
import secrets
import socket
import stat as _stat
from functools import lru_cache
from pathlib import Path
from typing import Tuple

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# 固定 salt（公开不影响安全：PBKDF2 的强度依赖迭代次数 + 特征输入的不可预测性）
_SALT = b"cxda-cred-v1-salt-do-not-change"
# 标记前缀，用于区分密文与明文（明文凭证不会以这个开头）
ENC_PREFIX = "ENCv1:"
_ENC_PREFIX = ENC_PREFIX  # 保留旧模块内部名称，兼容已有调用方
# Pepper 文件路径与大小
_PEPPER_FILENAME = ".cred_pepper.bin"
_PEPPER_SIZE = 32


def _pepper_dir() -> Path:
    """pepper 文件所在目录；拒绝软链/非目录节点并固定为 0700。"""
    d = Path.home() / ".cxda-cache"
    try:
        st = os.lstat(d)
        if _stat.S_ISLNK(st.st_mode):
            raise RuntimeError("拒绝凭证目录为符号链接: {}".format(d))
        if not _stat.S_ISDIR(st.st_mode):
            raise RuntimeError("拒绝凭证目录为非目录节点: {}".format(d))
    except FileNotFoundError:
        d.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        os.chmod(d, 0o700)
    except OSError:
        pass
    return d


def _get_or_create_pepper() -> bytes:
    """获取用户私有 pepper（不存在则用 secrets 生成，0o600 权限，缓解水平越权）。

    - O_NOFOLLOW：目标若为 symlink 则直接失败，避免攻击者预置软链把 pepper 写到别处。
    - O_EXCL + O_CREAT：首次创建时原子；若并发创建导致 EEXIST，退化为读取模式。
    - lstat 校验：读取路径必须是普通文件（而非软链/目录），否则拒绝。
    """
    pepper_path = _pepper_dir() / _PEPPER_FILENAME

    # 已存在：lstat 校验后读取
    if pepper_path.exists() or pepper_path.is_symlink():
        try:
            st = os.lstat(pepper_path)
        except OSError as e:
            raise RuntimeError(f"读取 pepper 失败（lstat）: {e}")
        if _stat.S_ISLNK(st.st_mode):
            raise RuntimeError(f"拒绝 pepper 为符号链接: {pepper_path}")
        if not _stat.S_ISREG(st.st_mode):
            raise RuntimeError(f"拒绝 pepper 非普通文件: {pepper_path}")

        flags = os.O_RDONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        if hasattr(os, "O_NONBLOCK"):
            flags |= os.O_NONBLOCK
        if hasattr(os, "O_BINARY"):
            flags |= os.O_BINARY
        fd = os.open(pepper_path, flags)
        try:
            opened_stat = os.fstat(fd)
            if not _stat.S_ISREG(opened_stat.st_mode):
                raise RuntimeError("拒绝 pepper 非普通文件: {}".format(pepper_path))
            if hasattr(os, "fchmod"):
                try:
                    os.fchmod(fd, 0o600)
                except OSError:
                    pass
            chunks = []
            remaining = _PEPPER_SIZE * 4
            while remaining > 0:
                chunk = os.read(fd, remaining)
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            data = b"".join(chunks)
        finally:
            os.close(fd)
        if len(data) < _PEPPER_SIZE:
            raise RuntimeError(f"pepper 文件长度异常: {len(data)}")
        return data[:_PEPPER_SIZE]

    # 首次创建：secrets.token_bytes + O_EXCL + O_NOFOLLOW + 0o600
    pepper = secrets.token_bytes(_PEPPER_SIZE)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    try:
        fd = os.open(pepper_path, flags, 0o600)
    except FileExistsError:
        # 并发创建：递归再走一次读路径（此次分支必然进入 exists 分支）
        return _get_or_create_pepper()
    try:
        offset = 0
        while offset < _PEPPER_SIZE:
            written = os.write(fd, pepper[offset:])
            if written <= 0:
                raise RuntimeError(f"pepper 写入不完整: {offset}/{_PEPPER_SIZE}")
            offset += written
    finally:
        os.close(fd)
    # 双保险：确保 0o600（POSIX），Windows 上 chmod 会被忽略但 %USERPROFILE% 默认独占 ACL
    try:
        os.chmod(pepper_path, 0o600)
    except OSError:
        pass
    return pepper


def _get_effective_username() -> str:
    """获取进程真实所属用户名（缓解水平越权：拒绝 LOGNAME/USER 等环境变量污染）。

    - POSIX：走 pwd.getpwuid(os.getuid())，直接从口令数据库按 EUID 反查，
      不受 LOGNAME/USER/LNAME 影响。
    - Windows：走 GetUserNameW WinAPI，从访问令牌读取，不受 USERNAME 环境变量影响。
    任一环节失败视为无法获取有效用户名，返回空串（上层将拒绝派生密钥）。
    """
    if os.name == "posix":
        try:
            import pwd
            return pwd.getpwuid(os.getuid()).pw_name or ""
        except (KeyError, ImportError, OSError):
            return ""

    if platform.system() == "Windows":
        try:
            import ctypes
            from ctypes import wintypes
            get_user_name_w = ctypes.windll.advapi32.GetUserNameW
            size = wintypes.DWORD(257)
            buf = ctypes.create_unicode_buffer(size.value)
            if get_user_name_w(buf, ctypes.byref(size)):
                return buf.value or ""
        except Exception:
            return ""

    return ""


def _get_machine_id() -> str:
    """获取机器唯一标识，增加密钥派生材料不可预测性。

    优先级：
    1. macOS IOPlatformUUID（ioreg）
    2. Linux /etc/machine-id 或 /var/lib/dbus/machine-id
    3. Windows MachineGuid 注册表
    4. 回退空串（仍依赖 hostname+user）
    """
    import subprocess as _sp

    system = platform.system()

    try:
        if system == "Darwin":
            result = _sp.run(
                ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                capture_output=True, text=True, timeout=5,
            )
            for line in result.stdout.splitlines():
                if "IOPlatformUUID" in line:
                    parts = line.split('"')
                    if len(parts) >= 4:
                        return parts[-2].strip()
        elif system == "Linux":
            for path in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
                p = Path(path)
                if p.exists():
                    return p.read_text().strip()[:64]
        elif system == "Windows":
            result = _sp.run(
                ["reg", "query",
                 r"HKLM\SOFTWARE\Microsoft\Cryptography",
                 "/v", "MachineGuid"],
                capture_output=True, text=True, timeout=5,
            )
            for line in result.stdout.splitlines():
                if "MachineGuid" in line:
                    return line.split()[-1].strip()
    except Exception:
        pass

    return ""


@lru_cache(maxsize=1)
def _derive_key() -> bytes:
    r"""由本机特征 + 用户私有 pepper 派生 Fernet 密钥（base64 编码的 32 字节）。

    密钥材料 = 结构化 JSON({host, user, machine_id}) + 用户私有 pepper。
    - JSON 序列化 + sort_keys + separators=(",",":")：避免分隔符碰撞
      （旧版 f"{host}|{user}|{machine_id}"，若字段本身含 `|`，
      不同 (host,user,mid) 三元组可能拼出同一 material，引发跨用户 key 碰撞
      → 水平越权），JSON 转义 `"` 和 `\` 使不同输入必然对应不同序列化结果。
    - user 走 _get_effective_username（不受环境变量污染），杜绝伪造。
    - pepper 32 字节 secure random，落盘 0o600（缓解仅依赖公开系统属性的水平越权）。
    严格要求三项特征均非空，任一缺失都拒绝派生，防止 material 退化为可预测低熵输入。
    """
    user = _get_effective_username()
    host = socket.gethostname() or ""
    machine_id = _get_machine_id()
    if not host or not user or not machine_id:
        raise RuntimeError(
            "无法获取足够的机器特征（hostname/username/machine-id 至少一项为空），"
            "拒绝生成低熵密钥。请检查系统主机名、登录用户以及 machine-id 配置。"
        )
    pepper = _get_or_create_pepper()
    identity = json.dumps(
        {"host": host, "user": user, "machine_id": machine_id},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    # pepper 独立成段附加，避免 identity 中出现 pepper 字节的边界歧义
    material = identity + b"\x00pepper=" + pepper
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_SALT,
        iterations=200_000,
    )
    return base64.urlsafe_b64encode(kdf.derive(material))


def encrypt(plaintext: str) -> str:
    """加密明文，返回带 ENCv1 前缀的密文；空串原样返回。"""
    if not plaintext:
        return plaintext
    f = Fernet(_derive_key())
    token = f.encrypt(plaintext.encode("utf-8"))
    return _ENC_PREFIX + token.decode("ascii")


def decrypt(stored: str) -> Tuple[str, bool]:
    """解密。若 stored 是明文（无前缀），原样返回并标记其明文形态。

    返回 (明文, is_plaintext)。是否迁移由调用方决定；共享认证凭证不迁移。
    """
    if not stored:
        return "", False
    if not stored.startswith(_ENC_PREFIX):
        # 老明文数据：原样返回，由调用方决定是否迁移
        return stored, True
    try:
        token = stored[len(_ENC_PREFIX):].encode("ascii")
        f = Fernet(_derive_key())
        return f.decrypt(token).decode("utf-8"), False
    except (InvalidToken, ValueError, UnicodeError):
        return "", False
    except Exception:
        return "", False
