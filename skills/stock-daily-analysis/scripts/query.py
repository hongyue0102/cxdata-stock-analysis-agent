# -*- coding: utf-8 -*-
"""
CXDA Skill - 统一查询脚本

提供数据查询和系统查询功能：
  - api:       调用业务数据接口
  - page-size: 查询接口分页大小限制
  - package:   查询用户套餐额度

用法：
  python query.py api <API_ID> key=value [key=value ...]
  python query.py page-size <API_ID>
  python query.py package [--api-main <API_ID>]
"""

import argparse
import json
import re
import sys
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

# fcntl 仅 Unix 可用，Windows 下记账锁退化为无锁（单进程场景无影响）
try:
    import fcntl
    _HAS_FCNTL = True
except ImportError:
    _HAS_FCNTL = False

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from common import (
    BASE_URL,
    REQUEST_CHANNEL,
    ensure_token,
    http_get,
    get_user_key,
    check_terms_accepted,
    output_json,
    output_error,
    get_shared_json,
    save_shared_json,
    PROXIES,
    HEADERS,
)


# ── 积分统计相关常量 ──────────────────────────────────────────────────

# 接口成功的返回码
SUCCESS_CODE = "10000"

# 公域会话账本文件（账户级，跨 Skill 共享）
SESSION_LEDGER_FILE = "cxda_session_ledger.json"

# 兜底：距上次计费调用超过该分钟数，视为新会话（防止 Agent 未显式 start）
SESSION_IDLE_MINUTES = 30

# 单轮会话达到该成功计费调用次数后，需要用户确认才能继续
BILLABLE_CALL_CONFIRMATION_THRESHOLD = 50

CONFIRMATION_REQUIRED_STATUS = "confirmation_required"

_TIME_FMT = "%Y-%m-%d %H:%M:%S"
_DISPLAY_TZ = timezone(timedelta(hours=8))


@contextmanager
def _ledger_lock():
    """账本文件锁：保护「读-改-写」整个临界区，防止并发 subprocess 互相覆盖。

    并发调用时，多个 query.py 进程同时「读账本→追加→写账本」，若只锁写不锁读，
    后写进程会覆盖先写进程的记录，导致积分记账大量丢失。此锁对整个临界区加排他锁。
    Windows 无 fcntl，退化为无锁（单进程或低并发场景无影响）。
    """
    if not _HAS_FCNTL:
        yield
        return
    lock_path = Path.home() / ".cxda-cache" / ".shared" / ".session_ledger.lock"
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    f = open(lock_path, "w")
    try:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    finally:
        f.close()


def parse_params(args):
    """解析命令行参数，支持 key=value 格式"""
    params = {}
    for arg in args:
        if '=' in arg:
            k, v = arg.split('=', 1)
            params[k.strip()] = v.strip()
    return params


# ── 会话积分账本 ──────────────────────────────────────────────────────

def _to_number(value):
    """将消耗值安全转为数字，失败返回 None"""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    try:
        text = str(value).strip()
        if text == "":
            return None
        num = float(text)
        return int(num) if num.is_integer() else num
    except (ValueError, TypeError):
        return None


def _format_timestamp(value, default="-"):
    """将后端毫秒时间戳格式化为北京时间 yyyy-MM-dd HH:mm:ss。"""
    if value is None or isinstance(value, bool):
        return default
    try:
        text = str(value).strip()
        if text == "":
            return default
        timestamp = float(text)
        if timestamp > 9999999999:
            timestamp = timestamp / 1000
        return datetime.fromtimestamp(timestamp, _DISPLAY_TZ).strftime(_TIME_FMT)
    except (ValueError, TypeError, OSError, OverflowError):
        return default


def _has_display_value(value):
    """判断字段是否应参与展示，0 是有效额度，空值和占位符不是。"""
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() not in ("", "-")
    return True


