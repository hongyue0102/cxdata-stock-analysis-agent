# 认证流程详细说明

> 本文件由 SKILL.md 主流程按需引用，不可独立执行。

---

## 服务协议确认

> **法律合规要求**：在使用本 Skill 的任何功能前，必须确认用户已阅读并接受以下三份协议。

**协议链接：**
- [《财新数据隐私政策》](https://cdp.ccxe.com.cn/clause/privacy)
- [《财新数据用户服务协议》](https://cdp.ccxe.com.cn/clause/service)
- [《财新数据付费用户服务协议》](https://cdp.ccxe.com.cn/clause/vip)

**协议检查命令：**

```bash
$PYTHON "$AUTH_SCRIPT" terms-check
```

**返回结果：**
- `terms_accepted: true` → 用户已接受，可继续认证流程
- `terms_accepted: false` → 用户未接受，需要引导用户阅读并确认

**协议未接受时的处理流程：**

```
├────────────────────────────────────────────────────────────────────────────┐
│  用户未接受协议时，引导完成协议确认：                                             │
│                                                                            │
│  1. 展示官方声明与协议确认（必须使用以下原文，不得修改表述样式或内容）：                │
│                                                                            │
│  继续使用本 Skill 即表示您已阅读并同意以下协议的全部内容 ：                          │
│  - [《财新数据隐私政策》](https://cdp.ccxe.com.cn/clause/privacy)              │
│  - [《财新数据用户服务协议》](https://cdp.ccxe.com.cn/clause/service)           │
│  - [《财新数据付费用户服务协议》](https://cdp.ccxe.com.cn/clause/vip)            │
│                                                                             │
│  如果同意请输入您的手机号，我来为您发送验证码完成账号认证。                            │
│                                                                             │
│  2. 用户输入'查看全文'时：                                                      │
│   使用系统默认浏览器打开对应协议内容，逐条展示后重新询问是否同意                        │
│   → 打开完成后重新询问是否同意                                                   │
│                                                                             │
│  3. 用户接受后（直接输入手机号）：                                                │
│   $PYTHON "$AUTH_SCRIPT" terms-accept                                        │
│   → 用户输入手机号即视为同意，跳过询问直接发送验证码                                  │
│                                                                              │
│  4. 用户明确拒绝后执行：                                                         │
│   $PYTHON "$AUTH_SCRIPT" terms-decline                                       │
│   → 告知用户无法使用服务，结束对话                                                │
└──────────────────────────────────────────────────────────────────────────────┘
```

**注意事项**

- 《财新数据隐私政策》链接：https://cdp.ccxe.com.cn/clause/privacy
- 《财新数据用户服务协议》链接：https://cdp.ccxe.com.cn/clause/service
- 《财新数据付费用户服务协议》链接：https://cdp.ccxe.com.cn/clause/vip
- 展示协议部分时必须使用原文，不得修改表述样式或内容

> **重要：**用户接受协议后，`terms_accepted` 状态会持久化存储在本地缓存中
> （`~/.cxda-cache/.shared/cxda_auth.json`），同一设备后续调用无需重复确认。
> 如需撤销接受，可使用 `terms-decline` 命令。

---

## 认证状态检查

> 本轮首次业务查询前必须检查用户认证状态，确认 CXDA_USER_KEY 是否有效。普通已认证查询不需要重复展示认证话术。

**状态检查命令：**

```bash
$PYTHON "$AUTH_SCRIPT" status
```

**返回结果：**
- `authenticated: true` → 用户已认证，可继续使用功能
- `authenticated: false` → 用户未认证，需要引导完成认证流程

**已认证时**：继续执行 SKILL.md 的主流程。`status` 输出的 `CXDA_USER_KEY` 已脱敏，仅用于确认认证状态；不要向用户展示、复述或记录该字段。

**未认证时**：引导用户完成认证：

```
您还未完成财新数据认证，需要先验证手机号才能使用数据接口。
请告诉我您的手机号，我来帮您发送验证码。
```

按如下认证流程完成登录，然后重新执行 status 确认认证状态。

> **重要：**认证成功后，`CXDA_USER_KEY` 会持久化存储在本地缓存中
> （`~/.cxda-cache/.shared/cxda_auth.json`），同一设备上的所有 CXDA Skill 共享此认证状态，
> 无需重复认证。

---

## 认证流程

### 发送验证码

```bash
$PYTHON "$AUTH_SCRIPT" send-code --phone <手机号>
```

**输出 JSON 字段：**
- `code`：后端返回码，`10000` 表示成功，`10500` 表示失败
- `msg`：后端返回消息；失败原因直接读取该字段
- `data`：后端返回数据，发送验证码时通常为空

**成功 →** 告知用户：
```
验证码已发送至手机 xxx****xxxx，请打开手机短信查看验证码，5分钟内有效。
```

**失败 →** 保留后端 `code/msg/data` 结构；直接按后端 `msg` 告知用户，并根据消息判断是否需要用户更正手机号、等待冷却时间或稍后重试。

不要在短信接口返回失败后反复重试；手机号为空、手机号格式错误、频率限制或网络异常时，先向用户说明后端 `msg` 并等待用户补充或稍后再试。

### 验证验证码

```bash
$PYTHON "$AUTH_SCRIPT" verify --phone <完整手机号> --code <4-6位验证码>
```

**输出 JSON 字段：**
- `code`：后端返回码，`10000` 表示成功，`10500` 表示失败
- `msg`：后端返回消息；失败原因直接读取该字段
- `data`：`code=10000` 时为 `CXDA_USER_KEY`

**成功 →** 认证信息已保存，命令输出只展示脱敏值。告知用户：
```
✅ 认证成功！您现在可以使用财新数据接口了。
```

验证成功后，重新执行 status 确认认证状态。

**失败 →** 保留后端 `code/msg/data` 结构；直接按后端 `msg` 告知用户。验证码错误或失效时最多引导用户重新发送或重新输入；不要在没有新验证码或新手机号的情况下连续重复调用。

---

## 认证接口返回码

认证接口与后端 `mall/com/caixin/mall/action/UserApiAction.java` 保持一致，不另起本地错误码体系：

| 接口 | 成功返回 | 失败返回 | 失败原因来源 |
|------|----------|----------|--------------|
| `api_getVerify` | `code="10000"`，`msg` 为发送成功提示，`data` 通常为空 | `code="10500"`，`msg` 为异常消息，`data` 为空 | `UserDataApiServiceImpl.getVerify` 抛出的消息，如手机号为空、手机号格式错误、请 N 秒后重试、操作过于频繁 |
| `api_verifyLogin` | `code="10000"`，`msg="登录成功返回userKey"`，`data` 为 userKey | `code="10500"`，`msg` 为异常消息，`data` 为空 | `UserDataApiServiceImpl.verifyLogin` 抛出的消息，如未获取验证码或验证码已失效、验证码错误 |
| `api_getAuthList` | `code="10000"`，`msg="返回权限清单成功"`，`data` 为权限清单 | `code="10500"`，`msg` 为异常消息，`data` 为空 | `UserDataApiServiceImpl.getAuthList` 抛出的消息，如 userKey 不合法 |

Agent 处理失败时只读取并转述 `msg`，不要自行归类或改写后端返回结构。

---

## 认证数据存储

认证成功后，以下数据写入本地共享缓存（`~/.cxda-cache/.shared/cxda_auth.json`）：

```json
{
  "terms_accepted": true,
  "CXDA_USER_KEY": "xxxxxxxx",
  "authtoken": "xxxxxxxx",
  "authtoken_expire": "2026-06-03 15:30:00",
  "phone_masked": "138****5678",
  "authed_at": 1748928000
}
```

- **terms_accepted**：用户是否已接受服务协议，同一设备后续使用无需重复确认
- **CXDA_USER_KEY**：用户密钥，所有 CXDA Skill 共享，调用数据接口时使用
- **authtoken**：接口访问令牌，由 `common.py` 自动管理（300秒缓存，过期自动刷新）
- **phone_masked**：脱敏手机号，用于展示认证状态
- **authed_at**：认证时间戳（Unix 时间）

### 跨 Skill 共享机制

```
用户通过 Skill A 确认协议 + 认证 → 数据写入 ~/.cxda-cache/.shared/cxda_auth.json
                              ↓
用户使用 Skill B → common.py 从 ~/.cxda-cache/.shared/cxda_auth.json 读取
                  → terms_accepted=true, CXDA_USER_KEY 有效
                              ↓
                    ✅ 无需重复确认协议，无需重复认证
```

> 后续下载的任何 CXDA Skill 均自动共享协议状态和认证状态，用户只需操作一次。
