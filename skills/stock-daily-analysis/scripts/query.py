# -*- coding: utf-8 -*-
"""
CXDA Skill - 统一查询脚本

提供数据查询和系统查询功能：
  - api:       编排鉴权、会话、业务数据接口和积分汇总
  - page-size: 查询接口分页大小限制
  - package:   查询用户套餐额度

用法：
  python query.py api <API_ID> key=value [key=value ...] [--finalize]
  python query.py page-size <API_ID> [key=value ...]
  python query.py package [--api-main <API_ID>]
"""

import argparse
import hashlib
import json
import re
import sys
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from common import (
    BASE_URL,
    AuthenticationRequiredError,
    ensure_token,
    http_get,
    http_post_form,
    get_user_key,
    check_terms_accepted,
    output_json,
    output_error,
    get_shared_json,
    save_shared_json,
    get_shared_text,
    save_shared_text,
    append_shared_text,
    shared_file_lock,
    get_platform_show_billing_info,
)


# ── 积分统计相关常量 ──────────────────────────────────────────────────

# 接口成功的返回码
SUCCESS_CODE = "10000"

# 公域会话账本文件（账户级，跨 Skill 共享，保存会话元数据）
SESSION_LEDGER_FILE = "cxda_session_ledger.json"

# 公域计费调用日志（账户级，跨 Skill 共享，每行一个 JSON 调用记录）
SESSION_CALLS_LOG_FILE = "cxda_session_calls.jsonl"
SESSION_LOCK_FILE = "cxda_session_ledger.lock"

# 兜底：距上次计费调用超过该分钟数，视为新会话（防止 Agent 未显式 start）
SESSION_IDLE_MINUTES = 30

# 业务请求意外退出后，预留记录超过该时间可回收。HTTP 自身超时为 30 秒。
PENDING_CALL_TIMEOUT_SECONDS = 120

# 单轮会话达到该成功计费调用次数后，需要用户确认才能继续
BILLABLE_CALL_CONFIRMATION_THRESHOLD = 50

CONFIRMATION_REQUIRED_STATUS = "confirmation_required"

_TIME_FMT = "%Y-%m-%d %H:%M:%S"
_DISPLAY_TZ = timezone(timedelta(hours=8))
_PAGE_SIZE_CACHE = None
_PAGE_SIZE_LOCK = threading.RLock()
_SESSION_SUMMARY_FIELD = "_cxda_session"
_POLICY_FIELD = "_cxda_policy"

_FORBIDDEN_PARAM_KEYS = {"authtoken", "userkey", "requestchannel"}
_PAGE_SIZE_PARAM = "pagesize"
_API_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")


def parse_params(args):
    """解析 key=value 参数，并拒绝覆盖脚本管理的认证/渠道字段。"""
    params = {}
    for arg in args:
        if '=' in arg:
            k, v = arg.split('=', 1)
            k = k.strip()
            if not k:
                raise ValueError("查询参数名不能为空")
            if k.lower() in _FORBIDDEN_PARAM_KEYS:
                raise ValueError("禁止覆盖保留参数（脚本自动管理）: {}".format(k))
            # pageSize 由脚本统一管理，调用方提供的值不参与请求参数构造；
            # 业务请求统一使用接口返回的 maxPageSize。
            if k.lower() == _PAGE_SIZE_PARAM:
                continue
            params[k] = v.strip()
    return params


def _validate_api_id(api_id):
    """API ID 只允许安全标识符，阻断路径遍历和注入字符。"""
    if not isinstance(api_id, str) or not _API_ID_RE.fullmatch(api_id):
        raise ValueError("非法 API ID（仅允许字母数字下划线连字符）: {!r}".format(api_id))
    return api_id


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
        "session_id": uuid.uuid4().hex,
        "session_start": now.strftime(_TIME_FMT),
        "started_ts": now.timestamp(),
        "last_call_ts": now.timestamp(),
        "requires_confirmation": False,
        "confirmed_after_50": False,
        "confirmation_required_at_count": None,
        "confirmed_at": None,
        "pending_calls": [],
        "page_size_cache": {},
    }


def _ensure_ledger_confirmation_state(ledger):
    changed = False
    for key, default in (
        ("requires_confirmation", False),
        ("confirmed_after_50", False),
        ("confirmation_required_at_count", None),
        ("confirmed_at", None),
    ):
        if key not in ledger:
            ledger[key] = default
            changed = True

    if not isinstance(ledger.get("pending_calls"), list):
        ledger["pending_calls"] = []
        changed = True

    if not isinstance(ledger.get("page_size_cache"), dict):
        ledger["page_size_cache"] = {}
        changed = True

    if not ledger.get("session_id"):
        ledger["session_id"] = uuid.uuid4().hex
        changed = True

    return changed