def _new_ledger(now):
    return {
        "session_start": now.strftime(_TIME_FMT),
        "started_ts": now.timestamp(),
        "last_call_ts": now.timestamp(),
        "calls": [],
        "requires_confirmation": False,
        "confirmed_after_50": False,
        "confirmation_required_at_count": None,
        "confirmed_at": None,
    }


def _ensure_ledger_confirmation_state(ledger):
    ledger.setdefault("requires_confirmation", False)
    ledger.setdefault("confirmed_after_50", False)
    ledger.setdefault("confirmation_required_at_count", None)
    ledger.setdefault("confirmed_at", None)
    return ledger


def _is_ledger_idle_expired(ledger, now):
    last_ts = ledger.get("last_call_ts") if isinstance(ledger, dict) else None
    if last_ts is None:
        return False
    try:
        return (now.timestamp() - float(last_ts)) > SESSION_IDLE_MINUTES * 60
    except (ValueError, TypeError):
        return False


def _get_active_ledger(now):
    ledger = get_shared_json(SESSION_LEDGER_FILE)
    calls = ledger.get("calls") if isinstance(ledger, dict) else None

    # 无账本 / 空账本 / 空闲超时 → 开新会话
    if not isinstance(calls, list) or _is_ledger_idle_expired(ledger, now):
        ledger = _new_ledger(now)
        calls = ledger["calls"]
    else:
        _ensure_ledger_confirmation_state(ledger)

    return ledger, calls


def _guard_before_billable_api_call():
    """
    在发起远端 API 调用前检查会话账本。
    已有 50 次成功计费调用且尚未确认时，暂停而不调用接口，避免产生第 51 次消耗。
    """
    now = datetime.now()
    # 加锁：并发时多个进程同时检查 call_count 会导致超过 50 次才触发，锁保证计数准确
    with _ledger_lock():
        ledger, calls = _get_active_ledger(now)
        call_count = len(calls)
        if call_count < BILLABLE_CALL_CONFIRMATION_THRESHOLD or ledger.get("confirmed_after_50") is True:
            return

        ledger["requires_confirmation"] = True
        ledger["confirmation_required_at_count"] = call_count
        save_shared_json(SESSION_LEDGER_FILE, ledger)
        return call_count


def _record_call_if_billable(api_id, data):
    """
    仅当「成功(code==10000) 且 消耗>0」时，将本次调用计入会话账本。
    失败、消耗缺失、消耗为 0 均不计入。记账异常不影响业务输出。
    """
    try:
        if not isinstance(data, dict):
            return
        if str(data.get("code")) != SUCCESS_CODE:
            return
        consumed = _to_number(data.get("consumePoints"))
        if consumed is None or consumed <= 0:
            return

        now = datetime.now()
        # 加锁保护「读-改-写」整个临界区，防止并发 subprocess 互相覆盖导致记账丢失
        with _ledger_lock():
            ledger, calls = _get_active_ledger(now)

            calls.append({
                "time": now.strftime(_TIME_FMT),
                "api_id": api_id,
                "consumed": consumed,
            })
            ledger["calls"] = calls
            ledger["last_call_ts"] = now.timestamp()
            save_shared_json(SESSION_LEDGER_FILE, ledger)
    except Exception:
        # 记账为旁路逻辑，任何异常都不应影响接口数据返回
        pass


def _format_package_item(item):
    """格式化套餐额度明细，保持 package 子命令输出结构稳定。"""
    return {
        "relation_id": item.get("id", ""),
        "user_id": item.get("wsUserId", ""),
        "package_id": item.get("wsPackageId", ""),
        "package_name": item.get("packageName", "-"),
        "package_code": item.get("packageCode", ""),
        "source_type": item.get("sourceType", ""),
        "status": item.get("status", ""),
        "valid_start": _format_timestamp(item.get("validStartTime")),
        "valid_end": _format_timestamp(item.get("validEndTime")),
        "total_money": item.get("totalMoney", ""),
        "balance": item.get("balance", ""),
        "day_balance": item.get("dayBalance", ""),
        "day_money": item.get("dayMoney", ""),
    }


