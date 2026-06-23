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


# ── 安全校验 ──────────────────────────────────────────────────────────

def _validate_filename(filename: str) -> str:
    """
    校验文件名，防止路径遍历（如 ../、绝对路径、盘符）。

    仅允许纯文件名（可含子目录但禁止逃逸 workspace）。
    """
    if not filename or not isinstance(filename, str):
        raise ValueError("文件名不能为空")

    # 禁止绝对路径与盘符（Windows）
    if os.path.isabs(filename) or ":" in filename.split(os.sep)[0]:
        raise ValueError(f"非法文件名（禁止绝对路径）: {filename}")

    # 解析后不得包含 .. 段，也不得逃出目标目录
    parts = Path(filename).parts
    if ".." in parts:
        raise ValueError(f"非法文件名（禁止路径遍历）: {filename}")

    return filename


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
            # 校验：禁止空值、相对路径中的 .. 逃逸（必须是明确的目标目录）
            workspace = Path(path).expanduser()
            if ".." in workspace.parts:
                raise ValueError(f"非法 workspace 路径（禁止 .. 逃逸）: {path}")
            workspace = workspace.resolve()
            workspace.mkdir(parents=True, exist_ok=True)
            return workspace

    workspace = Path.home() / ".cxda-cache"
    workspace.mkdir(parents=True, exist_ok=True)
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
        shared_dir.mkdir(parents=True, exist_ok=True)

    def _check_within_workspace(self, resolved: Path) -> Path:
        """确保解析后的路径仍位于 workspace 内，防止符号链接/..逃逸"""
        try:
            resolved.relative_to(self.workspace)
        except ValueError:
            raise ValueError(f"路径逃逸出 workspace: {resolved}")
        return resolved

    # ==================== 公域数据管理 ====================

    def _get_shared_path(self, filename: str) -> Path:
        """获取公域文件路径"""
        _validate_filename(filename)
        shared_dir = self.workspace / ".shared"
        shared_dir.mkdir(parents=True, exist_ok=True)
        return self._check_within_workspace((shared_dir / filename).resolve())

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
        """写入公域文件（带文件锁保护）"""
        file_path = self._get_shared_path(filename)

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                if _HAS_FCNTL:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                try:
                    f.write(content)
                finally:
                    if _HAS_FCNTL:
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)

            return {"success": True, "path": str(file_path), "file": filename}
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
        _validate_filename(skill_name)
        if subdir not in self.SUBDIR_TYPES:
            raise ValueError(f"未知子目录类型: {subdir}。可用: {list(self.SUBDIR_TYPES.keys())}")
        skill_path = self.workspace / skill_name / subdir
        skill_path.mkdir(parents=True, exist_ok=True)
        return self._check_within_workspace(skill_path.resolve())

    def _get_file_path(self, skill_name: str, filename: str, subdir: str = "data") -> Path:
        """获取文件完整路径"""
        _validate_filename(filename)
        return self._check_within_workspace(
            (self._get_skill_path(skill_name, subdir) / filename).resolve()
        )

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
        _validate_filename(skill_name)
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
