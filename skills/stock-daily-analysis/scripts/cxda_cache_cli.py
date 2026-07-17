#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CXDA Skill 缓存管理 CLI 工具

提供公域/私域数据隔离、认证数据管理能力。
通过环境变量或自动探测识别工作空间。

目录结构: {workspace}/
  .shared/    - 公域数据（跨Skill共享，如 cxda_auth.json）
  {skill}/    - 私域数据（data/ cache/ config/）
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# fcntl 仅 Unix 可用，Windows 下跳过文件锁
try:
    import fcntl
    _HAS_FCNTL = True
except ImportError:
    _HAS_FCNTL = False


# ── 工作空间探测 ──────────────────────────────────────────────────────

def _ensure_dir_not_symlink(path: Path) -> None:
    """确保目录不是符号链接（缓解 workspace 指向系统目录的 chmod 攻击）。

    攻击模型：攻击者预置 `ln -s /etc ~/.cxda-cache`，随后本模块 mkdir/chmod 0o700
    会作用到 /etc，造成 DoS/越权。用 lstat 显式检测 symlink：
      - 若已存在且是 symlink → 拒绝并抛错（不做任何 mkdir/chmod）；
      - 若已存在但类型不是目录 → 也拒绝（避免 chmod 到普通文件）；
      - 若不存在 → 不动，交给调用方 mkdir。
    """
    try:
        st = os.lstat(path)
    except FileNotFoundError:
        return
    import stat as _stat
    if _stat.S_ISLNK(st.st_mode):
        raise RuntimeError(f"拒绝 workspace {path} 为符号链接（缓解 symlink 攻击）")
    if not _stat.S_ISDIR(st.st_mode):
        raise RuntimeError(f"拒绝 workspace {path} 非目录（存在非目录节点）")


def _validate_workspace_path(workspace: Path, source: str = "") -> Path:
    """校验 workspace 路径合理性（缓解环境变量路径遍历 + symlink 攻击）。

    拒绝系统关键目录、要求在用户家目录下，否则回退默认 ~/.cxda-cache。
    回退路径同样走 _ensure_dir_not_symlink 检测，避免默认路径被预置为软链。

    安全说明：SYSTEM_CRITICAL 不再包含 /root。因为 /root 是 root 用户的默认家目录，
    默认回退路径 ~/.cxda-cache 对 root 用户即 /root/.cxda-cache，将 /root 列为关键目录
    与"要求在家目录下"的规则直接冲突，会让 root 用户永远拿不到工作空间。
    /root 的访问隔离由文件系统权限（默认 0o700）+ 本模块写入使用的 0o600 保证，
    不需要在此重复拦截。
    """
    SYSTEM_CRITICAL = (
        "/etc", "/bin", "/sbin", "/usr", "/boot", "/dev", "/proc", "/sys",
        "/var", "/lib", "/lib64", "/Library", "/System",
    )
    home = Path.home().resolve()
    resolved = workspace.resolve()
    resolved_str = str(resolved)
    for crit in SYSTEM_CRITICAL:
        if resolved_str == crit or resolved_str.startswith(crit + os.sep):
            sys.stderr.write(f"[WARN] 拒绝 workspace {resolved_str}（系统关键目录），回退默认。来源: {source}\n")
            fallback = Path.home() / ".cxda-cache"
            _ensure_dir_not_symlink(fallback)
            return fallback
    if not resolved_str.startswith(str(home) + os.sep) and resolved_str != str(home):
        sys.stderr.write(f"[WARN] 拒绝 workspace {resolved_str}（不在用户家目录下），回退默认。来源: {source}\n")
        fallback = Path.home() / ".cxda-cache"
        _ensure_dir_not_symlink(fallback)
        return fallback
    _ensure_dir_not_symlink(resolved)
    return resolved