def _clear_session_calls_log():
    save_shared_text(SESSION_CALLS_LOG_FILE, "")


def _read_session_calls_log(session_id=None):
    calls = []
    content = get_shared_text(SESSION_CALLS_LOG_FILE)
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            call = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(call, dict):
            continue
        if session_id and call.get("session_id") != session_id:
            continue
        calls.append(call)
    return calls


def _get_ledger_calls(ledger):
    if not isinstance(ledger, dict):
        return []

    calls = []
    legacy_calls = ledger.get("calls")
    if isinstance(legacy_calls, list):
        calls.extend(call for call in legacy_calls if isinstance(call, dict))

    calls.extend(_read_session_calls_log(ledger.get("session_id")))
    return calls


def _call_timestamp(call):
    ts = call.get("ts") if isinstance(call, dict) else None
    if ts is not None and not isinstance(ts, bool):
        try:
            return float(ts)
        except (ValueError, TypeError):
            pass

    text = call.get("time") if isinstance(call, dict) else None
    if isinstance(text, str) and text.strip():
        try:
            return datetime.strptime(text.strip(), _TIME_FMT).replace(tzinfo=_DISPLAY_TZ).timestamp()
        except ValueError:
            return None
    return None


def _format_session_call(call):
    return {
        "time": call.get("time", "-"),
        "api_id": call.get("api_id", ""),
        "consumed": call.get("consumed"),
    }


def _is_ledger_idle_expired(ledger, now, calls=None):
    if not isinstance(ledger, dict):
        return False

    last_ts = None
    for call in calls or []:
        call_ts = _call_timestamp(call)
        if call_ts is not None and (last_ts is None or call_ts > last_ts):
            last_ts = call_ts

    if last_ts is None:
        last_ts = ledger.get("last_call_ts") or ledger.get("started_ts")
    try:
        return (now.timestamp() - float(last_ts)) > SESSION_IDLE_MINUTES * 60
    except (ValueError, TypeError):
        return False


def _cleanup_pending_calls(ledger, calls, now):
    """清理已提交或超时的调用预留，返回账本是否发生变化。"""
    pending_calls = ledger.get("pending_calls", [])
    committed_ids = {
        call.get("call_id")
        for call in calls
        if isinstance(call, dict) and call.get("call_id")
    }
    now_ts = now.timestamp()
    retained = []
    for pending in pending_calls:
        if not isinstance(pending, dict):
            continue
        call_id = pending.get("call_id")
        created_ts = pending.get("created_ts")
        if not call_id or call_id in committed_ids:
            continue
        try:
            if now_ts - float(created_ts) > PENDING_CALL_TIMEOUT_SECONDS:
                continue
        except (ValueError, TypeError):
            continue
        retained.append(pending)

    changed = retained != pending_calls
    if changed:
        ledger["pending_calls"] = retained
    return changed


def _get_active_ledger_unlocked(now):
    """在 SESSION_LOCK_FILE 已持有的前提下读取或创建活动会话。"""
    ledger = get_shared_json(SESSION_LEDGER_FILE)

    # 无账本 / 空账本 / 空闲超时 → 开新会话
    if not isinstance(ledger, dict) or not ledger:
        ledger = _new_ledger(now)
        _clear_session_calls_log()
        save_shared_json(SESSION_LEDGER_FILE, ledger)
        return ledger, []

    changed = _ensure_ledger_confirmation_state(ledger)
    calls = _get_ledger_calls(ledger)
    if _cleanup_pending_calls(ledger, calls, now):
        changed = True
    if not ledger.get("pending_calls") and _is_ledger_idle_expired(ledger, now, calls):
        ledger = _new_ledger(now)
        _clear_session_calls_log()
        save_shared_json(SESSION_LEDGER_FILE, ledger)
        return ledger, []

    if changed:
        save_shared_json(SESSION_LEDGER_FILE, ledger)

    return ledger, calls


def _get_active_ledger(now):
    with shared_file_lock(SESSION_LOCK_FILE):
        return _get_active_ledger_unlocked(now)


