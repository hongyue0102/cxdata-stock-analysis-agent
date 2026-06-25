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

def _validate_workspace_path(workspace: Path, source: str = "") -> Path:
    """校验 workspace 路径合理性（缓解环境变量路径遍历）。

    拒绝系统关键目录、要求在用户家目录下，否则回退默认 ~/.cxda-cache。
    """
    SYSTEM_CRITICAL = (
        "/etc", "/bin", "/sbin", "/usr", "/boot", "/dev", "/proc", "/sys",
        "/var", "/lib", "/lib64", "/root", "/Library", "/System",
    )
    home = Path.home().resolve()
    resolved = workspace.resolve()
    resolved_str = str(resolved)
    for crit in SYSTEM_CRITICAL:
        if resolved_str == crit or resolved_str.startswith(crit + os.sep):
            sys.stderr.write(f"[WARN] 拒绝 workspace {resolved_str}（系统关键目录），回退默认。来源: {source}\n")
            return Path.home() / ".cxda-cache"
    if not resolved_str.startswith(str(home) + os.sep) and resolved_str != str(home):
        sys.stderr.write(f"[WARN] 拒绝 workspace {resolved_str}（不在用户家目录下），回退默认。来源: {source}\n")
        return Path.home() / ".cxda-cache"
    return resolved


def _secure_write_text(file_path: Path, content: str) -> None:
    """以 0o600 权限写文本文件（缓解凭证文件默认 0o644 可被同机用户读取）。保留 fcntl 文件锁。"""
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
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


def detect_workspace() -> Path:
    """
    自动检测工作空间路径

    优先级：
    1. CXDA_CACHE_WORKSPACE 环境变量
    2. CLAUDE_WORKSPACE 环境变量
    3. 默认 ~/.cxda-cache

    环境变量路径需通过 _validate_workspace_path 校验。
    """
    for env_var in ["CXDA_CACHE_WORKSPACE", "CLAUDE_WORKSPACE"]:
        path = os.environ.get(env_var)
        if path:
            workspace = _validate_workspace_path(Path(path).expanduser(), source=env_var)
            workspace.mkdir(parents=True, exist_ok=True, mode=0o700)
            try:
                os.chmod(workspace, 0o700)
            except OSError:
                pass
            return workspace

    workspace = Path.home() / ".cxda-cache"
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

    def shared_read(self, filename: str) -> dict:
        """读取公域文件"""
        file_path = self._get_shared_path(filename)

        if not file_path.exists():
            return {"success": False, "error": f"文件不存在: {file_path}"}

        try:
            content = file_path.read_text(encoding="utf-8")
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
        """追加公域文件，使用 O_APPEND + 单次 os.write 降低并发丢写风险（权限 0o600）。"""
        file_path = self._get_shared_path(filename)

        try:
            data = content.encode("utf-8")
            flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
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
        """删除公域文件"""
        file_path = self._get_shared_path(filename)

        if not file_path.exists():
            return {"success": False, "error": f"文件不存在: {file_path}"}

        try:
            file_path.unlink()
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

    def _get_skill_path(self, skill_name: str, subdir: str = "data") -> Path:
        """获取 Skill 目录路径"""
        if subdir not in self.SUBDIR_TYPES:
            raise ValueError(f"未知子目录类型: {subdir}。可用: {list(self.SUBDIR_TYPES.keys())}")
        skill_path = self.workspace / skill_name / subdir
        skill_path.mkdir(parents=True, exist_ok=True, mode=0o700)
        return skill_path

    def _get_file_path(self, skill_name: str, filename: str, subdir: str = "data") -> Path:
        """获取文件完整路径"""
        return self._get_skill_path(skill_name, subdir) / filename

    def write(self, skill_name: str, filename: str, content: str,
              subdir: str = "data", append: bool = False) -> dict:
        """写入私域文件"""
        file_path = self._get_file_path(skill_name, filename, subdir)
        mode = "a" if append else "w"

        try:
            with open(file_path, mode, encoding="utf-8") as f:
                if _HAS_FCNTL:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                try:
                    f.write(content)
                finally:
                    if _HAS_FCNTL:
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)

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
        file_path = self._get_file_path(skill_name, filename, subdir)

        if not file_path.exists():
            return {"success": False, "error": f"文件不存在: {file_path}"}

        try:
            content = file_path.read_text(encoding="utf-8")
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
        """删除私域文件"""
        file_path = self._get_file_path(skill_name, filename, subdir)

        if not file_path.exists():
            return {"success": False, "error": f"文件不存在: {file_path}"}

        try:
            file_path.unlink()
            return {
                "success": True,
                "path": str(file_path),
                "skill": skill_name,
                "file": filename
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def list_files(self, skill_name: str, subdir: str = None) -> dict:
        """列出文件"""
        if subdir:
            paths = [self._get_skill_path(skill_name, subdir)]
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
    auth_set.add_argument("--data", "-d", required=True, help="JSON格式的认证数据")

    auth_delete = auth_subparsers.add_parser("delete", help="删除认证字段")
    auth_delete.add_argument("--key", "-k", help="特定键（可选，不指定则清空所有）")

    # ── shared 命令组 ──
    shared_parser = subparsers.add_parser("shared", help="公域数据管理")
    shared_subparsers = shared_parser.add_subparsers(dest="shared_cmd")

    shared_read = shared_subparsers.add_parser("read", help="读取公域文件")
    shared_read.add_argument("file", help="文件名")

    shared_write = shared_subparsers.add_parser("write", help="写入公域文件")
    shared_write.add_argument("file", help="文件名")
    shared_write.add_argument("--content", "-c", required=True, help="文件内容")

    shared_append = shared_subparsers.add_parser("append", help="追加公域文件")
    shared_append.add_argument("file", help="文件名")
    shared_append.add_argument("--content", "-c", required=True, help="文件内容")

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
    write_parser.add_argument("--content", "-c", required=True, help="文件内容")
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
            try:
                auth_data = json.loads(args.data)
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
            result = manager.shared_write(args.file, args.content)
        elif args.shared_cmd == "append":
            result = manager.shared_append(args.file, args.content)
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
        result = manager.write(args.skill, args.file, args.content, args.type, args.append)

    elif args.command == "info":
        result = manager.info()

    else:
        parser.print_help()
        return

    # 输出结果
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
