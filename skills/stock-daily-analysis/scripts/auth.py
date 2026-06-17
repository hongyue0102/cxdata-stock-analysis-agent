# -*- coding: utf-8 -*-
"""
CXDA Skill 授权模块

提供服务协议确认、手机号验证码登录、认证状态管理能力。
对接后端接口：api_getVerify（发送验证码）、api_verifyLogin（验证码登录）。

用法：
  python auth.py terms-check                      # 检查协议接受状态
  python auth.py terms-accept                     # 接受服务协议
  python auth.py terms-decline                    # 拒绝服务协议
  python auth.py send-code --phone 13812345678    # 发送验证码
  python auth.py verify --phone 13812345678 --code 123456  # 验证码校验
  python auth.py status                           # 查看认证状态
"""

import argparse
import json
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from common import (
    BASE_URL,
    HEADERS,
    PROXIES,
    REQUEST_CHANNEL,
    get_user_key,
    set_user_key,
    get_cached_auth,
    save_auth,
    check_terms_accepted,
    mask_user_key,
)


# ── 常量 ──────────────────────────────────────────────────────────────

TERMS_ACCEPTED_KEY = "terms_accepted"

# 协议链接
PRIVACY_URL = "https://cdp.ccxe.com.cn/clause/privacy"
SERVICE_URL = "https://cdp.ccxe.com.cn/clause/service"
VIP_URL = "https://cdp.ccxe.com.cn/clause/vip"


# ── 手机号展示工具 ────────────────────────────────────────────────────


def _mask_phone(phone: str) -> str:
    """手机号脱敏：138****5678"""
    return phone[:3] + "****" + phone[-4:]


# ── 命令：terms-check ─────────────────────────────────────────────────

def cmd_terms_check():
    """检查用户是否已接受服务协议"""
    auth = get_cached_auth()
    accepted = auth.get(TERMS_ACCEPTED_KEY, False)

    print(json.dumps({
        "success": True,
        "terms_accepted": accepted,
        "message": "用户已接受服务协议" if accepted else "用户尚未接受服务协议"
    }, ensure_ascii=False))


# ── 命令：terms-accept ────────────────────────────────────────────────

def cmd_terms_accept():
    """用户接受服务协议"""
    auth = get_cached_auth()
    auth[TERMS_ACCEPTED_KEY] = True
    save_auth(auth)

    print(json.dumps({
        "success": True,
        "terms_accepted": True,
        "message": "已接受服务协议，可以继续使用"
    }, ensure_ascii=False))


# ── 命令：terms-decline ───────────────────────────────────────────────

def cmd_terms_decline():
    """用户拒绝服务协议"""
    auth = get_cached_auth()
    auth[TERMS_ACCEPTED_KEY] = False
    # 同时清除登录状态
    auth["CXDA_USER_KEY"] = ""
    auth["authtoken"] = ""
    auth["authtoken_expire"] = ""
    save_auth(auth)

    print(json.dumps({
        "success": True,
        "terms_accepted": False,
        "message": "已拒绝服务协议，无法继续使用相关功能"
    }, ensure_ascii=False))


# ── 命令：send-code ──────────────────────────────────────────────────