def _reserve_billable_api_call(api_id, track_usage=True):
    """
    在业务请求前原子预留一个可能计费的调用槽位。

    把 pending 计入阈值判断，保证 49 个已计费调用时只有一个并发请求能继续；
    请求完成后再根据后端 consumePoints 提交或取消预留。
    """
    now = datetime.now()
    if not track_usage:
        ledger, _ = _get_active_ledger(now)
        return {
            "session_id": ledger.get("session_id"),
            "api_id": api_id,
        }, None

    with shared_file_lock(SESSION_LOCK_FILE):
        ledger, calls = _get_active_ledger_unlocked(now)
        pending_calls = ledger.get("pending_calls", [])
        effective_count = len(calls) + len(pending_calls)
        if (
            effective_count >= BILLABLE_CALL_CONFIRMATION_THRESHOLD
            and ledger.get("confirmed_after_50") is not True
        ):
            ledger["requires_confirmation"] = True
            ledger["confirmation_required_at_count"] = effective_count
            save_shared_json(SESSION_LEDGER_FILE, ledger)
            return None, effective_count

        reservation = {
            "call_id": uuid.uuid4().hex,
            "session_id": ledger.get("session_id"),
            "api_id": api_id,
            "created_ts": now.timestamp(),
        }
        pending_calls.append(reservation)
        ledger["pending_calls"] = pending_calls
        ledger["last_call_ts"] = now.timestamp()
        save_shared_json(SESSION_LEDGER_FILE, ledger)
        return reservation, None


def _remove_reservation(ledger, call_id):
    pending_calls = ledger.get("pending_calls", [])
    retained = [
        item for item in pending_calls
        if not isinstance(item, dict) or item.get("call_id") != call_id
    ]
    changed = retained != pending_calls
    if changed:
        ledger["pending_calls"] = retained
    return changed


def _finish_reserved_call(reservation, data):
    """原子提交成功计费记录；失败或零消耗只取消预留。"""
    if not isinstance(reservation, dict) or not reservation.get("call_id"):
        return

    now = datetime.now()
    call_id = reservation["call_id"]
    with shared_file_lock(SESSION_LOCK_FILE):
        ledger = get_shared_json(SESSION_LEDGER_FILE)
        if not isinstance(ledger, dict) or ledger.get("session_id") != reservation.get("session_id"):
            return

        _ensure_ledger_confirmation_state(ledger)
        calls = _get_ledger_calls(ledger)
        already_committed = any(
            isinstance(call, dict) and call.get("call_id") == call_id
            for call in calls
        )
        consumed = _to_number(data.get("consumePoints")) if isinstance(data, dict) else None
        is_billable = (
            isinstance(data, dict)
            and str(data.get("code")) == SUCCESS_CODE
            and consumed is not None
            and consumed > 0
        )
        if is_billable and not already_committed:
            call = {
                "call_id": call_id,
                "session_id": ledger.get("session_id"),
                "ts": now.timestamp(),
                "time": now.strftime(_TIME_FMT),
                "api_id": reservation.get("api_id", ""),
                "consumed": consumed,
            }
            append_shared_text(
                SESSION_CALLS_LOG_FILE,
                json.dumps(call, ensure_ascii=False, separators=(",", ":")) + "\n"
            )
        if _remove_reservation(ledger, call_id):
            ledger["last_call_ts"] = now.timestamp()
            save_shared_json(SESSION_LEDGER_FILE, ledger)


def _cancel_reserved_call(reservation):
    """业务请求异常时释放预留；若会话已重置则无需处理。"""
    if not isinstance(reservation, dict) or not reservation.get("call_id"):
        return
    with shared_file_lock(SESSION_LOCK_FILE):
        ledger = get_shared_json(SESSION_LEDGER_FILE)
        if not isinstance(ledger, dict) or ledger.get("session_id") != reservation.get("session_id"):
            return
        if _remove_reservation(ledger, reservation["call_id"]):
            save_shared_json(SESSION_LEDGER_FILE, ledger)


