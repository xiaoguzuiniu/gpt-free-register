# -*- coding: utf-8 -*-
"""
注册成功后的 Codex OAuth 授权模块（2026-06-15 改造：全新 session + 接码）。

旧方案"复用注册的已登录 session"会撞 /choose-an-account 卡死（React SPA 解析不出
可提交字段）。新方案改为用**全新干净 session**从头登录，走 OpenAI 标准风控路径，
手机号验证靠接码平台 GrizzlySMS 自动收码。

完整接口链（2026-06-15 浏览器抓包确认，均 POST auth.openai.com，json）：
    1. 提交邮箱   /api/accounts/authorize/continue  {"username":{"kind":"email","value":邮箱}}  带 sentinel(authorize_continue)
    2. 验邮箱码   /api/accounts/email-otp/validate   {"code":"xxx"}                            带 sentinel(authorize_continue)
    3. 提交手机号 /api/accounts/add-phone/send       {"phone_number":"+1xxx","channel":"sms"}  无需 sentinel
    4. 验手机码   /api/accounts/phone-otp/validate   {"code":"xxx"}                            无需 sentinel
    5. 选 workspace /api/accounts/workspace/select   {"workspace_id":"<uuid>"}                  无需 sentinel
       workspace_id 从 oai-client-auth-session cookie（base64 解码）的 workspaces[0].id 取
    6. → 重定向 localhost:1455/auth/callback?code=ac_...，从 Location 抠 code

拿到 code 后换 token / 落盘的逻辑（exchange_codex_token / build_codex_storage /
save_codex_credential）沿用旧实现，未改动。
"""
import base64
import hashlib
import json
import logging
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, urlparse, parse_qs

from config.codex import (
    ENABLE_CODEX_AUTO,
    CODEX_CLIENT_ID,
    CODEX_AUTH_URL,
    CODEX_TOKEN_URL,
    CODEX_REDIRECT_URI,
    CODEX_SCOPE,
    CODEX_OUTPUT_DIRNAME,
    SMS_MAX_RETRIES,
)
from core.session import BrowserSession
from core.openai_auth import (
    _is_transient_network_error,
    request_sentinel_token,
    build_sentinel_header,
)
from core import sms_provider

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 跟重定向链时的最大跳数，防死循环
_MAX_REDIRECTS = 15

# 网络层临时性错误（代理抖动 / TLS 握手失败 / 重置）重试参数，对齐 openai_auth.follow_authorize
_NET_MAX_ATTEMPTS = 3
_NET_BACKOFF_BASE = 2.0


def _with_net_retry(label: str, fn):
    """
    对临时性网络错误（TLS/代理/超时/重置）做重试包装。
    非临时错误（业务 4xx 等）直接抛。最多 _NET_MAX_ATTEMPTS 次。
    """
    last_exc = None
    for attempt in range(1, _NET_MAX_ATTEMPTS + 1):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            if not _is_transient_network_error(exc):
                raise
            if attempt >= _NET_MAX_ATTEMPTS:
                break
            backoff = _NET_BACKOFF_BASE ** (attempt - 1)
            logger.warning(
                f"[Codex] {label} 临时性网络错误 ({type(exc).__name__}: {str(exc)[:120]})，"
                f"{backoff:.1f}s 后重试 (尝试 {attempt}/{_NET_MAX_ATTEMPTS})..."
            )
            time.sleep(backoff)
    raise last_exc if last_exc else RuntimeError(f"[Codex] {label} 重试耗尽但无异常记录")


def _codex_result(
    *,
    status: str,
    ok: bool = False,
    http_status: int | None = None,
    email: str | None = None,
    file_path: str | None = None,
    callback_url: str | None = None,
    message: str = "",
) -> dict:
    """构造与 flow_trigger._flow_result 同形态的结构化结果。"""
    return {
        "status": status,
        "ok": ok,
        "http_status": http_status,
        "email": email,
        "file_path": file_path,
        "callback_url": callback_url,
        "message": message,
    }


# ============================================================
# PKCE / state（对照 CLIProxyAPI pkce.go）
# ============================================================

