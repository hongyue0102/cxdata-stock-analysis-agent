# -*- coding: utf-8 -*-
"""
凭证加解密模块（缓解风险2：CXDA_USER_KEY 明文存储）。

设计：
- 使用 cryptography 库的 Fernet 对称加密（AES128-CBC + HMAC，密码学安全）。
- 密钥由本机特征（hostname + 登录用户名 + 固定 salt）经 PBKDF2HMAC 派生，
  不落盘、无需管理 key 文件。换机器/换用户则密钥变化，老密文失效（需重新鉴权，可接受）。
- get_user_key/set_user_key 透明调用本模块；兼容老明文数据（解密失败时按明文返回并标记需迁移）。

注意：本机特征派生只能防「肉眼直读」和「文件被拷走离线破解」，
无法防御已获得本机同用户执行权限的攻击者（那种场景下任何本地加密都无意义，
需配合风险6的文件权限 0o600 才构成完整防护）。
"""

import base64
import getpass
import os
import socket

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# 固定 salt（公开不影响安全：PBKDF2 的强度依赖迭代次数 + 特征输入的不可预测性）
_SALT = b"cxda-cred-v1-salt-do-not-change"
# 标记前缀，用于区分密文与明文（明文凭证不会以这个开头）
_ENC_PREFIX = "ENCv1:"


def _get_machine_id() -> str:
    """获取机器唯一标识，增加密钥派生材料不可预测性（缓解火山风险3：硬编码凭证）。

    优先级：
    1. macOS IOPlatformUUID（ioreg）
    2. Linux /etc/machine-id 或 /var/lib/dbus/machine-id
    3. Windows MachineGuid 注册表
    4. 回退空串（仍依赖 hostname+user，与旧版一致）
    """
    import subprocess as _sp
    import platform

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
                p = Path(path) if "Path" in dir() else __import__("pathlib").Path(path)
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


def _derive_key() -> bytes:
    """由本机特征派生 Fernet 密钥（base64 编码的 32 字节）。

    密钥材料 = hostname + username + 机器唯一标识（machine-id），
    增加 attack surface 门槛——攻击者不仅需要知道 hostname/username，
    还需要获取 machine-id 才能离线派生密钥（缓解火山风险3：硬编码凭证）。
    """
    # 机器特征：主机名 + 登录用户名（getpass 在无 tty 环境可能抛错，兜底用环境变量）
    try:
        user = getpass.getuser() or os.environ.get("USER", "") or os.environ.get("USERNAME", "")
    except Exception:
        user = os.environ.get("USER", "") or os.environ.get("USERNAME", "")
    host = socket.gethostname() or ""
    # 退化检测：host 与 user 均空时 material 会退化成固定 b"|"，密钥可预测，
    # 攻击者可解密所有凭证。此时拒绝派生，强制环境正确配置 hostname/user。
    if not host and not user:
        raise RuntimeError(
            "无法获取机器特征（hostname 与用户名均为空），拒绝生成可预测的弱密钥。"
            "请配置 HOSTNAME/USER 环境变量后重试。"
        )
    machine_id = _get_machine_id()
    material = f"{host}|{user}|{machine_id}".encode("utf-8")
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_SALT,
        iterations=200_000,
    )
    return base64.urlsafe_b64encode(kdf.derive(material))


def encrypt(plaintext: str) -> str:
    """加密明文，返回带前缀的密文字符串。空串原样返回。"""
    if not plaintext:
        return plaintext
    f = Fernet(_derive_key())
    token = f.encrypt(plaintext.encode("utf-8"))
    return _ENC_PREFIX + token.decode("ascii")


def decrypt(stored: str) -> str:
    """解密。若 stored 是明文（无前缀或解密失败），原样返回并交给调用方迁移。

    返回 (明文, is_plaintext_needs_migration)。
    """
    if not stored:
        return "", False
    if not stored.startswith(_ENC_PREFIX):
        # 老明文数据：原样返回，标记需迁移加密
        return stored, True
    token = stored[len(_ENC_PREFIX):].encode("ascii")
    try:
        f = Fernet(_derive_key())
        return f.decrypt(token).decode("utf-8"), False
    except (InvalidToken, Exception):
        # 密钥已变（换机器/换用户）或数据损坏：视为无法解密
        return "", False


def is_encrypted(stored: str) -> bool:
    """判断 stored 是否为加密形态。"""
    return bool(stored) and stored.startswith(_ENC_PREFIX)