def _query_package_result(user_key, api_main=""):
    """查询并格式化用户套餐额度，供 package 和 session summary 复用。"""
    if not user_key:
        return {
            "code": "10500",
            "msg": "未找到 CXDA_USER_KEY，请先通过 auth.py 完成认证",
            "package_count": 0,
            "packages": [],
        }

    params = {"userKey": user_key}
    if api_main:
        params["apiMain"] = api_main

    resp_data = http_get(
        f"{BASE_URL}/mall/api_getAuthList.htm",
        params=params
    )
    if str(resp_data.get("code")) != SUCCESS_CODE:
        return {
            "code": str(resp_data.get("code", "10500")),
            "msg": resp_data.get("msg", "查询失败"),
            "package_count": 0,
            "packages": [],
        }

    raw_list = resp_data.get("data", [])
    if not isinstance(raw_list, list):
        raw_list = []

    formatted = []
    for item in raw_list:
        if isinstance(item, dict):
            formatted.append(_format_package_item(item))
    return {
        "code": SUCCESS_CODE,
        "msg": resp_data.get("msg", "返回权限清单成功"),
        "package_count": len(formatted),
        "packages": formatted,
    }


def _format_session_package(item):
    """会话汇总只输出套餐剩余积分关键信息，避免跨套餐合并剩余额度。"""
    balance = item.get("balance", "")
    total_money = item.get("total_money", "")
    integral = "{}/{}".format(balance, total_money) if (
        _has_display_value(balance) and _has_display_value(total_money)
    ) else ""
    return {
        "source_type": item.get("source_type", ""),
        "package_name": item.get("package_name", "-"),
        "balance": balance,
        "total_money": total_money,
        "integral": integral,
        "day_balance": item.get("day_balance", ""),
        "day_money": item.get("day_money", ""),
        "valid_end": item.get("valid_end", "-"),
    }


# ── 子命令：api（业务数据接口查询）──────────────────────────────────────

def cmd_api(api_id, params):
    """
    调用业务数据接口

    认证方式：authtoken（自动从缓存获取或刷新）
    响应格式：gzip + base64 编码
    """
    # 安全校验：api_id 直接拼接到 URL path，必须严格限制为合法接口名格式
    # 防止 path traversal 攻击（如 api_id="../../admin/users" 访问内部端点）
    import re
    if not isinstance(api_id, str) or not re.match(r"^[A-Za-z0-9_-]+$", api_id):
        output_error(
            "非法的 api_id：{!r}（只允许字母、数字、下划线、短横线）".format(api_id)
        )
        return

    accepted, error_response = check_terms_accepted()
    if not accepted:
        output_json(error_response)
        return
    
    try:
        confirmation_required_count = _guard_before_billable_api_call()
        if confirmation_required_count is not None:
            output_json({
                "error": "本轮会话已成功调用 {} 次计费接口，请先获得用户确认后再继续。".format(confirmation_required_count),
                "status": CONFIRMATION_REQUIRED_STATUS,
                "call_count": confirmation_required_count,
                "next_action": "请用户确认是否继续调用；确认后执行 query.py session confirm",
            })
            return

        token = ensure_token()

        request_params = {"authtoken": token}
        request_params.update(params)

        data = http_get(
            f"{BASE_URL}/webservice/cxdata/{api_id}.htm",
            params=request_params
        )
        # 旁路：成功且消耗>0时计入会话积分账本（不改变业务输出结构）
        _record_call_if_billable(api_id, data)
        output_json(data)
    except Exception as e:
        output_error(str(e))


# ── 子命令：session（会话积分统计）──────────────────────────────────────

