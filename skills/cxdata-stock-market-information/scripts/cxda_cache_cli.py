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
import re
import stat as _stat
import sys
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

# 平台文件锁：普通文件继续使用 Unix flock；跨文件事务锁同时支持 Windows。
try:
    import fcntl
    _HAS_FCNTL = True
except ImportError:
    fcntl = None
    _HAS_FCNTL = False

try:
    import msvcrt
    _HAS_MSVCRT = True
except ImportError:
    msvcrt = None
    _HAS_MSVCRT = False


# ── 安全文件/工作空间工具 ─────────────────────────────────────────────


def _ensure_dir_not_symlink(path: Path) -> None:
    """拒绝 workspace/shared 目录为符号链接或其它非目录节点。"""
    try:
        st = os.lstat(path)
    except FileNotFoundError:
        return
    if _stat.S_ISLNK(st.st_mode):
        raise RuntimeError("拒绝目录为符号链接: {}".format(path))
    if not _stat.S_ISDIR(st.st_mode):
        raise RuntimeError("拒绝目录为非目录节点: {}".format(path))


def _secure_chmod(path: Path, mode: int) -> None:
    try:
        os.chmod(path, mode)
    except OSError:
        # Windows ACL 不由 chmod 控制；默认用户目录 ACL 仍负责隔离。
        pass


def _write_all(fd: int, data: bytes) -> None:
    view = memoryview(data)
    offset = 0
    while offset < len(view):
        written = os.write(fd, view[offset:])
        if written <= 0:
            raise OSError("写入失败")
        offset += written


@contextmanager
def _exclusive_file_lock(file_path: Path, timeout: float = 30.0):
    """获取一个跨平台独占锁，用于保护跨多个缓存文件的完整事务。"""
    try:
        st = os.lstat(file_path)
        if _stat.S_ISLNK(st.st_mode) or not _stat.S_ISREG(st.st_mode):
            raise OSError("锁文件不是普通文件")
    except FileNotFoundError:
        pass

    flags = os.O_RDWR | os.O_CREAT
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    fd = os.open(file_path, flags, 0o600)
    locked = False
    try:
        opened_stat = os.fstat(fd)
        if not _stat.S_ISREG(opened_stat.st_mode):
            raise OSError("锁文件不是普通文件")
        if opened_stat.st_size == 0:
            os.write(fd, b"\0")
        deadline = time.monotonic() + max(float(timeout), 0.0)
        while True:
            try:
                if _HAS_FCNTL:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                elif _HAS_MSVCRT:
                    os.lseek(fd, 0, os.SEEK_SET)
                    msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                else:
                    raise RuntimeError("当前平台不支持跨进程文件锁")
                locked = True
                break
            except (BlockingIOError, OSError):
                if time.monotonic() >= deadline:
                    raise TimeoutError("获取共享锁超时: {}".format(file_path.name))
                time.sleep(0.05)
        yield
    finally:
        if locked:
            if _HAS_FCNTL:
                fcntl.flock(fd, fcntl.LOCK_UN)
            elif _HAS_MSVCRT:
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        os.close(fd)