def _generate_pkce() -> tuple[str, str]:
    """生成 PKCE 代码对：verifier=base64url(96字节)，challenge=base64url(sha256(verifier))。"""
    verifier_bytes = secrets.token_bytes(96)
    code_verifier = base64.urlsafe_b64encode(verifier_bytes).rstrip(b"=").decode("ascii")
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return code_verifier, code_challenge


def _generate_state() -> str:
    """生成 OAuth state 随机串，防 CSRF。"""
    return secrets.token_urlsafe(32)


def _build_authorize_url(state: str, code_challenge: str, prompt: str = "login") -> str:
    """按 CLIProxyAPI openai_auth.go 的参数集拼 Codex 授权 URL。"""
    params = {
        "client_id": CODEX_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": CODEX_REDIRECT_URI,
        "scope": CODEX_SCOPE,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "prompt": prompt,
        "id_token_add_organizations": "true",
        "codex_cli_simplified_flow": "true",
    }
    return f"{CODEX_AUTH_URL}?{urlencode(params)}"


# ============================================================
# 小工具：判定/解析
# ============================================================

def _is_redirect_uri(location: str) -> bool:
    """判断 Location 是否指向注册的 redirect_uri（localhost:1455/auth/callback）。"""
    try:
        parsed = urlparse(location)
    except Exception:
        return False
    return parsed.scheme in ("http", "https") and \
        parsed.hostname in ("localhost", "127.0.0.1") and \
        parsed.port == 1455 and \
        parsed.path == "/auth/callback"


def _extract_code(location: str, state: str) -> str:
    """从 redirect_uri 的 Location 里提取并校验 code。"""
    parsed = urlparse(location)
    qs = parse_qs(parsed.query)
    err = (qs.get("error") or [""])[0]
    if err:
        err_desc = (qs.get("error_description") or [""])[0]
        raise RuntimeError(f"[Codex] 授权服务器返回错误: error={err}, desc={err_desc}")
    code = (qs.get("code") or [""])[0]
    if not code:
        raise RuntimeError(f"[Codex] redirect_uri 缺少 code 参数: {location}")
    returned_state = (qs.get("state") or [""])[0]
    if returned_state and returned_state != state:
        raise RuntimeError(
            f"[Codex] state 不匹配（疑似 CSRF）: expected={state[:8]}..., got={returned_state[:8]}..."
        )
    return code


def _decode_jwt_segment(seg: str) -> dict:
    """base64url 解码一个 JWT/cookie 段为 JSON dict（失败返回 {}）。"""
    try:
        padding = "=" * (-len(seg) % 4)
        return json.loads(base64.urlsafe_b64decode(seg + padding))
    except Exception:
        return {}


def _post_json(session: BrowserSession, url: str, payload: dict, referer: str,
               sentinel_header: str | None = None):
    """统一发 /api/accounts/* 的 JSON POST。"""
    headers = session.get_auth_headers(referer=referer)
    if sentinel_header:
        headers["openai-sentinel-token"] = sentinel_header
    return session.post(url, headers=headers, data=json.dumps(payload), allow_redirects=False)


def _resp_json(resp) -> dict:
    try:
        return resp.json()
    except Exception:
        return {}


# ============================================================
# 步骤 0：用全新 session 跟随 Codex authorize URL，建立 auth.openai.com 会话
# ============================================================

def _bootstrap_authorize(session: BrowserSession, state: str, code_challenge: str) -> None:
    """
    GET Codex authorize URL 并跟随重定向，落到登录页，建立 auth.openai.com cookies
    （含 oai-client-auth-session：内含 Codex 目标 + 后续要用的 workspace 列表）。
    """
    auth_url = _build_authorize_url(state, code_challenge, prompt="login")
    headers = session.get_auth_navigate_headers(referer="https://chatgpt.com/")
    logger.info("[Codex] 跟随 Codex authorize URL 建立会话...")
    resp = _with_net_retry(
        "bootstrap authorize",
        lambda: session.get(auth_url, headers=headers, allow_redirects=True),
    )
    logger.debug(f"[Codex] authorize 落点: {getattr(resp, 'url', '')}, status={getattr(resp, 'status_code', '')}")