def cmd_session(action):
    """
    会话积分统计。会话边界由调用方（Agent）决定，脚本只负责记账与汇总。

      start   开始/重置当前会话（清空账本，记录起始时间）
      summary 汇总当前会话的消耗（合计 + 明细）和各套餐剩余积分
      confirm 记录用户已确认超过 50 次后继续调用
      reset   清空当前会话账本
    """
    # summary 需要查询套餐额度，需要协议前置
    if action == "summary":
        accepted, error_response = check_terms_accepted()
        if not accepted:
            output_json(error_response)
            return
    
    now = datetime.now()

    if action == "start":
        ledger = _new_ledger(now)
        save_shared_json(SESSION_LEDGER_FILE, ledger)
        output_json({
            "success": True,
            "message": "会话已开始",
            "session_start": ledger["session_start"],
        })
        return

    if action == "reset":
        save_shared_json(SESSION_LEDGER_FILE, {})
        output_json({"success": True, "message": "会话账本已清空"})
        return

    if action == "confirm":
        ledger = get_shared_json(SESSION_LEDGER_FILE)
        if not isinstance(ledger, dict) or not isinstance(ledger.get("calls"), list):
            output_json({
                "success": False,
                "status": "confirmation_not_required",
                "message": "没有可确认的会话账本",
            })
            return

        _ensure_ledger_confirmation_state(ledger)
        calls = ledger["calls"]
        if len(calls) < BILLABLE_CALL_CONFIRMATION_THRESHOLD:
            output_json({
                "success": False,
                "status": "confirmation_not_required",
                "message": "当前会话尚未达到需要确认的调用次数",
                "call_count": len(calls),
            })
            return

        ledger["requires_confirmation"] = False
        ledger["confirmed_after_50"] = True
        ledger["confirmation_required_at_count"] = ledger.get("confirmation_required_at_count") or len(calls)
        ledger["confirmed_at"] = now.strftime(_TIME_FMT)
        save_shared_json(SESSION_LEDGER_FILE, ledger)
        output_json({
            "success": True,
            "message": "已确认继续调用",
            "call_count": len(calls),
            "confirmed_at": ledger["confirmed_at"],
        })
        return

    # summary
    ledger = get_shared_json(SESSION_LEDGER_FILE)
    calls = ledger.get("calls", []) if isinstance(ledger, dict) else []
    total_consumed = 0
    for call in calls:
        num = _to_number(call.get("consumed"))
        if num is not None:
            total_consumed += num
    try:
        package_result = _query_package_result(get_user_key())
    except Exception as e:
        package_result = {
            "code": "10500",
            "msg": str(e),
            "packages": [],
        }
    packages = []
    if str(package_result.get("code")) == SUCCESS_CODE:
        packages = [_format_session_package(item) for item in package_result.get("packages", [])]
    output_json({
        "success": True,
        "session_start": ledger.get("session_start") if isinstance(ledger, dict) else None,
        "call_count": len(calls),
        "total_consumed": total_consumed,
        "calls": calls,
        "package_count": len(packages),
        "packages": packages,
        "package_error": None if str(package_result.get("code")) == SUCCESS_CODE else package_result.get("msg"),
    })


# ── 子命令：page-size（接口分页大小查询）────────────────────────────────

def cmd_page_size(api_id):
    """
    查询接口分页大小限制

    认证方式：userKey
    """
    # 安全校验：与 cmd_api 保持一致的 api_id 白名单
    import re
    if not isinstance(api_id, str) or not re.match(r"^[A-Za-z0-9_-]+$", api_id):
        output_error(
            "非法的 api_id：{!r}（只允许字母、数字、下划线、短横线）".format(api_id)
        )
        return

    accepted, error_response = check_terms_accepted()
    if not accepted:
        output_json(error_response)
        return
    
    user_key = get_user_key()
    if not user_key:
        output_error("未找到 CXDA_USER_KEY，请先通过 auth.py 完成认证")
        return

    try:
        import requests

        params = {"userKey": user_key, "apiMain": api_id}
        if REQUEST_CHANNEL:
            params["requestChannel"] = REQUEST_CHANNEL
        resp = requests.get(
            f"{BASE_URL}/mall/api_getApiLimitSetting.htm",
            params=params,
            headers=HEADERS,
            proxies=PROXIES
        )
        data = resp.json()
        output_json(data)
    except Exception as e:
        output_error(str(e))