def _secure_write_text(file_path: Path, content: str, append: bool = False) -> None:
    """以 0600 + O_NOFOLLOW 写入文本，并保留 Unix 文件锁。"""
    try:
        st = os.lstat(file_path)
        if _stat.S_ISLNK(st.st_mode) or not _stat.S_ISREG(st.st_mode):
            raise OSError("目标不是普通文件")
    except FileNotFoundError:
        pass
    # 覆盖写不能在加锁前 O_TRUNC，否则两个并发写入者可能在拿到锁之前互相截断。
    # 先打开并加锁，再在锁内 ftruncate；追加模式继续依赖 O_APPEND 的原子偏移语义。
    flags = os.O_WRONLY | os.O_CREAT | (os.O_APPEND if append else 0)
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    if hasattr(os, "O_NONBLOCK"):
        flags |= os.O_NONBLOCK
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    fd = os.open(file_path, flags, 0o600)
    try:
        opened_stat = os.fstat(fd)
        if not _stat.S_ISREG(opened_stat.st_mode):
            raise OSError("目标不是普通文件")
        if hasattr(os, "fchmod"):
            try:
                os.fchmod(fd, 0o600)
            except OSError:
                pass
        if _HAS_FCNTL:
            fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            if not append:
                os.ftruncate(fd, 0)
                os.lseek(fd, 0, os.SEEK_SET)
            _write_all(fd, content.encode("utf-8"))
        finally:
            if _HAS_FCNTL:
                fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def _secure_read_text(file_path: Path) -> str:
    """以 O_NOFOLLOW 从 fd 读取，避免符号链接替换竞态。"""
    st = os.lstat(file_path)
    if _stat.S_ISLNK(st.st_mode) or not _stat.S_ISREG(st.st_mode):
        raise OSError("目标不是普通文件")
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    if hasattr(os, "O_NONBLOCK"):
        flags |= os.O_NONBLOCK
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    fd = os.open(file_path, flags)
    try:
        opened_stat = os.fstat(fd)
        if not _stat.S_ISREG(opened_stat.st_mode):
            raise OSError("目标不是普通文件")
        if _HAS_FCNTL:
            fcntl.flock(fd, fcntl.LOCK_SH)
        try:
            chunks = []
            while True:
                chunk = os.read(fd, 65536)
                if not chunk:
                    break
                chunks.append(chunk)
            return b"".join(chunks).decode("utf-8")
        finally:
            if _HAS_FCNTL:
                fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def _fallback_workspace() -> Path:
    fallback = Path.home() / ".cxda-cache"
    _ensure_dir_not_symlink(fallback)
    return fallback


def _validate_workspace_path(workspace: Path, source: str = "", require_home: bool = True) -> Path:
    """限制工作空间到当前用户家目录，拒绝系统目录和符号链接。"""
    try:
        candidate = workspace.expanduser()
        if not candidate.is_absolute():
            candidate = (Path.cwd() / candidate)
        _ensure_dir_not_symlink(candidate)
        resolved = candidate.resolve()
        home = Path.home().resolve()
        if resolved == Path(resolved.anchor):
            raise ValueError("文件系统根目录")
        critical = (
            "/etc", "/bin", "/sbin", "/usr", "/boot", "/dev", "/proc", "/sys",
            "/var", "/lib", "/lib64", "/Library", "/System",
        )
        resolved_text = str(resolved)
        if any(resolved_text == item or resolved_text.startswith(item + os.sep) for item in critical):
            raise ValueError("系统关键目录")
        if require_home:
            if resolved == home:
                raise ValueError("用户家目录本身不能作为缓存目录")
            try:
                resolved.relative_to(home)
            except ValueError:
                raise ValueError("不在用户家目录下")
        return resolved
    except (OSError, ValueError, RuntimeError) as exc:
        sys.stderr.write("[WARN] 拒绝 workspace，回退默认目录（{}，来源={}）\n".format(
            type(exc).__name__, source or "unknown"
        ))
        return _fallback_workspace()


# ── 工作空间探测 ──────────────────────────────────────────────────────

def detect_workspace() -> Path:
    """
    自动检测工作空间路径

    优先级：
    1. CXDA_CACHE_WORKSPACE 环境变量
    2. CLAUDE_WORKSPACE 环境变量
    3. 默认 ~/.cxda-cache
    """
    for env_var in ["CXDA_CACHE_WORKSPACE", "CLAUDE_WORKSPACE"]:
        path = os.environ.get(env_var)
        if path:
            workspace = _validate_workspace_path(Path(path), source=env_var)
            workspace.mkdir(parents=True, exist_ok=True)
            _secure_chmod(workspace, 0o700)
            return workspace

    workspace = _validate_workspace_path(Path.home() / ".cxda-cache", source="default")
    workspace.mkdir(parents=True, exist_ok=True)
    _secure_chmod(workspace, 0o700)
    return workspace


# ── 缓存管理器 ────────────────────────────────────────────────────────