# ============================================================
# 步骤 1：提交邮箱（触发邮箱 OTP 发送）
# ============================================================

def _submit_email(session: BrowserSession, email: str) -> None:
    """POST authorize/continue 提交邮箱，触发 OpenAI 发送邮箱 OTP。带 sentinel。"""
    sentinel_resp = request_sentinel_token(session, "authorize_continue")
    sentinel_header, _ = build_sentinel_header(session, sentinel_resp, "authorize_continue")
    payload = {"username": {"kind": "email", "value": email}}
    resp = _post_json(
        session,
        "https://auth.openai.com/api/accounts/authorize/continue",
        payload,
        referer="https://auth.openai.com/log-in",
        sentinel_header=sentinel_header,
    )
    if resp.status_code not in (200, 204):
        raise RuntimeError(
            f"[Codex] 提交邮箱失败 status={resp.status_code}: {(resp.text or '')[:300]}"
        )
    logger.info(f"[Codex] 已提交邮箱 {email}，等待邮箱 OTP")


# ============================================================
# 步骤 2：提交邮箱 OTP
# ============================================================

def _submit_email_otp(session: BrowserSession, code: str) -> None:
    """POST email-otp/validate 提交邮箱验证码。带 sentinel(authorize_continue)。"""
    sentinel_resp = request_sentinel_token(session, "authorize_continue")
    sentinel_header, _ = build_sentinel_header(session, sentinel_resp, "authorize_continue")
    resp = _post_json(
        session,
        "https://auth.openai.com/api/accounts/email-otp/validate",
        {"code": code},
        referer="https://auth.openai.com/email-verification",
        sentinel_header=sentinel_header,
    )
    if resp.status_code != 200:
        raise RuntimeError(
            f"[Codex] 邮箱 OTP 验证失败 status={resp.status_code}: {(resp.text or '')[:300]}"
        )
    logger.info("[Codex] 邮箱 OTP 验证通过")


# ============================================================
# 步骤 3-4：手机号验证（接码，失败换号重试）
# ============================================================

def _do_phone_verification(session: BrowserSession) -> None:
    """
    用接码平台拿号 → add-phone/send 发短信 → 收码 → phone-otp/validate。
    一个号收不到码或被 OpenAI 拒就取消换号，最多 SMS_MAX_RETRIES 次。
    """
    http = sms_provider._http()
    try:
        last_err = None
        for attempt in range(1, SMS_MAX_RETRIES + 1):
            activation_id = None
            try:
                activation_id, phone = sms_provider.acquire_number(http)
                logger.info(f"[Codex] 手机验证尝试 {attempt}/{SMS_MAX_RETRIES}，号码=+{phone}")

                # 发短信
                send_resp = _post_json(
                    session,
                    "https://auth.openai.com/api/accounts/add-phone/send",
                    {"phone_number": f"+{phone}", "channel": "sms"},
                    referer="https://auth.openai.com/add-phone",
                )
                if send_resp.status_code not in (200, 204):
                    # 号码被拒（VoIP/黑名单等）→ 取消换号
                    logger.warning(
                        f"[Codex] add-phone/send 被拒 status={send_resp.status_code}: "
                        f"{(send_resp.text or '')[:200]}，换号重试"
                    )
                    sms_provider.cancel(activation_id, http)
                    continue

                # 通知平台短信已发出（status=1）
                sms_provider.set_status(activation_id, 1, http=http)

                # 等短信
                try:
                    sms_code = sms_provider.wait_for_sms_code(activation_id, http)
                except sms_provider.SmsCodeTimeout:
                    logger.warning(f"[Codex] 号码 +{phone} 未收到短信，取消换号")
                    sms_provider.cancel(activation_id, http)
                    continue

                # 验手机码
                val_resp = _post_json(
                    session,
                    "https://auth.openai.com/api/accounts/phone-otp/validate",
                    {"code": sms_code},
                    referer="https://auth.openai.com/phone-verification",
                )
                if val_resp.status_code != 200:
                    logger.warning(
                        f"[Codex] phone-otp/validate 失败 status={val_resp.status_code}: "
                        f"{(val_resp.text or '')[:200]}，换号重试"
                    )
                    sms_provider.cancel(activation_id, http)
                    continue

                # 成功
                sms_provider.complete(activation_id, http)
                logger.info("[Codex] 手机号验证通过")
                return

            except sms_provider.SmsNoBalanceError:
                # 余额不足，重试无意义，直接抛
                raise
            except sms_provider.SmsProviderError as exc:
                last_err = exc
                logger.warning(f"[Codex] 接码尝试 {attempt} 失败：{exc}")
                if activation_id:
                    sms_provider.cancel(activation_id, http)
                continue

        raise RuntimeError(
            f"[Codex] 手机号验证重试 {SMS_MAX_RETRIES} 次仍失败"
            + (f"，最后错误：{last_err}" if last_err else "")
        )
    finally:
        http.close()