def _format_package_item(item):
    """格式化套餐额度明细，保持 package 子命令输出结构稳定。"""
    return {
        "relation_id": item.get("id", ""),
        "user_id": item.get("wsUserId", ""),
        "package_id": item.get("wsPackageId", ""),
        "package_name": item.get("packageName", "-"),
        "package_code": item.get("packageCode", ""),
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

    resp_data = http_post_form(
        f"{BASE_URL}/mall/api_getAuthList.htm",
        data=params
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
        "package_name": item.get("package_name", "-"),
        "balance": balance,
        "total_money": total_money,
        "integral": integral,
        "day_balance": item.get("day_balance", ""),
        "day_money": item.get("day_money", ""),
        "valid_end": item.get("valid_end", "-"),
    }


def _build_session_summary(include_packages=False):
    """构造当前会话汇总；套餐只在显式收尾时查询一次。"""
    with shared_file_lock(SESSION_LOCK_FILE):
        ledger = get_shared_json(SESSION_LEDGER_FILE)
        calls = _get_ledger_calls(ledger)
    visible_calls = [_format_session_call(call) for call in calls]
    total_consumed = 0
    for call in calls:
        num = _to_number(call.get("consumed"))
        if num is not None:
            total_consumed += num

    packages = []
    package_error = None
    if include_packages:
        try:
            package_result = _query_package_result(get_user_key())
        except Exception as exc:
            package_result = {
                "code": "10500",
                "msg": str(exc),
                "packages": [],
            }
        if str(package_result.get("code")) == SUCCESS_CODE:
            packages = [_format_session_package(item) for item in package_result.get("packages", [])]
        else:
            package_error = package_result.get("msg")

    return {
        "session_start": ledger.get("session_start") if isinstance(ledger, dict) else None,
        "call_count": len(calls),
        "total_consumed": total_consumed,
        "calls": visible_calls,
        "packages_included": bool(include_packages),
        "package_count": len(packages),
        "packages": packages,
        "package_error": package_error,
    }


def _with_session_summary(data, include_packages=False):
    """在业务输出中附加脚本生成的会话汇总，不修改后端原始对象。"""
    result = dict(data) if isinstance(data, dict) else {"data": data}
    try:
        result[_SESSION_SUMMARY_FIELD] = _build_session_summary(include_packages=include_packages)
    except Exception as exc:
        # 汇总是业务调用后的附加信息，异常时不得吞掉已经取得的业务数据。
        result[_SESSION_SUMMARY_FIELD] = {
            "session_start": None,
            "call_count": 0,
            "total_consumed": 0,
            "calls": [],
            "packages_included": bool(include_packages),
            "package_count": 0,
            "packages": [],
            "package_error": "会话汇总失败：{}".format(str(exc)),
        }
    return result


def _with_billing_policy(data, show_billing_info):
    """在每次业务命令结果中附加当前平台策略，供上级分析型 Skill 逐响应判断。"""
    result = dict(data) if isinstance(data, dict) else {"data": data}
    result[_POLICY_FIELD] = {
        "show_billing_info": bool(show_billing_info),
    }
    return result


# ── 接口最大分页缓存 ─────────────────────────────────────────────────

def _normalize_max_page_size(value):
    """将 maxPageSize 转成正整数，无法识别时返回 None。"""
    if value is None or isinstance(value, bool):
        return None
    try:
        text = str(value).strip()
        if text == "":
            return None
        number = int(float(text))
        return number if number > 0 else None
    except (ValueError, TypeError, OverflowError):
        return None


def _load_page_size_cache(session_id):
    """读取当前会话缓存；同一进程检测到会话切换时立即失效。"""
    global _PAGE_SIZE_CACHE
    if (
        isinstance(_PAGE_SIZE_CACHE, dict)
        and _PAGE_SIZE_CACHE.get("session_id") == session_id
        and isinstance(_PAGE_SIZE_CACHE.get("entries"), dict)
    ):
        return _PAGE_SIZE_CACHE["entries"]

    with shared_file_lock(SESSION_LOCK_FILE):
        ledger = get_shared_json(SESSION_LEDGER_FILE)
        entries = {}
        if isinstance(ledger, dict) and ledger.get("session_id") == session_id:
            stored = ledger.get("page_size_cache", {})
            if isinstance(stored, dict):
                for api_id, value in stored.items():
                    normalized = _normalize_max_page_size(value)
                    if normalized is not None:
                        entries[api_id] = normalized
    _PAGE_SIZE_CACHE = {
        "session_id": session_id,
        "entries": entries,
    }
    return entries


def _page_size_cache_key(api_id, params):
    """按接口和业务输入参数生成分页上限缓存键。"""
    normalized_params = {
        str(key): value
        for key, value in dict(params or {}).items()
        if str(key).lower() not in ("pagenum", "pagesize")
    }
    payload = json.dumps(
        normalized_params,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return "{}:{}".format(api_id, digest)


def _fetch_api_limit_setting(api_id, authtoken, params=None):
    """携带 authtoken 和业务输入参数查询当前条件下的最优分页大小。"""
    if not authtoken:
        raise RuntimeError("未找到 authtoken，请先通过 auth.py 完成认证")

    # 分页控制字段不是业务条件，也不应被转发给分页配置接口。尤其是
    # pageSize，必须避免调用方传入的值影响 maxPageSize 的计算。
    request_data = {
        key: value
        for key, value in dict(params or {}).items()
        if str(key).lower() not in (_PAGE_SIZE_PARAM, "pagenum")
    }
    request_data["authtoken"] = authtoken
    request_data["apiMain"] = api_id
    return http_post_form(
        f"{BASE_URL}/mall/api_getApiLimitSetting.htm",
        data=request_data,
    )


def _get_api_max_page_size(api_id, params, session_id, authtoken):
    """获取当前业务输入对应的最优分页大小，并按参数组合缓存。"""
    cache_key = _page_size_cache_key(api_id, params)
    # 同一进程内的并发首屏请求共享一个获取动作，避免多个线程同时发现
    # 缓存为空而重复调用 api_getApiLimitSetting。跨进程仍由会话账本缓存
    # 保证最终结果一致。
    with _PAGE_SIZE_LOCK:
        cache = _load_page_size_cache(session_id)
        if cache_key in cache:
            return cache[cache_key]

        data = _fetch_api_limit_setting(api_id, authtoken, params)
        max_page_size = _normalize_max_page_size(
            data.get("maxPageSize") if isinstance(data, dict) else None
        )
        if max_page_size is None:
            msg = data.get("msg") if isinstance(data, dict) else ""
            raise RuntimeError(
                "查询接口最大分页失败：{}".format(msg or "未返回有效 maxPageSize")
            )

        _cache_api_max_page_size(cache_key, data, session_id)
        return max_page_size


def _cache_api_max_page_size(cache_key, data, session_id):
    """查询成功后同步到当前进程与当前会话账本。"""
    max_page_size = _normalize_max_page_size(data.get("maxPageSize") if isinstance(data, dict) else None)
    if max_page_size is None:
        return

    cache = _load_page_size_cache(session_id)
    cache[cache_key] = max_page_size
    with shared_file_lock(SESSION_LOCK_FILE):
        ledger = get_shared_json(SESSION_LEDGER_FILE)
        if not isinstance(ledger, dict) or ledger.get("session_id") != session_id:
            return
        _ensure_ledger_confirmation_state(ledger)
        ledger["page_size_cache"][cache_key] = max_page_size
        save_shared_json(SESSION_LEDGER_FILE, ledger)


def _apply_default_page_size(api_id, params, session_id, authtoken):
    """忽略调用方 pageSize，统一使用接口返回的 maxPageSize。

    按当前业务条件取得（或复用当前会话缓存的）最大分页值，再覆盖为规范
    的 ``pageSize``。
    """
    normalized_params = {
        key: value
        for key, value in dict(params or {}).items()
        if str(key).lower() != _PAGE_SIZE_PARAM
    }
    normalized_params["pageSize"] = str(
        _get_api_max_page_size(
            api_id,
            normalized_params,
            session_id,
            authtoken,
        )
    )
    return normalized_params


# ── 子命令：api（业务数据接口查询）─────────────────────────────────────

def run_api(
    api_id,
    params,
    token,
    include_packages=False,
    include_summary=True,
    execution_meta=None,
    show_billing_info=None,
):
    """执行一次已鉴权业务调用；会话槽位使用两阶段预留/提交。"""
    if show_billing_info is None:
        show_billing_info = get_platform_show_billing_info()
    if isinstance(execution_meta, dict):
        execution_meta["business_http_started"] = False
    _validate_api_id(api_id)
    reservation, confirmation_required_count = _reserve_billable_api_call(
        api_id,
        track_usage=show_billing_info,
    )
    if confirmation_required_count is not None:
        result = {
            "error": "本轮会话已有 {} 个已计费或执行中的接口调用，请先获得用户确认后再继续。".format(
                confirmation_required_count
            ),
            "status": CONFIRMATION_REQUIRED_STATUS,
            "call_count": confirmation_required_count,
            "next_action": "请用户确认是否继续调用；确认后执行 query.py session confirm",
        }
        return (
            _with_session_summary(result, include_packages=False)
            if include_summary else result
        )

    try:
        normalized_params = _apply_default_page_size(
            api_id,
            params,
            reservation.get("session_id"),
            token,
        )
        request_params = {"authtoken": token}
        request_params.update(normalized_params)
        if isinstance(execution_meta, dict):
            execution_meta["business_http_started"] = True
        data = http_get(
            f"{BASE_URL}/webservice/cxdata/{api_id}.htm",
            params=request_params
        )
    except Exception:
        try:
            _cancel_reserved_call(reservation)
        except Exception:
            pass
        raise

    bookkeeping_warning = None
    if show_billing_info:
        try:
            _finish_reserved_call(reservation, data)
        except Exception as exc:
            try:
                _cancel_reserved_call(reservation)
            except Exception:
                pass
            bookkeeping_warning = "会话记账失败：{}".format(type(exc).__name__)

    result = dict(data) if isinstance(data, dict) else {"data": data}
    if not show_billing_info:
        result.pop("consumePoints", None)
        result.pop(_SESSION_SUMMARY_FIELD, None)
    if bookkeeping_warning and show_billing_info:
        result["_cxda_runtime_warning"] = bookkeeping_warning
    if include_summary and show_billing_info:
        return _with_session_summary(
            result,
            include_packages=include_packages and show_billing_info,
        )
    return result


def cmd_api(api_id, params, include_packages=False):
    """编排协议检查、鉴权、单次业务调用和本地会话汇总。"""
    show_billing_info = get_platform_show_billing_info()

    def emit(data):
        output_json(_with_billing_policy(data, show_billing_info))

    try:
        _validate_api_id(api_id)
    except ValueError as exc:
        emit({"error": str(exc), "status": "failed"})
        return

    accepted, error_response = check_terms_accepted()
    if not accepted:
        emit(error_response)
        return

    try:
        token = ensure_token(emit_error=False)
        result = run_api(
            api_id,
            params,
            token=token,
            include_packages=include_packages and show_billing_info,
            include_summary=show_billing_info,
            show_billing_info=show_billing_info,
        )
        emit(result)
    except AuthenticationRequiredError as exc:
        emit(exc.response)
    except Exception as exc:
        emit({"error": str(exc), "status": "failed"})



# ── 子命令：session（会话积分统计）──────────────────────────────────────

def cmd_session(action):
    """
    会话积分维护命令。api 会隐式开始会话并内联汇总。

      start   开始/重置当前会话（清空账本，记录起始时间）
      summary 汇总当前会话的消耗（合计 + 明细）和各套餐剩余积分
      confirm 记录用户已确认超过 50 次后继续调用
      reset   清空当前会话账本
    """
    show_billing_info = get_platform_show_billing_info()

    def emit(data):
        output_json(_with_billing_policy(data, show_billing_info))

    if not show_billing_info:
        emit({"success": True})
        return

    # summary 需要查询套餐额度，需要协议前置
    if action == "summary":
        accepted, error_response = check_terms_accepted()
        if not accepted:
            emit(error_response)
            return

    now = datetime.now()

    if action in ("start", "reset", "confirm"):
        with shared_file_lock(SESSION_LOCK_FILE):
            ledger = get_shared_json(SESSION_LEDGER_FILE)
            ledger_changed = False
            if isinstance(ledger, dict) and ledger:
                if _ensure_ledger_confirmation_state(ledger):
                    ledger_changed = True
                calls = _get_ledger_calls(ledger)
                if _cleanup_pending_calls(ledger, calls, now):
                    ledger_changed = True
            else:
                ledger = {}
                calls = []

            if action in ("start", "reset") and ledger.get("pending_calls", []):
                emit({
                    "success": False,
                    "status": "session_busy",
                    "message": "仍有业务请求执行中，暂不能重置会话",
                    "pending_count": len(ledger["pending_calls"]),
                })
                return

            if action == "start":
                ledger = _new_ledger(now)
                _clear_session_calls_log()
                save_shared_json(SESSION_LEDGER_FILE, ledger)
                emit({
                    "success": True,
                    "message": "会话已开始",
                    "session_start": ledger["session_start"],
                })
                return

            if action == "reset":
                save_shared_json(SESSION_LEDGER_FILE, {})
                _clear_session_calls_log()
                emit({"success": True, "message": "会话账本已清空"})
                return

            if not isinstance(ledger, dict) or not ledger:
                emit({
                    "success": False,
                    "status": "confirmation_not_required",
                    "message": "没有可确认的会话账本",
                })
                return

            effective_count = len(calls) + len(ledger.get("pending_calls", []))
            if effective_count < BILLABLE_CALL_CONFIRMATION_THRESHOLD:
                if ledger_changed:
                    save_shared_json(SESSION_LEDGER_FILE, ledger)
                emit({
                    "success": False,
                    "status": "confirmation_not_required",
                    "message": "当前会话尚未达到需要确认的调用次数",
                    "call_count": len(calls),
                    "pending_count": len(ledger.get("pending_calls", [])),
                })
                return

            ledger["requires_confirmation"] = False
            ledger["confirmed_after_50"] = True
            ledger["confirmation_required_at_count"] = (
                ledger.get("confirmation_required_at_count") or effective_count
            )
            ledger["confirmed_at"] = now.strftime(_TIME_FMT)
            save_shared_json(SESSION_LEDGER_FILE, ledger)
            emit({
                "success": True,
                "message": "已确认继续调用",
                "call_count": len(calls),
                "pending_count": len(ledger.get("pending_calls", [])),
                "confirmed_at": ledger["confirmed_at"],
            })
            return

    # summary
    emit({"success": True, **_build_session_summary(include_packages=True)})


# ── 子命令：page-size（接口分页大小查询）────────────────────────────────

def cmd_page_size(api_id, params=None):
    """
    查询接口分页大小限制

    认证方式：authtoken
    """
    try:
        _validate_api_id(api_id)
    except ValueError as exc:
        output_error(str(exc))
        return

    accepted, error_response = check_terms_accepted()
    if not accepted:
        output_json(error_response)
        return

    try:
        token = ensure_token(emit_error=False)
        data = _fetch_api_limit_setting(api_id, token, params)
        ledger, _calls = _get_active_ledger(datetime.now())
        _cache_api_max_page_size(
            _page_size_cache_key(api_id, params),
            data,
            ledger.get("session_id"),
        )
        output_json(data)
    except AuthenticationRequiredError as exc:
        output_json(exc.response)
    except Exception as e:
        output_error(str(e))


# ── 子命令：package（套餐额度查询）──────────────────────────────────────

def cmd_package(api_main=""):
    """
    查询用户套餐额度

    认证方式：userKey
    """
    show_billing_info = get_platform_show_billing_info()

    def emit(data):
        output_json(_with_billing_policy(data, show_billing_info))

    if not show_billing_info:
        emit({"success": True})
        return

    if api_main:
        try:
            _validate_api_id(api_main)
        except ValueError as exc:
            emit({
                "code": "10400",
                "msg": str(exc),
                "package_count": 0,
                "packages": [],
            })
            return

    accepted, error_response = check_terms_accepted()
    if not accepted:
        emit(error_response)
        return

    user_key = get_user_key()

    if not user_key:
        emit({
            "code": "10500",
            "msg": "未找到 CXDA_USER_KEY，请先通过 auth.py 完成认证",
            "package_count": 0,
            "packages": [],
        })
        return

    try:
        emit(_query_package_result(user_key, api_main))
    except Exception as e:
        emit({"code": "10500", "msg": str(e), "package_count": 0, "packages": []})


# ── 入口 ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="CXDA Skill - 统一查询工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
子命令说明：

  api <API_ID> [key=value ...] [--finalize]
    统一编排协议检查、token、隐式会话、业务查询和积分汇总。
    authtoken 由脚本自动管理（缓存300秒，过期自动刷新），无需手动传入。
    默认输出本地 _cxda_session，不请求套餐；--finalize 才查询一次套餐剩余额度。
    返回数据经 gzip+base64 编码，脚本自动解码。
    参数以 key=value 格式传入，可传多个。

    用法：
      python query.py api <API_ID> key1=value1 key2=value2 ...

    示例：
      python query.py api getStkBasicInfoByCond-K stkCode=600519
      python query.py api getCooWineCateDailQuoByWineName wineName=飞天茅台
      python query.py api getCooWineCateDailQuoByWineName wineName=飞天茅台 --finalize

    输出 JSON 格式：
      成功 → 接口返回的业务数据（JSON）和 _cxda_session
      需认证 → status 为 terms_not_accepted 或 authentication_required
      失败 → {"error": "错误信息", "status": "failed"}

  page-size <API_ID>
    查询指定接口的分页大小限制（每次请求最大返回条数）。
    使用脚本自动管理的 authtoken 认证，无需额外参数。

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
      每个 packages 项包含：relation_id, user_id, package_id, package_name, package_code, status, valid_start, valid_end, total_money, balance, day_balance, day_money
        """
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # api
    p_api = subparsers.add_parser(
        "api",
        help="调用业务数据接口",
        description="统一编排鉴权、隐式会话、业务查询和积分汇总。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python query.py api getStkBasicInfoByCond-K stkCode=600519
  python query.py api getCooWineCateDailQuoByWineName wineName=飞天茅台
  python query.py api getCooWineCateDailQuoByWineName wineName=飞天茅台 pageNum=1

说明：
  - API_ID 为接口访问标识，由 Skill 的 SKILL.md 提供
  - 查询参数以 key=value 格式传入，支持多个参数
  - pageSize 由脚本统一查询并使用该接口的 maxPageSize；调用方传入的 pageSize 会被忽略
  - authtoken 由脚本自动管理，无需手动传入
  - 返回数据自动解码（gzip+base64），直接输出 JSON
  - _cxda_session 默认只返回本轮本地累计；--finalize 才查询套餐剩余额度
  - 仅当返回 terms_not_accepted 或 authentication_required 时，才使用 auth.py 认证
        """
    )
    p_api.add_argument("api_id", help="接口访问标识（API ID）")
    p_api.add_argument("params", nargs="*", help="查询参数，格式 key=value（可多个）")
    p_api.add_argument("--finalize", action="store_true", help="本次调用完成后查询一次套餐剩余额度")

    # page-size
    p_ps = subparsers.add_parser(
        "page-size",
        help="查询接口分页大小限制",
        description="查询指定接口的分页大小限制（每次请求最大返回条数）。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python query.py page-size getStkBasicInfoByCond-K stkCode=600519

说明：
  - 业务输入参数以 key=value 格式传入，用于计算当前查询条件下的最优分页大小
  - 返回当前查询条件下每次请求允许的最大返回条数
  - api 子命令会自动查询 maxPageSize；本命令仅用于排查或确认分页限制
  - 使用脚本自动管理的 authtoken 认证
        """
    )
    p_ps.add_argument("api_id", help="接口访问标识（API ID）")
    p_ps.add_argument("params", nargs="*", help="查询参数，格式 key=value（可多个）")

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
  - 每个套餐包含：套餐关系ID、用户ID、套餐ID、套餐名称、套餐编码、状态、有效期、总积分、剩余积分、每日积分、每日剩余积分
  - valid_start、valid_end 固定输出为北京时间 yyyy-MM-dd HH:mm:ss
        """
    )
    p_pkg.add_argument("--api-main", default="", help="接口访问标识（可选，传入时只返回包含该接口的套餐）")

    # session
    p_session = subparsers.add_parser(
        "session",
        help="会话积分维护",
        description="会话积分维护命令；api 会隐式开始会话并在 _cxda_session 中内联汇总。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python query.py session start      # 会话开始时调用，重置账本
  python query.py session confirm    # 用户确认超过50次后继续调用
  python query.py session summary    # 会话结束时调用，汇总本次消耗和套餐剩余额度
  python query.py session reset      # 清空账本

说明：
  - 正常业务查询无需显式 start；未使用 api --finalize 时，最终调用一次 summary
  - api 子命令在「成功(code=10000) 且 消耗>0」时自动记账，失败/0消耗不计入
  - 当前会话已有50次成功计费调用且未确认时，api 会在调用前返回 confirmation_required
  - 用户确认继续后，先执行 session confirm，再继续 api 调用
  - summary 返回 call_count（会话调用接口数量）、total_consumed（本次会话消耗合计）、calls（明细）
  - summary 同时返回 packages，每个套餐包含：package_name、balance、total_money、integral、day_balance、day_money、valid_end
  - 不同套餐的剩余积分不能混合合计，必须逐套餐展示
        """
    )
    p_session.add_argument("action", choices=["start", "confirm", "summary", "reset"], help="会话操作")

    args = parser.parse_args()

    if args.command == "api":
        try:
            params = parse_params(args.params)
        except ValueError as exc:
            output_json(_with_billing_policy(
                {"error": str(exc), "status": "failed"},
                get_platform_show_billing_info(),
            ))
            return
        cmd_api(args.api_id, params, include_packages=args.finalize)
    elif args.command == "page-size":
        try:
            params = parse_params(args.params)
        except ValueError as exc:
            output_error(str(exc))
            return
        cmd_page_size(args.api_id, params)
    elif args.command == "package":
        cmd_package(args.api_main)
    elif args.command == "session":
        cmd_session(args.action)


if __name__ == "__main__":
    main()