def cmd_send_code(phone: str):
    """
    发送验证码

    流程：
    1. 调用后端 api_getVerify 接口发送短信验证码
    2. 原样返回后端 AjaxResult：code/msg/data
    """
    accepted, error_response = check_terms_accepted()
    if not accepted:
        print(json.dumps(error_response, ensure_ascii=False))
        return
    
    try:
        import requests

        params = {"phone": phone}
        if REQUEST_CHANNEL:
            params["requestChannel"] = REQUEST_CHANNEL

        resp = requests.get(
            f"{BASE_URL}/mall/api_getVerify.htm",
            params=params,
            headers=HEADERS,
            proxies=PROXIES
        )
        resp_data = resp.json()
        print(json.dumps(resp_data, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({
            "code": "10500",
            "msg": f"网络异常：{str(e)}",
            "data": ""
        }, ensure_ascii=False))


# ── 命令：verify ─────────────────────────────────────────────────────

def cmd_verify(phone: str, code: str):
    """
    验证验证码并获取 CXDA_USER_KEY

    流程：
    1. 调用后端 api_verifyLogin 接口验证
    2. code=10000 时将 data 中的 userKey 写入缓存
    3. 原样返回后端 AjaxResult：code/msg/data
    """
    accepted, error_response = check_terms_accepted()
    if not accepted:
        print(json.dumps(error_response, ensure_ascii=False))
        return
    
    phone_masked = _mask_phone(phone)

    try:
        import requests

        params = {"phone": phone, "verifyCode": code}
        if REQUEST_CHANNEL:
            params["requestChannel"] = REQUEST_CHANNEL

        resp = requests.get(
            f"{BASE_URL}/mall/api_verifyLogin.htm",
            params=params,
            headers=HEADERS,
            proxies=PROXIES
        )
        resp_data = resp.json()

        if str(resp_data.get("code")) == "10000":
            user_key = resp_data.get("data", "")
            if isinstance(user_key, str):
                user_key = user_key.strip()
            if not user_key:
                print(json.dumps({
                    "code": "10500",
                    "msg": "接口返回成功但 userKey 为空",
                    "data": "",
                }, ensure_ascii=False))
                return

            # 写入缓存
            auth_data = get_cached_auth()
            auth_data.update({
                "CXDA_USER_KEY": user_key,
                "phone_masked": phone_masked,
                "authed_at": int(time.time())
            })
            save_auth(auth_data)

            safe_resp_data = dict(resp_data)
            safe_resp_data["data"] = mask_user_key(user_key)
            print(json.dumps(safe_resp_data, ensure_ascii=False))
        else:
            print(json.dumps(resp_data, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({
            "code": "10500",
            "msg": f"网络异常：{str(e)}",
            "data": "",
        }, ensure_ascii=False))


# ── 命令：status ─────────────────────────────────────────────────────

def cmd_status():
    """查看当前认证状态（本地检查缓存）"""
    user_key = get_user_key()
    auth = get_cached_auth()
    phone_masked = auth.get("phone_masked", "")
    authed_at = auth.get("authed_at", "")
    terms_accepted = auth.get(TERMS_ACCEPTED_KEY, False)

    if user_key:
        print(json.dumps({
            "success": True,
            "authenticated": True,
            "terms_accepted": terms_accepted,
            "phone_masked": phone_masked,
            "authed_at": authed_at,
            "CXDA_USER_KEY": mask_user_key(user_key),
            "message": "已认证"
        }, ensure_ascii=False))
    else:
        print(json.dumps({
            "success": True,
            "authenticated": False,
            "terms_accepted": terms_accepted,
            "message": "未认证，请先完成协议确认并通过 send-code + verify 完成认证"
        }, ensure_ascii=False))


# ── 入口 ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="CXDA Skill 用户认证工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
子命令说明：

  status
    查看当前认证状态（本地检查，不调用远程接口）。
    返回 authenticated=true/false、terms_accepted=true/false、CXDA_USER_KEY（脱敏）等。

  terms-check
    检查用户是否已接受服务协议。
    返回 terms_accepted=true/false。首次使用时必须先引导用户接受协议。

  terms-accept
    标记用户已接受服务协议。用户输入手机号即视为同意。
    接受后状态持久化存储，同一设备后续无需重复确认。

  terms-decline
    标记用户拒绝服务协议。同时清除本地 CXDA_USER_KEY、authtoken、authtoken_expire。
    拒绝后无法使用任何功能。

  send-code --phone <手机号>
    向用户手机号发送短信验证码。
    手机号校验由后端执行。
    验证码有效期5分钟。
    成功后提示用户查看短信并告知验证码。

  verify --phone <手机号> --code <验证码>
    验证短信验证码，验证成功后自动将 CXDA_USER_KEY 写入本地缓存。
    验证码校验由后端执行。
    成功后所有 CXDA Skill 共享此认证状态，无需重复认证。

认证流程顺序：
  1. terms-check → 是否已接受协议？
     ├── false → 引导用户接受（terms-accept）
     └── true  → 继续
  2. status → 是否已认证？
     ├── false → 引导手机号验证（send-code → verify）
     └── true  → 可以使用接口
        """
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # terms-check
    subparsers.add_parser(
        "terms-check",
        help="检查用户是否已接受服务协议",
        description="检查用户是否已接受《财新数据隐私政策》《用户服务协议》《付费用户服务协议》。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
输出 JSON 格式：
  {"success": true, "terms_accepted": true/false, "message": "..."}

说明：
  - terms_accepted=true  → 用户已接受，可继续认证流程
  - terms_accepted=false → 需要引导用户阅读协议并确认
  - 协议接受状态持久化存储，同一设备后续无需重复确认
        """
    )

    # terms-accept
    subparsers.add_parser(
        "terms-accept",
        help="接受服务协议",
        description="标记用户已接受全部服务协议（隐私政策、用户服务协议、付费用户服务协议）。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
输出 JSON 格式：
  {"success": true, "terms_accepted": true, "message": "已接受服务协议，可以继续使用"}

说明：
  - 用户输入手机号即视为同意协议
  - 状态持久化存储，后续无需重复确认
        """
    )

    # terms-decline
    subparsers.add_parser(
        "terms-decline",
        help="拒绝服务协议",
        description="标记用户拒绝服务协议，同时清除本地认证信息。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
输出 JSON 格式：
  {"success": true, "terms_accepted": false, "message": "已拒绝服务协议，无法继续使用相关功能"}

说明：
  - 同时清除本地 CXDA_USER_KEY、authtoken、authtoken_expire
  - 拒绝后无法使用任何功能
        """
    )

    # send-code
    p_sms = subparsers.add_parser(
        "send-code",
        help="发送短信验证码",
        description="向用户手机号发送短信验证码，用于完成账号认证。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python auth.py send-code --phone 13812345678

输出 JSON 格式：
  成功 → {"code": "10000", "msg": "验证码发送成功,请用手机号：13812345678查收验证码", "data": ""}
  失败 → {"code": "10500", "msg": "后端返回的失败原因", "data": ""}

说明：
  - 手机号格式与频率限制由后端校验
  - 验证码有效期5分钟
  - 成功后告知用户查看短信，等待用户告知验证码
        """
    )
    p_sms.add_argument("--phone", required=True, help="手机号（由后端校验）")

    # verify
    p_verify = subparsers.add_parser(
        "verify",
        help="验证码校验并获取 CXDA_USER_KEY",
        description="验证短信验证码，成功后自动将 CXDA_USER_KEY 写入本地缓存。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python auth.py verify --phone 13812345678 --code 123456

输出 JSON 格式：
  成功 → {"code": "10000", "msg": "登录成功返回userKey", "data": "xxx"}
  失败 → {"code": "10500", "msg": "后端返回的失败原因", "data": ""}

说明：
  - 验证码格式和有效性由后端校验
  - 验证成功后 data 中的 CXDA_USER_KEY 自动写入缓存，所有 CXDA Skill 共享
  - 验证码错误或过期时可重新发送（send-code）
        """
    )
    p_verify.add_argument("--phone", required=True, help="手机号（由后端校验）")
    p_verify.add_argument("--code", required=True, help="短信验证码（由后端校验）")

    # status
    subparsers.add_parser(
        "status",
        help="查看当前认证状态",
        description="本地检查认证状态（不调用远程接口），返回认证信息。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
输出 JSON 格式：
  已认证 → {"success": true, "authenticated": true, "terms_accepted": true, "CXDA_USER_KEY": "xxxx****xxxx", ...}
  未认证 → {"success": true, "authenticated": false, "terms_accepted": true/false, ...}

说明：
  - 纯本地检查，不发起网络请求
  - authenticated=true 表示用户已完成手机号验证
  - terms_accepted=true 表示用户已接受服务协议
  - 两者都为 true 才能正常使用数据接口
        """
    )

    args = parser.parse_args()

    if args.command == "terms-check":
        cmd_terms_check()
    elif args.command == "terms-accept":
        cmd_terms_accept()
    elif args.command == "terms-decline":
        cmd_terms_decline()
    elif args.command == "send-code":
        cmd_send_code(args.phone)
    elif args.command == "verify":
        cmd_verify(args.phone, args.code)
    elif args.command == "status":
        cmd_status()


if __name__ == "__main__":
    main()