# ============================================================
# 步骤 5：选 workspace → 拿 callback code
# ============================================================

def _get_workspace_id(session: BrowserSession) -> str:
    """
    从 oai-client-auth-session cookie 解出 workspaces[0].id。
    cookie 形如 base64payload.sig.sig，取第一段 base64 解码后的 JSON。
    """
    raw = None
    try:
        # curl_cffi cookies
        for c in session.session.cookies.jar:
            if c.name == "oai-client-auth-session":
                raw = c.value
                break
    except Exception:
        pass
    if not raw:
        # 退而求其次：从 cookies 字典拿
        try:
            raw = session.session.cookies.get("oai-client-auth-session")
        except Exception:
            raw = None
    if not raw:
        raise RuntimeError("[Codex] 找不到 oai-client-auth-session cookie，无法取 workspace_id")

    payload = _decode_jwt_segment(raw.split(".")[0])
    workspaces = payload.get("workspaces") or []
    if not workspaces:
        raise RuntimeError(f"[Codex] cookie 里无 workspaces 字段: keys={list(payload.keys())}")
    wid = workspaces[0].get("id")
    if not wid:
        raise RuntimeError(f"[Codex] workspaces[0] 无 id: {workspaces[0]}")
    logger.info(f"[Codex] workspace_id={wid}")
    return wid


def _select_workspace_and_get_callback(session: BrowserSession, state: str) -> str:
    """
    POST workspace/select，然后跟随后续重定向/响应里的 URL 直到命中 localhost:1455 callback。
    返回完整 callback URL（含 code）。
    """
    wid = _get_workspace_id(session)
    resp = _post_json(
        session,
        "https://auth.openai.com/api/accounts/workspace/select",
        {"workspace_id": wid},
        referer="https://auth.openai.com/sign-in-with-chatgpt/codex/consent",
    )

    # 1) 直接带 Location 头命中 callback
    loc = resp.headers.get("location") or resp.headers.get("Location")
    if loc and _is_redirect_uri(loc):
        return loc

    # 2) 响应 JSON 里给了下一步 URL（continue_url / redirect_url / url / next）
    data = _resp_json(resp)
    next_url = None
    for key in ("redirect_url", "continue_url", "url", "next", "location"):
        v = data.get(key)
        if isinstance(v, str) and v:
            next_url = v
            break

    # 3) 没给 URL 但有 Location（非 callback）→ 从 Location 起跟
    if not next_url and loc:
        next_url = loc

    if not next_url:
        raise RuntimeError(
            f"[Codex] workspace/select 后找不到下一跳 URL: status={resp.status_code}, "
            f"body={(resp.text or '')[:300]}"
        )

    # 跟随重定向链直到命中 callback
    return _follow_until_callback(session, next_url, state)


