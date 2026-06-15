# -*- coding: utf-8 -*-
"""
一次性诊断脚本：注册一个新号到阶段 6 后，
详细观察 Codex authorize 重定向链，搞清楚 Hydra login_challenge 需要什么。

诊断重点：
1. 注册完成后 auth.openai.com 域名下有哪些 cookie
2. login_challenge URL 直接 GET 会发生什么（已登录放行 / 要求登录）
3. 如果要求登录，登录页返回什么（OTP / 密码 / 其它）
"""
import random
import string
import sys
import time
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logging.getLogger("core").setLevel(logging.WARNING)
logger = logging.getLogger("diag")


def main():
    from core.session import BrowserSession
    from core.chatgpt_auth import get_providers, get_csrf_token, signin_openai
    from core.openai_auth import (
        follow_authorize, request_sentinel_token, build_sentinel_header,
        validate_email_otp, create_account,
    )
    from core.account_export import follow_oauth_callback, fetch_session
    from core.email_provider import acquire_email, wait_for_otp
    from core.codex_oauth import _generate_pkce, _generate_state, _build_authorize_url, _is_redirect_uri

    # === 注册一个新号到阶段 6 ===
    email = acquire_email()
    name = (random.choice(string.ascii_uppercase) + "".join(random.choices(string.ascii_lowercase, k=5)) + " " +
            random.choice(string.ascii_uppercase) + "".join(random.choices(string.ascii_lowercase, k=5)))
    logger.info(f"邮箱={email}, name={name}")

    session = BrowserSession()
    get_providers(session); time.sleep(0.5)
    csrf = get_csrf_token(session); time.sleep(0.5)
    auth_url = signin_openai(session, csrf, email); time.sleep(0.5)
    otp_after = time.time()
    follow_authorize(session, auth_url); time.sleep(2)
    sr = request_sentinel_token(session, "authorize_continue")
    sh, _ = build_sentinel_header(session, sr, "authorize_continue"); time.sleep(0.3)
    otp = wait_for_otp(email, after_ts=otp_after)
    validate_email_otp(session, otp, sh); time.sleep(0.5)
    sr2 = request_sentinel_token(session, "oauth_create_account")
    sh2, soh2 = build_sentinel_header(session, sr2, "oauth_create_account"); time.sleep(0.3)
    cr = create_account(session, name, "2000-01-01", sh2, soh2); time.sleep(1)
    follow_oauth_callback(session, cr["continue_url"]); time.sleep(1)
    si = fetch_session(session)
    logger.info(f"✅ 注册+登录态完成: {si.get('user',{}).get('email')}")

    # === 诊断 1: auth.openai.com 域的 cookie ===
    print("\n" + "=" * 70)
    print("诊断 1: auth.openai.com 域 cookie")
    print("=" * 70)
    cookies = session.session.cookies
    jar = cookies.jar
    auth_cookies = {}
    for c in jar:
        domain = c.domain or ""
        if "auth.openai.com" in domain or domain.endswith("openai.com"):
            val = c.value or ""
            auth_cookies[(domain, c.name)] = val[:30] + "..." if len(val) > 30 else val
    if auth_cookies:
        for (domain, name), val in auth_cookies.items():
            print(f"  [{domain}] {name:40s} = {val}")
    else:
        print("  (auth.openai.com / openai.com 域无 cookie！)")
        # 退而求其次，打印所有 cookie 的域名分布
        all_domains = sorted({c.domain or "(no domain)" for c in jar})
        print(f"  所有 cookie 域名: {all_domains}")
        for c in jar:
            v = (c.value or "")
            print(f"    [{c.domain}] {c.name} = {v[:30]}")

    # === 诊断 2: Codex authorize 重定向链逐跳详细打印 ===
    print("\n" + "=" * 70)
    print("诊断 2: Codex authorize 重定向链（逐跳打印，不拦截 login_challenge）")
    print("=" * 70)
    cv, cc = _generate_pkce()
    state = _generate_state()
    auth_url = _build_authorize_url(state, cc)
    print(f"起始 URL:\n  {auth_url[:120]}...")

    headers = session.get_auth_navigate_headers(referer="https://chatgpt.com/")
    resp = session.get(auth_url, headers=headers, allow_redirects=False)
    hop = 0
    login_challenge_url = None
    while hop < 15:
        status = resp.status_code
        loc = resp.headers.get("location") or resp.headers.get("Location")
        print(f"\n[hop {hop}] status={status}")
        print(f"  location={loc[:200] if loc else '(无)'}")
        # 打印关键 cookie 变化
        set_cookies = [v for k, v in resp.headers.items() if k.lower() == "set-cookie"]
        if set_cookies:
            for sc in set_cookies:
                print(f"  set-cookie: {sc[:150]}")

        if loc is None:
            print(f"  body_head={(resp.text or '')[:300]}")
            break
        if _is_redirect_uri(loc):
            print(f"  ✅ 命中 redirect_uri，含 code！")
            break
        # 记录 login_challenge URL，但不拦截，继续跟
        if "/api/accounts/login" in loc and "login_challenge" in loc:
            login_challenge_url = loc
            print(f"  ⚠️ 这是 Hydra login_challenge URL，继续跟看会怎样")

        nh = session.get_auth_navigate_headers(referer="https://auth.openai.com/")
        resp = session.get(loc, headers=nh, allow_redirects=False)
        hop += 1

    # === 诊断 3: 如果到了登录页，看页面内容 ===
    print("\n" + "=" * 70)
    print("诊断 3: 最终落点页面分析")
    print("=" * 70)
    final_url = str(resp.url)
    print(f"最终 URL: {final_url}")
    body = resp.text or ""
    print(f"status={resp.status_code}, body 长度={len(body)}")
    # 找登录页的特征
    markers = ["email", "password", "验证码", "code", "otp", "login_challenge",
               "create-account", "about-you", "screen_hint", "login_or_signup"]
    found = [m for m in markers if m.lower() in body.lower()]
    print(f"页面含关键词: {found}")
    # 打印页面里出现的 form action / 关键 URL
    import re
    actions = re.findall(r'action="([^"]+)"', body)
    print(f"form actions: {actions[:5]}")
    # 打印 body 前 800 字
    print(f"\n--- body 前 800 字 ---\n{body[:800]}")

    # === 诊断 4: 深入分析 choose-an-account 的 form 结构 ===
    print("\n" + "=" * 70)
    print("诊断 4: choose-an-account form 结构分析")
    print("=" * 70)
    import re
    # 找所有 input 字段
    inputs = re.findall(r'<input[^>]+>', body)
    print(f"input 字段 ({len(inputs)} 个):")
    for inp in inputs:
        name = re.search(r'name="([^"]+)"', inp)
        val = re.search(r'value="([^"]*)"', inp)
        typ = re.search(r'type="([^"]+)"', inp)
        print(f"  type={typ.group(1) if typ else '?':10s} name={name.group(1) if name else '?':30s} value={(val.group(1)[:40] if val else '?')}")
    # 找 button
    buttons = re.findall(r'<button[^>]*>([^<]*)</button>', body)
    print(f"button 文本: {buttons[:10]}")
    # 找所有 form
    forms = re.findall(r'<form[^>]+>', body)
    print(f"form 标签: {forms}")
    # 找 data-* 属性里可能藏的 account id / challenge
    data_attrs = re.findall(r'data-[a-z-]+="[^"]{1,60}"', body)
    print(f"data-* 属性 (前20): {data_attrs[:20]}")
    # 找 __NEXT_DATA__ 或类似的内联 JSON
    next_data = re.search(r'<script[^>]*id="__NEXT_DATA__"[^>]*>([^<]+)</script>', body)
    if next_data:
        print(f"\n__NEXT_DATA__ (前 1500 字):\n{next_data.group(1)[:1500]}")
    # 找所有带 account/email/user 的 JSON 片段
    json_snippets = re.findall(r'\{[^{}]*"(?:account|email|user|challenge|session)[^{}]*\}', body[:20000])
    print(f"\n含 account/email/user 的 JSON 片段 (前5个):")
    for snip in json_snippets[:5]:
        print(f"  {snip[:200]}")

    # dump 完整 body 到文件供离线分析
    dump_path = _PROJECT_ROOT / "tools" / "_diag_choose_an_account.html"
    dump_path.write_text(body, encoding="utf-8")
    print(f"\n完整 body 已 dump 到: {dump_path}")


if __name__ == "__main__":
    main()