# ── 子命令：package（套餐额度查询）──────────────────────────────────────

def cmd_package(api_main=""):
    """
    查询用户套餐额度

    认证方式：userKey
    """
    # 安全校验（缓解风险1 SQLi）：api_main 与 api_id 保持一致的白名单校验，
    # 拒绝非合法标识符（含 SQL 注入 payload、特殊字符）的输入
    if api_main and not re.match(r"^[A-Za-z0-9_-]+$", api_main):
        output_json({"code": "10400", "msg": f"非法 api-main 参数: {api_main!r}",
                     "package_count": 0, "packages": []})
        return

    accepted, error_response = check_terms_accepted()
    if not accepted:
        output_json(error_response)
        return
    
    user_key = get_user_key()
    
    if not user_key:
        output_json({
            "code": "10500",
            "msg": "未找到 CXDA_USER_KEY，请先通过 auth.py 完成认证",
            "package_count": 0,
            "packages": [],
        })
        return

    try:
        output_json(_query_package_result(user_key, api_main))
    except Exception as e:
        output_json({"code": "10500", "msg": str(e), "package_count": 0, "packages": []})


# ── 入口 ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="CXDA Skill - 统一查询工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
子命令说明：

  api <API_ID> [key=value ...]
    调用业务数据接口，查询具体数据。
    需要先完成认证（auth.py status 返回 authenticated=true）。
    authtoken 由脚本自动管理（缓存300秒，过期自动刷新），无需手动传入。
    返回数据经 gzip+base64 编码，脚本自动解码。
    参数以 key=value 格式传入，可传多个。

    用法：
      python query.py api <API_ID> key1=value1 key2=value2 ...

    示例：
      python query.py api getStkBasicInfoByCond-K stkCode=600519
      python query.py api getCooWineCateDailQuoByWineName wineName=飞天茅台
      python query.py api getCooWineCateDailQuoByWineName wineName=飞天茅台 pageNum=1 pageSize=10

    输出 JSON 格式：
      成功 → 接口返回的业务数据（JSON）
      失败 → {"error": "错误信息", "status": "failed"}

  page-size <API_ID>
    查询指定接口的分页大小限制（每次请求最大返回条数）。
    使用缓存的 CXDA_USER_KEY 认证，无需额外参数。

    用法：
      python query.py page-size <API_ID>

    示例：
      python query.py page-size getStkBasicInfoByCond-K

    输出 JSON 格式：
      {"code": 0, "maxPageSize": 20, ...}

  package [--api-main <API_ID>]
    查询用户套餐额度信息，自动从缓存读取 CXDA_USER_KEY。
    传入 --api-main 时，只返回包含该接口的套餐清单。
    每个套餐包含：套餐关系ID、用户ID、套餐ID、套餐名称、有效起止时间、总积分、剩余积分等。
    valid_start、valid_end 固定为北京时间 yyyy-MM-dd HH:mm:ss 格式。

    用法：
      python query.py package
      python query.py package --api-main <API_ID>

    示例：
      python query.py package
      python query.py package --api-main getStkBasicInfoByCond-K

    输出 JSON 格式：
      {"code": "10000", "msg": "返回权限清单成功", "package_count": 1, "packages": [{...}]}
      package 命令只返回脚本格式化后的 packages，避免与后端原始 data 重复。
      每个 packages 项包含：relation_id, user_id, package_id, package_name, package_code, source_type, status, valid_start, valid_end, total_money, balance, day_balance, day_money
        """
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # api
    p_api = subparsers.add_parser(
        "api",
        help="调用业务数据接口",
        description="调用业务数据接口查询具体数据。需要先完成认证（authenticated=true）。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python query.py api getStkBasicInfoByCond-K stkCode=600519
  python query.py api getCooWineCateDailQuoByWineName wineName=飞天茅台
  python query.py api getCooWineCateDailQuoByWineName wineName=飞天茅台 pageNum=1 pageSize=10

说明：
  - API_ID 为接口访问标识，由 Skill 的 SKILL.md 提供
  - 查询参数以 key=value 格式传入，支持多个参数
  - authtoken 由脚本自动管理，无需手动传入
  - 返回数据自动解码（gzip+base64），直接输出 JSON
  - 前置条件：用户已完成认证（python auth.py status 返回 authenticated=true）
        """
    )
    p_api.add_argument("api_id", help="接口访问标识（API ID）")
    p_api.add_argument("params", nargs="*", help="查询参数，格式 key=value（可多个）")

    # page-size
    p_ps = subparsers.add_parser(
        "page-size",
        help="查询接口分页大小限制",
        description="查询指定接口的分页大小限制（每次请求最大返回条数）。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python query.py page-size getStkBasicInfoByCond-K

说明：
  - 返回该接口每次请求允许的最大返回条数
  - 用于在调用 api 子命令时确定合适的 pageSize 参数值
  - 前置条件：用户已完成认证（python auth.py status 返回 authenticated=true）
        """
    )
    p_ps.add_argument("api_id", help="接口访问标识（API ID）")

    # package
    p_pkg = subparsers.add_parser(
        "package",
        help="查询用户套餐额度",
        description="查询用户套餐额度信息，自动从缓存读取 CXDA_USER_KEY，包含套餐关系、套餐名称、有效期、总积分、剩余积分、每日积分、每日剩余积分等。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python query.py package
  python query.py package --api-main getStkBasicInfoByCond-K

说明：
  - 查询用户已开通的套餐清单及额度信息
  - 自动从缓存读取 CXDA_USER_KEY，无需手动传入
  - 传入 --api-main 可筛选只包含指定接口的套餐
  - 每个套餐包含：套餐关系ID、用户ID、套餐ID、套餐名称、套餐编码、来源类型、状态、有效期、总积分、剩余积分、每日积分、每日剩余积分
  - valid_start、valid_end 固定输出为北京时间 yyyy-MM-dd HH:mm:ss
        """
    )
    p_pkg.add_argument("--api-main", default="", help="接口访问标识（可选，传入时只返回包含该接口的套餐）")

    # session
    p_session = subparsers.add_parser(
        "session",
        help="会话积分统计",
        description="会话积分统计。会话边界由调用方（Agent）决定，脚本负责记账、汇总和查询套餐剩余额度。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python query.py session start      # 会话开始时调用，重置账本
  python query.py session confirm    # 用户确认超过50次后继续调用
  python query.py session summary    # 会话结束时调用，汇总本次消耗和套餐剩余额度
  python query.py session reset      # 清空账本

说明：
  - api 子命令在「成功(code=10000) 且 消耗>0」时自动记账，失败/0消耗不计入
  - 当前会话已有50次成功计费调用且未确认时，api 会在调用前返回 confirmation_required
  - 用户确认继续后，先执行 session confirm，再继续 api 调用
  - summary 返回 call_count（会话调用接口数量）、total_consumed（本次会话消耗合计）、calls（明细）
  - summary 同时返回 packages，每个套餐包含：source_type、package_name、balance、total_money、integral、day_balance、day_money、valid_end
  - 不同套餐的剩余积分不能混合合计，必须逐套餐展示
        """
    )
    p_session.add_argument("action", choices=["start", "confirm", "summary", "reset"], help="会话操作")

    args = parser.parse_args()

    if args.command == "api":
        params = parse_params(args.params)
        cmd_api(args.api_id, params)
    elif args.command == "page-size":
        cmd_page_size(args.api_id)
    elif args.command == "package":
        cmd_package(args.api_main)
    elif args.command == "session":
        cmd_session(args.action)


if __name__ == "__main__":
    main()