class CacheManager:
    """CXDA Skill 缓存管理器"""

    def __init__(self, workspace: Path = None):
        self.workspace = (
            _validate_workspace_path(Path(workspace), source="explicit", require_home=False)
            if workspace is not None else detect_workspace()
        )
        self.workspace.mkdir(parents=True, exist_ok=True)
        _secure_chmod(self.workspace, 0o700)
        self._ensure_structure()

    def _ensure_structure(self):
        """确保基础目录结构存在"""
        shared_dir = self.workspace / ".shared"
        _ensure_dir_not_symlink(shared_dir)
        shared_dir.mkdir(parents=True, exist_ok=True)
        _secure_chmod(shared_dir, 0o700)

    # ==================== 公域数据管理 ====================

    def _get_shared_path(self, filename: str) -> Path:
        """获取公域文件路径并确保 resolve 后仍位于 .shared 内。"""
        self._validate_shared_filename(filename)
        shared_dir = self.workspace / ".shared"
        _ensure_dir_not_symlink(shared_dir)
        shared_dir.mkdir(parents=True, exist_ok=True)
        _secure_chmod(shared_dir, 0o700)
        target = shared_dir / filename
        try:
            target.resolve().relative_to(shared_dir.resolve())
        except ValueError:
            raise ValueError("非法路径（拒绝路径遍历）: {}".format(filename))
        return target

    _SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
    _ALL_DOTS_RE = re.compile(r"^\.+$")

    @classmethod
    def _validate_shared_filename(cls, filename: str) -> str:
        if (
            not isinstance(filename, str)
            or not filename
            or not cls._SAFE_NAME_RE.fullmatch(filename)
            or cls._ALL_DOTS_RE.fullmatch(filename)
            or ".." in filename
        ):
            raise ValueError("非法公域文件名（拒绝路径遍历）: {!r}".format(filename))
        return filename

    def _get_shared_path_lexical(self, filename: str) -> Path:
        """删除时返回不 resolve 的词法路径，保证只删除软链本身。"""
        self._validate_shared_filename(filename)
        shared_dir = self.workspace / ".shared"
        _ensure_dir_not_symlink(shared_dir)
        shared_dir.mkdir(parents=True, exist_ok=True)
        _secure_chmod(shared_dir, 0o700)
        return shared_dir / filename

    @contextmanager
    def shared_lock(self, filename: str, timeout: float = 30.0):
        """锁住一个命名事务；同一 workspace 下所有 Skill 共享该锁。"""
        file_path = self._get_shared_path(filename)
        with _exclusive_file_lock(file_path, timeout=timeout):
            yield

    def shared_read(self, filename: str) -> dict:
        """读取公域文件"""
        try:
            file_path = self._get_shared_path(filename)
            os.lstat(file_path)
            content = _secure_read_text(file_path)
            return {"success": True, "content": content, "path": str(file_path)}
        except FileNotFoundError:
            return {"success": False, "error": "文件不存在"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def shared_write(self, filename: str, content: str) -> dict:
        """写入公域文件（带文件锁保护）"""
        try:
            file_path = self._get_shared_path(filename)
            _secure_write_text(file_path, content)

            return {"success": True, "path": str(file_path), "file": filename}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def shared_append(self, filename: str, content: str) -> dict:
        """追加公域文件，使用 O_APPEND + 单次 os.write 降低并发丢写风险。"""
        try:
            file_path = self._get_shared_path(filename)
            _secure_write_text(file_path, content, append=True)

            return {
                "success": True,
                "path": str(file_path),
                "file": filename,
                "operation": "append"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def shared_delete(self, filename: str) -> dict:
        """删除公域文件"""
        try:
            file_path = self._get_shared_path_lexical(filename)
            os.lstat(file_path)
            os.unlink(file_path)
            return {"success": True, "path": str(file_path), "file": filename}
        except FileNotFoundError:
            return {"success": False, "error": "文件不存在"}
        except ValueError as e:
            return {"success": False, "error": str(e)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def shared_list(self) -> dict:
        """列出所有公域文件"""
        shared_dir = self.workspace / ".shared"
        try:
            _ensure_dir_not_symlink(shared_dir)
            if not shared_dir.exists():
                return {"success": True, "files": []}
            files = [
                {
                    "name": f.name,
                    "size": f.stat().st_size,
                    "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat()
                }
                for f in shared_dir.iterdir()
                if not f.is_symlink() and f.is_file()
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
        if not isinstance(auth_data, dict):
            return {"success": False, "error": "认证数据必须是 JSON 对象"}
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

    def _get_skill_path(self, skill_name: str, subdir: str = "data") -> Path:
        """获取 Skill 目录路径"""
        self._validate_skill_name(skill_name)
        if subdir not in self.SUBDIR_TYPES:
            raise ValueError(f"未知子目录类型: {subdir}。可用: {list(self.SUBDIR_TYPES.keys())}")
        skill_root = self.workspace / skill_name
        _ensure_dir_not_symlink(skill_root)
        skill_root.mkdir(parents=True, exist_ok=True)
        _secure_chmod(skill_root, 0o700)
        skill_path = skill_root / subdir
        _ensure_dir_not_symlink(skill_path)
        skill_path.mkdir(parents=True, exist_ok=True)
        _secure_chmod(skill_path, 0o700)
        return skill_path

    @classmethod
    def _validate_skill_name(cls, skill_name: str) -> str:
        if (
            not isinstance(skill_name, str)
            or not skill_name
            or not cls._SAFE_NAME_RE.fullmatch(skill_name)
            or cls._ALL_DOTS_RE.fullmatch(skill_name)
            or ".." in skill_name
        ):
            raise ValueError("非法 skill 名称（拒绝路径遍历）: {!r}".format(skill_name))
        return skill_name

    @classmethod
    def _validate_private_filename(cls, filename: str) -> str:
        if (
            not isinstance(filename, str)
            or not filename
            or not cls._SAFE_NAME_RE.fullmatch(filename)
            or cls._ALL_DOTS_RE.fullmatch(filename)
            or ".." in filename
        ):
            raise ValueError("非法 file 名称（拒绝路径遍历）: {!r}".format(filename))
        return filename

    def _get_file_path(self, skill_name: str, filename: str, subdir: str = "data") -> Path:
        """获取文件完整路径"""
        self._validate_skill_name(skill_name)
        self._validate_private_filename(filename)
        skill_path = self._get_skill_path(skill_name, subdir)
        target = skill_path / filename
        try:
            target.resolve().relative_to(skill_path.resolve())
        except ValueError:
            raise ValueError("非法路径（拒绝路径遍历）")
        return target

    def _get_file_path_lexical(self, skill_name: str, filename: str, subdir: str = "data") -> Path:
        self._validate_skill_name(skill_name)
        self._validate_private_filename(filename)
        return self._get_skill_path(skill_name, subdir) / filename

    def write(self, skill_name: str, filename: str, content: str,
              subdir: str = "data", append: bool = False) -> dict:
        """写入私域文件"""
        try:
            file_path = self._get_file_path(skill_name, filename, subdir)
            _secure_write_text(file_path, content, append=append)

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
        """读取私域文件"""
        try:
            file_path = self._get_file_path(skill_name, filename, subdir)
            os.lstat(file_path)
            content = _secure_read_text(file_path)
            return {
                "success": True,
                "content": content,
                "path": str(file_path),
                "skill": skill_name,
                "file": filename
            }
        except FileNotFoundError:
            return {"success": False, "error": "文件不存在"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def delete(self, skill_name: str, filename: str, subdir: str = "data") -> dict:
        """删除私域文件"""
        try:
            file_path = self._get_file_path_lexical(skill_name, filename, subdir)
            os.lstat(file_path)
            os.unlink(file_path)
            return {
                "success": True,
                "path": str(file_path),
                "skill": skill_name,
                "file": filename
            }
        except FileNotFoundError:
            return {"success": False, "error": "文件不存在"}
        except ValueError as e:
            return {"success": False, "error": str(e)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def list_files(self, skill_name: str, subdir: str = None) -> dict:
        """列出文件"""
        self._validate_skill_name(skill_name)
        if subdir:
            if subdir not in self.SUBDIR_TYPES:
                raise ValueError(f"未知子目录类型: {subdir}。可用: {list(self.SUBDIR_TYPES.keys())}")
            paths = [self._get_skill_path(skill_name, subdir)]
        else:
            skill_root = self.workspace / skill_name
            _ensure_dir_not_symlink(skill_root)
            paths = [skill_root / d for d in self.SUBDIR_TYPES.keys()]

        result = {}
        for path in paths:
            _ensure_dir_not_symlink(path)
            if path.exists():
                key = path.name
                result[key] = [
                    {
                        "name": f.name,
                        "size": f.stat().st_size,
                        "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat()
                    }
                    for f in path.iterdir() if not f.is_symlink() and f.is_file()
                ]

        return {"success": True, "skill": skill_name, "files": result}

    def list_skills(self) -> dict:
        """列出所有 Skill"""
        _ensure_dir_not_symlink(self.workspace)
        if not self.workspace.exists():
            return {"success": True, "skills": []}

        skills = [
            d.name for d in self.workspace.iterdir()
            if not d.is_symlink() and d.is_dir() and not d.name.startswith(".")
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
    """读取 stdin 内容，供敏感数据/大块文本传递，避免进入进程参数。"""
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
  echo '{"CXDA_USER_KEY":"xxx","authtoken":"yyy"}' | cxda_cache_cli.py auth set
  cxda_cache_cli.py auth delete --key authtoken

  # 公域文件
  cxda_cache_cli.py shared read cxda_auth.json
  echo '{"key":"value"}' | cxda_cache_cli.py shared write config.json
  cxda_cache_cli.py shared list

  # 私域文件
  cxda_cache_cli.py read my-skill data.json
  echo '{"key":"value"}' | cxda_cache_cli.py write my-skill data.json
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # ── auth 命令组 ──
    auth_parser = subparsers.add_parser("auth", help="认证数据管理")
    auth_subparsers = auth_parser.add_subparsers(dest="auth_cmd")

    auth_get = auth_subparsers.add_parser("get", help="获取认证信息")
    auth_get.add_argument("--key", "-k", help="特定键（可选）")

    auth_set = auth_subparsers.add_parser("set", help="设置认证信息")
    auth_set.add_argument("--data", "-d", help="JSON格式的认证数据（缺省时从 stdin 读取）")

    auth_delete = auth_subparsers.add_parser("delete", help="删除认证字段")
    auth_delete.add_argument("--key", "-k", help="特定键（可选，不指定则清空所有）")

    # ── shared 命令组 ──
    shared_parser = subparsers.add_parser("shared", help="公域数据管理")
    shared_subparsers = shared_parser.add_subparsers(dest="shared_cmd")

    shared_read = shared_subparsers.add_parser("read", help="读取公域文件")
    shared_read.add_argument("file", help="文件名")

    shared_write = shared_subparsers.add_parser("write", help="写入公域文件")
    shared_write.add_argument("file", help="文件名")
    shared_write.add_argument("--content", "-c", help="文件内容（缺省时从 stdin 读取）")

    shared_append = shared_subparsers.add_parser("append", help="追加公域文件")
    shared_append.add_argument("file", help="文件名")
    shared_append.add_argument("--content", "-c", help="文件内容（缺省时从 stdin 读取）")

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
    write_parser.add_argument("--content", "-c", help="文件内容（缺省时从 stdin 读取）")
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

    try:
        manager = CacheManager()
    except Exception as exc:
        print(json.dumps({"success": False, "error": "缓存目录初始化失败：{}".format(type(exc).__name__)},
                         ensure_ascii=False))
        return

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
            raw_data = args.data if args.data is not None else _read_stdin()
            if not raw_data:
                print(json.dumps({"success": False, "error": "缺少认证数据：请通过 --data 或 stdin 传入 JSON"},
                                 ensure_ascii=False))
                return
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