def _secure_write_text(file_path: Path, content: str) -> None:
    """以 0o600 权限写文本文件（缓解凭证文件默认 0o644 可被同机用户读取）。保留 fcntl 文件锁。

    O_NOFOLLOW（缓解 TOCTOU 与 symlink race）：目标若已是符号链接则 open 直接失败，
    杜绝攻击者在 check 与 use 之间把文件替换为指向敏感位置的软链。
    """
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    fd = os.open(file_path, flags, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        if _HAS_FCNTL:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            f.write(content)
        finally:
            if _HAS_FCNTL:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def _secure_read_text(file_path: Path) -> str:
    """以 O_NOFOLLOW 读取文本文件（缓解 symlink race，配合 _secure_write_text 使用）。

    Path.read_text() 会跟随符号链接，若目录权限被误配，攻击者可在 check-exists 与
    实际读取之间把文件替换为软链，导致越权读取敏感文件。用 os.open + O_NOFOLLOW
    从 fd 直接读，若目标已成 symlink 则直接失败。
    """
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    fd = os.open(file_path, flags)
    try:
        chunks = []
        while True:
            buf = os.read(fd, 65536)
            if not buf:
                break
            chunks.append(buf)
        return b"".join(chunks).decode("utf-8")
    finally:
        os.close(fd)


def detect_workspace() -> Path:
    """
    自动检测工作空间路径

    优先级：
    1. CXDA_CACHE_WORKSPACE 环境变量
    2. CLAUDE_WORKSPACE 环境变量
    3. 默认 ~/.cxda-cache

    所有路径（含默认值）都经 _validate_workspace_path 校验，避免 symlink 攻击
    （攻击者预置 `ln -s /etc ~/.cxda-cache` 后，mkdir/chmod 会作用到 /etc）。
    """
    for env_var in ["CXDA_CACHE_WORKSPACE", "CLAUDE_WORKSPACE"]:
        path = os.environ.get(env_var)
        if path:
            workspace = _validate_workspace_path(Path(path).expanduser(), source=env_var)
            _ensure_dir_not_symlink(workspace)
            workspace.mkdir(parents=True, exist_ok=True, mode=0o700)
            try:
                os.chmod(workspace, 0o700)
            except OSError:
                pass
            return workspace

    # 默认路径也走 _validate_workspace_path，确保 lstat 检查不被跳过
    default = Path.home() / ".cxda-cache"
    workspace = _validate_workspace_path(default, source="default")
    _ensure_dir_not_symlink(workspace)
    workspace.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        os.chmod(workspace, 0o700)
    except OSError:
        pass
    return workspace


# ── 缓存管理器 ────────────────────────────────────────────────────────

class CacheManager:
    """CXDA Skill 缓存管理器"""

    def __init__(self, workspace: Path = None):
        self.workspace = workspace or detect_workspace()
        self._ensure_structure()

    def _ensure_structure(self):
        """确保基础目录结构存在"""
        shared_dir = self.workspace / ".shared"
        shared_dir.mkdir(parents=True, exist_ok=True, mode=0o700)

    # ==================== 公域数据管理 ====================

    def _get_shared_path(self, filename: str) -> Path:
        """获取公域文件路径（含路径遍历防护）"""
        shared_dir = self.workspace / ".shared"
        shared_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        # resolve 后校验仍在 shared_dir 内，拒绝 ../ 逃逸
        target = (shared_dir / filename).resolve()
        try:
            target.relative_to(shared_dir.resolve())
        except ValueError:
            raise ValueError(f"非法路径（拒绝路径遍历）: {filename}")
        return target

    # 公域文件名白名单：仅允许字母/数字/下划线/点/连字符，禁止 / \ .. 等分隔与逃逸字符
    _SHARED_NAME_RE = __import__("re").compile(r"^[A-Za-z0-9_.\-]+$")
    # 纯点名（.、..、... 等）额外拒绝：仅靠字符白名单会漏掉 ".."（不含分隔符仍可回溯父目录）
    _ALL_DOTS_RE = __import__("re").compile(r"^\.+$")

    @classmethod
    def _validate_shared_filename(cls, filename: str) -> str:
        """校验公域文件名，拒绝路径遍历/注入字符（用于 delete 等词法路径场景）。

        双重防护：字符白名单 + 纯点名拒绝（`.`、`..`、`...` 均能定位特殊目录）。
        """
        if not isinstance(filename, str) or not filename or not cls._SHARED_NAME_RE.match(filename) or ".." in filename:
            raise ValueError(f"非法公域文件名（拒绝路径遍历）: {filename!r}")
        if cls._ALL_DOTS_RE.match(filename):
            raise ValueError(f"非法公域文件名（拒绝纯点名）: {filename!r}")
        return filename

    def _get_shared_path_lexical(self, filename: str) -> Path:
        """获取公域文件的词法路径（不 resolve，缓解 delete 跟随 symlink）。

        用途：delete 操作必须删除软链本身而非其目标。resolve 会展开 symlink，
        导致 unlink 删掉链接指向的真实文件（可能位于共享目录外）。这里直接做
        词法 join，配合白名单已阻断的 `..` 和 `/` 保证不会逃逸。
        """
        self._validate_shared_filename(filename)
        shared_dir = self.workspace / ".shared"
        shared_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        return shared_dir / filename

    def shared_read(self, filename: str) -> dict:
        """读取公域文件（O_NOFOLLOW 拒绝符号链接，缓解 symlink race）。"""
        file_path = self._get_shared_path(filename)

        if not file_path.exists():
            return {"success": False, "error": f"文件不存在: {file_path}"}

        try:
            content = _secure_read_text(file_path)
            return {"success": True, "content": content, "path": str(file_path)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def shared_write(self, filename: str, content: str) -> dict:
        """写入公域文件（权限 0o600，带文件锁保护）"""
        file_path = self._get_shared_path(filename)

        try:
            _secure_write_text(file_path, content)
            return {"success": True, "path": str(file_path), "file": filename}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def shared_append(self, filename: str, content: str) -> dict:
        """追加公域文件，O_APPEND + O_NOFOLLOW + 单次 os.write（缓解 symlink race，权限 0o600）。"""
        file_path = self._get_shared_path(filename)

        try:
            data = content.encode("utf-8")
            flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            if hasattr(os, "O_BINARY"):
                flags |= os.O_BINARY

            fd = os.open(file_path, flags, 0o600)
            try:
                written = os.write(fd, data)
                if written != len(data):
                    raise OSError(f"append write incomplete: {written}/{len(data)} bytes")
            finally:
                os.close(fd)

            return {
                "success": True,
                "path": str(file_path),
                "file": filename,
                "operation": "append"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def shared_delete(self, filename: str) -> dict:
        """删除公域文件本身（若为符号链接，只删软链、不跟随目标）。

        安全（缓解 symlink 误删）：使用 lexical path（不 resolve），配合白名单
        拒绝 `..`、`/`；用 os.lstat 判断类型；用 os.unlink 对路径直接操作，
        不跟随 symlink（Path.unlink / os.unlink 本身不 follow symlink 对文件而言，
        但为防歧义，路径不 resolve 是关键）。
        """
        try:
            file_path = self._get_shared_path_lexical(filename)
        except ValueError as e:
            return {"success": False, "error": str(e)}

        # lstat：文件不存在或为其它异常类型，明确报错
        try:
            os.lstat(file_path)
        except FileNotFoundError:
            return {"success": False, "error": f"文件不存在: {file_path}"}
        except OSError as e:
            return {"success": False, "error": f"lstat 失败: {e}"}

        try:
            # os.unlink 对路径直接操作，若路径本身是 symlink 则删软链（不跟随）
            os.unlink(file_path)
            return {"success": True, "path": str(file_path), "file": filename}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def shared_list(self) -> dict:
        """列出所有公域文件"""
        shared_dir = self.workspace / ".shared"

        if not shared_dir.exists():
            return {"success": True, "files": []}

        try:
            files = [
                {
                    "name": f.name,
                    "size": f.stat().st_size,
                    "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat()
                }
                for f in shared_dir.iterdir() if f.is_file()
            ]
            return {"success": True, "files": files}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ==================== 认证数据管理（公域） ====================

    AUTH_FILE = "cxda_auth.json"

    def auth_get(self) -> dict:
        """获取认证数据"""
        result = self.shared_read(self.AUTH_FILE)

        if not result.get("success"):
            if "不存在" in result.get("error", ""):
                return {"success": True, "data": {}, "found": False}
            return result

        try:
            data = json.loads(result["content"])
            return {"success": True, "data": data, "found": bool(data)}
        except json.JSONDecodeError as e:
            return {"success": False, "error": f"JSON解析错误: {e}"}

    def auth_set(self, auth_data: dict) -> dict:
        """设置认证数据（合并更新）"""
        # 读取现有数据
        existing = self.auth_get()
        data = existing.get("data", {}) if existing.get("success") else {}

        # 合并新数据
        data.update(auth_data)
        data["_updated_at"] = datetime.now().isoformat()

        # 写回
        content = json.dumps(data, ensure_ascii=False, indent=2)
        return self.shared_write(self.AUTH_FILE, content)

    def auth_delete(self, key: str = None) -> dict:
        """删除认证数据（key=None时清空所有）"""
        if key is None:
            return self.shared_write(self.AUTH_FILE, "{}")

        existing = self.auth_get()
        if not existing.get("success"):
            return existing

        data = existing.get("data", {})
        if key in data:
            del data[key]
            content = json.dumps(data, ensure_ascii=False, indent=2)
            return self.shared_write(self.AUTH_FILE, content)

        return {"success": False, "error": f"键不存在: {key}"}

    # ==================== 私域数据管理 ====================

    SUBDIR_TYPES = {
        "data": "持久化业务数据",
        "cache": "临时缓存",
        "config": "配置文件",
    }

    # skill_name / filename 白名单：仅允许字母数字下划线连字符点，
    # 从源头拒绝 ../ 、/ 、URL编码(%2f) 等路径分隔与逃逸字符（缓解路径遍历）
    _SAFE_NAME_RE = __import__("re").compile(r"^[A-Za-z0-9_.\-]+$")
    # 私域也需要拒绝纯点名（.、..、...）——字符白名单不足以拦 ".."
    _SAFE_ALL_DOTS_RE = __import__("re").compile(r"^\.+$")

    @classmethod
    def _validate_skill_name(cls, skill_name: str) -> str:
        """校验 skill_name，拦截路径遍历（../）与注入字符。所有接收 skill_name 的入口统一调用。

        双重防护：字符白名单（拒绝分隔符）+ 纯点名拒绝（拒绝 . / .. / ... 特殊目录）。
        """
        if not isinstance(skill_name, str) or not skill_name or not cls._SAFE_NAME_RE.match(skill_name) or ".." in skill_name:
            raise ValueError(f"非法 skill 名称（拒绝路径遍历）: {skill_name!r}")
        if cls._SAFE_ALL_DOTS_RE.match(skill_name):
            raise ValueError(f"非法 skill 名称（拒绝纯点名）: {skill_name!r}")
        return skill_name

    @classmethod
    def _validate_private_filename(cls, filename: str) -> str:
        """校验私域文件名，同 skill_name 双重防护。"""
        if not isinstance(filename, str) or not filename or not cls._SAFE_NAME_RE.match(filename) or ".." in filename:
            raise ValueError(f"非法 file 名称（拒绝路径遍历）: {filename!r}")
        if cls._SAFE_ALL_DOTS_RE.match(filename):
            raise ValueError(f"非法 file 名称（拒绝纯点名）: {filename!r}")
        return filename


    def _get_skill_path(self, skill_name: str, subdir: str = "data") -> Path:
        """获取 Skill 目录路径（含 skill_name 路径遍历防护）。"""
        self._validate_skill_name(skill_name)
        if subdir not in self.SUBDIR_TYPES:
            raise ValueError(f"未知子目录类型: {subdir}。可用: {list(self.SUBDIR_TYPES.keys())}")
        skill_path = self.workspace / skill_name / subdir
        skill_path.mkdir(parents=True, exist_ok=True, mode=0o700)
        return skill_path

    def _get_file_path(self, skill_name: str, filename: str, subdir: str = "data") -> Path:
        """获取文件完整路径（含路径遍历防护）。

        双重防护（缓解路径遍历）：
        1. 入口白名单：skill_name / filename 只允许字母数字下划线连字符点，
           从源头拒绝 ../ 、/ 、URL编码(%2f) 等路径分隔与逃逸字符；额外拒绝纯点名；
        2. resolve 校验：目标路径 resolve 后必须仍位于 skill 子目录内。
        """
        # 入口白名单（含纯点名拒绝）
        self._validate_skill_name(skill_name)
        self._validate_private_filename(filename)

        skill_path = self._get_skill_path(skill_name, subdir)
        target = (skill_path / filename).resolve()
        try:
            target.relative_to(skill_path.resolve())
        except ValueError:
            raise ValueError(f"非法路径（拒绝路径遍历）: skill={skill_name!r}, file={filename!r}")
        return target

    def _get_file_path_lexical(self, skill_name: str, filename: str, subdir: str = "data") -> Path:
        """获取私域文件词法路径（不 resolve，缓解 delete 跟随 symlink，同 shared 版本）。"""
        self._validate_skill_name(skill_name)
        self._validate_private_filename(filename)
        skill_path = self._get_skill_path(skill_name, subdir)
        return skill_path / filename

    def write(self, skill_name: str, filename: str, content: str,
              subdir: str = "data", append: bool = False) -> dict:
        """写入私域文件。

        安全（缓解默认权限 0o644 与 TOCTOU）：
        - 以 0o600 权限创建/写，避免同机其他用户读取；
        - O_NOFOLLOW：目标若是符号链接则直接失败，消除 check 与 use 之间的符号链接替换窗口。
        """
        file_path = self._get_file_path(skill_name, filename, subdir)

        try:
            flags = os.O_WRONLY | os.O_CREAT | (os.O_APPEND if append else os.O_TRUNC)
            # O_NOFOLLOW：拒绝符号链接，缓解 TOCTOU（攻击者在 check 后把文件换成 symlink）
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            if hasattr(os, "O_BINARY"):
                flags |= os.O_BINARY
            fd = os.open(file_path, flags, 0o600)
            try:
                if _HAS_FCNTL:
                    fcntl.flock(fd, fcntl.LOCK_EX)
                try:
                    os.write(fd, content.encode("utf-8"))
                finally:
                    if _HAS_FCNTL:
                        fcntl.flock(fd, fcntl.LOCK_UN)
            finally:
                os.close(fd)

            return {
                "success": True,
                "path": str(file_path),
                "skill": skill_name,
                "file": filename,
                "operation": "append" if append else "write"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def read(self, skill_name: str, filename: str, subdir: str = "data") -> dict:
        """读取私域文件（O_NOFOLLOW 拒绝符号链接，缓解 symlink race）。"""
        file_path = self._get_file_path(skill_name, filename, subdir)

        if not file_path.exists():
            return {"success": False, "error": f"文件不存在: {file_path}"}

        try:
            content = _secure_read_text(file_path)
            return {
                "success": True,
                "content": content,
                "path": str(file_path),
                "skill": skill_name,
                "file": filename
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def delete(self, skill_name: str, filename: str, subdir: str = "data") -> dict:
        """删除私域文件本身（若为符号链接，只删软链、不跟随目标）。

        缓解 symlink 误删：使用 lexical path（不 resolve），os.unlink 直接对
        路径操作，不 follow symlink。
        """
        try:
            file_path = self._get_file_path_lexical(skill_name, filename, subdir)
        except ValueError as e:
            return {"success": False, "error": str(e)}

        try:
            os.lstat(file_path)
        except FileNotFoundError:
            return {"success": False, "error": f"文件不存在: {file_path}"}
        except OSError as e:
            return {"success": False, "error": f"lstat 失败: {e}"}

        try:
            os.unlink(file_path)
            return {
                "success": True,
                "path": str(file_path),
                "skill": skill_name,
                "file": filename
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def list_files(self, skill_name: str, subdir: str = None) -> dict:
        """列出文件（含 skill_name 路径遍历防护）。"""
        self._validate_skill_name(skill_name)
        if subdir:
            if subdir not in self.SUBDIR_TYPES:
                raise ValueError(f"未知子目录类型: {subdir}。可用: {list(self.SUBDIR_TYPES.keys())}")
            paths = [self.workspace / skill_name / subdir]
        else:
            skill_root = self.workspace / skill_name
            paths = [skill_root / d for d in self.SUBDIR_TYPES.keys()]

        result = {}
        for path in paths:
            if path.exists():
                key = path.name
                result[key] = [
                    {
                        "name": f.name,
                        "size": f.stat().st_size,
                        "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat()
                    }
                    for f in path.iterdir() if f.is_file()
                ]

        return {"success": True, "skill": skill_name, "files": result}

    def list_skills(self) -> dict:
        """列出所有 Skill"""
        if not self.workspace.exists():
            return {"success": True, "skills": []}

        skills = [
            d.name for d in self.workspace.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        ]
        return {"success": True, "skills": skills}

    def info(self) -> dict:
        """获取缓存信息"""
        return {
            "success": True,
            "workspace": str(self.workspace),
            "timestamp": datetime.now().isoformat()
        }


# ── CLI 接口 ──────────────────────────────────────────────────────────

def _read_stdin() -> str:
    """从 stdin 读取内容（避免敏感数据出现在进程列表的命令行参数中）。"""
    if sys.stdin.isatty():
        return ""
    return sys.stdin.read()


def main():
    # Windows 编码修复
    if sys.platform == "win32":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

    parser = argparse.ArgumentParser(
        description="CXDA Skill 缓存管理 CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  # 认证数据管理
  cxda_cache_cli.py auth get
  cxda_cache_cli.py auth set --data '{"CXDA_USER_KEY":"xxx","authtoken":"yyy"}'
  cxda_cache_cli.py auth delete --key authtoken

  # 公域文件
  cxda_cache_cli.py shared read cxda_auth.json
  cxda_cache_cli.py shared write config.json --content '{"key":"value"}'
  cxda_cache_cli.py shared list

  # 私域文件
  cxda_cache_cli.py read my-skill data.json
  cxda_cache_cli.py write my-skill data.json --content '{"key":"value"}'
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # ── auth 命令组 ──
    auth_parser = subparsers.add_parser("auth", help="认证数据管理")
    auth_subparsers = auth_parser.add_subparsers(dest="auth_cmd")

    auth_get = auth_subparsers.add_parser("get", help="获取认证信息")
    auth_get.add_argument("--key", "-k", help="特定键（可选）")

    auth_set = auth_subparsers.add_parser("set", help="设置认证信息")
    # --data 可选：缺省时从 stdin 读取，避免含密钥的 JSON 出现在进程列表（缓解风险2）
    auth_set.add_argument("--data", "-d", help="JSON格式的认证数据（缺省时从stdin读取）")

    auth_delete = auth_subparsers.add_parser("delete", help="删除认证字段")
    auth_delete.add_argument("--key", "-k", help="特定键（可选，不指定则清空所有）")

    # ── shared 命令组 ──
    shared_parser = subparsers.add_parser("shared", help="公域数据管理")
    shared_subparsers = shared_parser.add_subparsers(dest="shared_cmd")

    shared_read = shared_subparsers.add_parser("read", help="读取公域文件")
    shared_read.add_argument("file", help="文件名")

    shared_write = shared_subparsers.add_parser("write", help="写入公域文件")
    shared_write.add_argument("file", help="文件名")
    shared_write.add_argument("--content", "-c", help="文件内容（缺省时从stdin读取）")

    shared_append = shared_subparsers.add_parser("append", help="追加公域文件")
    shared_append.add_argument("file", help="文件名")
    shared_append.add_argument("--content", "-c", help="文件内容（缺省时从stdin读取）")

    shared_delete = shared_subparsers.add_parser("delete", help="删除公域文件")
    shared_delete.add_argument("file", help="文件名")

    shared_subparsers.add_parser("list", help="列出公域文件")

    # ── 私域 read/write 命令 ──
    read_parser = subparsers.add_parser("read", help="读取私域文件")
    read_parser.add_argument("skill", help="Skill名称")
    read_parser.add_argument("file", help="文件名")
    read_parser.add_argument("--type", "-t", default="data",
                             choices=["data", "cache", "config"],
                             help="子目录类型")

    write_parser = subparsers.add_parser("write", help="写入私域文件")
    write_parser.add_argument("skill", help="Skill名称")
    write_parser.add_argument("file", help="文件名")
    write_parser.add_argument("--content", "-c", help="文件内容（缺省时从stdin读取）")
    write_parser.add_argument("--type", "-t", default="data",
                              choices=["data", "cache", "config"],
                              help="子目录类型")
    write_parser.add_argument("--append", "-a", action="store_true", help="追加模式")

    # ── info 命令 ──
    subparsers.add_parser("info", help="查看缓存信息")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    manager = CacheManager()

    # ── 执行命令 ──
    if args.command == "auth":
        if args.auth_cmd == "get":
            result = manager.auth_get()
            if result.get("success"):
                data = result.get("data", {})
                if args.key:
                    print(json.dumps({"success": True, "key": args.key, "value": data.get(args.key)},
                                     ensure_ascii=False, indent=2))
                else:
                    print(json.dumps(data, ensure_ascii=False, indent=2))
                return
        elif args.auth_cmd == "set":
            # 优先命令行 --data；缺省时从 stdin 读取，避免密钥出现在进程列表（缓解风险2）
            raw_data = args.data
            if not raw_data:
                if sys.stdin.isatty():
                    print(json.dumps({"success": False, "error": "缺少认证数据：请通过 --data 或 stdin 传入 JSON"}, ensure_ascii=False))
                    return
                raw_data = sys.stdin.read()
            try:
                auth_data = json.loads(raw_data)
            except json.JSONDecodeError as e:
                print(json.dumps({"success": False, "error": f"JSON解析错误: {e}"}, ensure_ascii=False))
                return
            result = manager.auth_set(auth_data)
        elif args.auth_cmd == "delete":
            result = manager.auth_delete(args.key)
        else:
            auth_parser.print_help()
            return

    elif args.command == "shared":
        if args.shared_cmd == "read":
            result = manager.shared_read(args.file)
            if result.get("success"):
                print(result["content"])
                return
        elif args.shared_cmd == "write":
            content = args.content if args.content is not None else _read_stdin()
            result = manager.shared_write(args.file, content)
        elif args.shared_cmd == "append":
            content = args.content if args.content is not None else _read_stdin()
            result = manager.shared_append(args.file, content)
        elif args.shared_cmd == "delete":
            result = manager.shared_delete(args.file)
        elif args.shared_cmd == "list":
            result = manager.shared_list()
        else:
            shared_parser.print_help()
            return

    elif args.command == "read":
        result = manager.read(args.skill, args.file, args.type)
        if result.get("success"):
            print(result["content"])
            return

    elif args.command == "write":
        content = args.content if args.content is not None else _read_stdin()
        result = manager.write(args.skill, args.file, content, args.type, args.append)

    elif args.command == "info":
        result = manager.info()

    else:
        parser.print_help()
        return

    # 输出结果
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