def _follow_until_callback(session: BrowserSession, url: str, state: str) -> str:
    """从给定 URL 起逐跳跟随，命中 localhost:1455 callback 时返回其 Location。"""
    if url.startswith("/"):
        url = "https://auth.openai.com" + url
    for hop in range(_MAX_REDIRECTS):
        if _is_redirect_uri(url):
            return url
        headers = session.get_auth_navigate_headers(referer="https://auth.openai.com/")
        resp = session.get(url, headers=headers, allow_redirects=False)
        loc = resp.headers.get("location") or resp.headers.get("Location")
        logger.debug(f"[Codex] callback 跟随 hop {hop}: status={getattr(resp,'status_code','')}, location={loc}")
        if loc is None:
            raise RuntimeError(
                f"[Codex] 跟随中断，未命中 callback: url={url}, "
                f"status={getattr(resp,'status_code','')}, body={(resp.text or '')[:200]}"
            )
        if _is_redirect_uri(loc):
            return loc
        url = loc if loc.startswith("http") else ("https://auth.openai.com" + loc)
    raise RuntimeError(f"[Codex] 跟随 callback 超过 {_MAX_REDIRECTS} 跳")


# ============================================================
# 换 token（对照 CLIProxyAPI ExchangeCodeForTokensWithRedirect）—— 未改动
# ============================================================

def exchange_codex_token(session: BrowserSession, code: str, code_verifier: str) -> dict:
    """用 authorization code 换 token。"""
    data = {
        "grant_type": "authorization_code",
        "client_id": CODEX_CLIENT_ID,
        "code": code,
        "redirect_uri": CODEX_REDIRECT_URI,
        "code_verifier": code_verifier,
    }
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
    }
    base = session._get_common_headers()
    base.update(headers)
    headers = base

    logger.info("[Codex] 用 authorization code 换 token...")
    resp = session.post(CODEX_TOKEN_URL, headers=headers, data=urlencode(data))
    http_status = resp.status_code
    if http_status != 200:
        raise RuntimeError(
            f"[Codex] 换 token 失败 status={http_status}: {(resp.text or '')[:300]}"
        )
    token_resp = resp.json()
    if not token_resp.get("access_token"):
        raise RuntimeError(f"[Codex] token 响应缺少 access_token: {token_resp}")
    logger.info(
        f"[Codex] 换 token 成功，expires_in={token_resp.get('expires_in')}, "
        f"access_token={token_resp['access_token'][:16]}..."
    )
    return token_resp


# ============================================================
# 解析 id_token / 落盘 —— 未改动
# ============================================================

def _parse_id_token(id_token: str) -> dict:
    """base64 解码 JWT payload（不验签），抽 email / account_id / plan_type。"""
    if not id_token:
        return {}
    try:
        parts = id_token.split(".")
        if len(parts) < 2:
            return {}
        claims = _decode_jwt_segment(parts[1])
    except Exception as exc:
        logger.warning(f"[Codex] id_token 解析失败: {exc}")
        return {}

    auth_claim = claims.get("https://api.openai.com/auth", {}) or {}
    profile_claim = claims.get("https://api.openai.com/profile", {}) or {}
    # OpenAI 新版 id_token 的 email 在顶层 claim；旧版/CLIProxyAPI 实现里在 profile_claim。
    # 顶层优先，否则回退 profile_claim，避免落盘的 codex-邮箱.json 里 email 字段为空。
    email_value = claims.get("email") or profile_claim.get("email", "")
    return {
        "email": email_value,
        "account_id": auth_claim.get("chatgpt_account_id", ""),
        "plan_type": auth_claim.get("chatgpt_plan_type", ""),
    }


def build_codex_storage(token_resp: dict, id_claims: dict) -> dict:
    """组装 CLIProxyAPI CodexTokenStorage JSON 结构。"""
    expires_in = token_resp.get("expires_in", 0) or 0
    expired_dt = datetime.now(timezone.utc) + _timedelta_seconds(expires_in)
    last_refresh_dt = datetime.now(timezone.utc)
    return {
        "id_token": token_resp.get("id_token", ""),
        "access_token": token_resp.get("access_token", ""),
        "refresh_token": token_resp.get("refresh_token", ""),
        "account_id": id_claims.get("account_id", ""),
        "last_refresh": last_refresh_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "email": id_claims.get("email", ""),
        "type": "codex",
        "expired": expired_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def _timedelta_seconds(seconds: int):
    from datetime import timedelta
    return timedelta(seconds=int(seconds))


def _credential_file_name(email: str, plan_type: str) -> str:
    """对照 CLIProxyAPI filename.go：无 plan→codex-{email}.json，否则带 plan 后缀。"""
    email = (email or "").strip()
    plan = (plan_type or "").strip().lower()
    if plan == "":
        return f"codex-{email}.json"
    return f"codex-{email}-{plan}.json"


def save_codex_credential(storage: dict, email: str, plan_type: str) -> Path:
    """落盘到 {PROJECT_ROOT}/{CODEX_OUTPUT_DIRNAME}/codex-{email}.json。"""
    out_dir = _PROJECT_ROOT / CODEX_OUTPUT_DIRNAME
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = _credential_file_name(email, plan_type)
    path = out_dir / fname
    path.write_text(
        json.dumps(storage, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


# ============================================================
# 入口
# ============================================================

def run_codex_oauth(email: str, otp_provider=None, proxy: str | None = None) -> dict:
    """
    注册成功后的 Codex OAuth 授权入口（全新 session + 接码方案）。

    不复用注册的 session：内部新建干净 BrowserSession，从头登录该邮箱，
    走 邮箱 OTP → 手机短信验证 → 选 workspace → 拿 code → 换 token → 落盘。

    Args:
        email: 已注册成功的账号邮箱
        otp_provider: 邮箱 OTP 获取回调 fn(email, after_ts)->code，默认用 wait_for_otp
        proxy: 代理（不传从 PROXY_POOL 抽）

    Returns:
        结构化结果 dict。任何异常都被吞掉转 status=failed，不向上抛，不影响注册主流程。
    """
    if not ENABLE_CODEX_AUTO:
        return _codex_result(status="skipped", message="ENABLE_CODEX_AUTO=False")
    if not email:
        return _codex_result(status="skipped", message="email 为空")

    if otp_provider is None:
        from core.email_provider import wait_for_otp as otp_provider

    session = BrowserSession(proxy=proxy)
    try:
        logger.info(f"[Codex] 开始授权（全新 session）：{email}")

        # 1. PKCE + state
        code_verifier, code_challenge = _generate_pkce()
        state = _generate_state()

        # 2. 建立会话
        _bootstrap_authorize(session, state, code_challenge)
        time.sleep(0.5)

        # 3. 提交邮箱（触发邮箱 OTP）
        otp_after_ts = time.time()
        _submit_email(session, email)
        time.sleep(0.5)

        # 4. 收邮箱 OTP + 提交
        logger.info(f"[Codex] 等待邮箱 OTP：{email}")
        email_otp = otp_provider(email, after_ts=otp_after_ts)
        logger.info(f"[Codex] 邮箱 OTP 收到：{email_otp}")
        _submit_email_otp(session, email_otp)
        time.sleep(0.5)

        # 5. 手机号验证（接码，自动重试换号）
        _do_phone_verification(session)
        time.sleep(0.5)

        # 6. 选 workspace → 拿 callback code
        callback_url = _select_workspace_and_get_callback(session, state)
        code = _extract_code(callback_url, state)
        logger.info(f"[Codex] 已拿到 authorization code：{code[:24]}...")

        # 7. 换 token
        token_resp = exchange_codex_token(session, code, code_verifier)

        # 8. 解析 id_token + 落盘
        id_claims = _parse_id_token(token_resp.get("id_token", ""))
        effective_email = id_claims.get("email") or email
        storage = build_codex_storage(token_resp, id_claims)
        path = save_codex_credential(storage, effective_email, id_claims.get("plan_type", ""))

        logger.info(
            f"[Codex] 成功：{effective_email}，plan={id_claims.get('plan_type') or 'unknown'}, "
            f"account_id={id_claims.get('account_id') or 'unknown'}, 已保存到 {path}"
        )
        return _codex_result(
            status="success",
            ok=True,
            email=effective_email,
            file_path=str(path),
            callback_url=callback_url,
            message=f"plan={id_claims.get('plan_type') or 'unknown'}",
        )
    except Exception as exc:
        logger.warning(f"[Codex] 失败：{email}，{type(exc).__name__}: {str(exc)[:200]}")
        logger.debug("[Codex] 失败详情:", exc_info=True)
        return _codex_result(
            status="failed",
            email=email,
            message=f"{type(exc).__name__}: {str(exc)[:200]}",
        )
