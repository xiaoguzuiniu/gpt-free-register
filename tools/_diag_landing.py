# -*- coding: utf-8 -*-
"""诊断：单邮箱注册流程落点。"""
import sys, time, random, string
sys.path.insert(0, r"D:\devApp\GPT协议注册-0419")

from core.session import BrowserSession
from core.chatgpt_auth import get_providers, get_csrf_token, signin_openai

email = "JeanineWetzler930@outlook.com"
log = []
def out(msg):
    log.append(msg)
    with open(r"D:\devApp\GPT协议注册-0419\tools\_diag_landing.out", "w", encoding="utf-8") as f:
        f.write("\n".join(log))

out(f"email={email}")
try:
    session = BrowserSession()
    out(f"proxy={session.proxy}")
    get_providers(session); time.sleep(0.5)
    csrf = get_csrf_token(session); time.sleep(0.5)
    auth_url = signin_openai(session, csrf, email); time.sleep(0.5)
    out(f"authorize_url head={auth_url[:100]}")
    resp = session.get(auth_url, headers=session.get_auth_navigate_headers(referer="https://chatgpt.com/"), allow_redirects=True)
    out(f"最终落点: {resp.url}")
    out(f"status: {resp.status_code}")
    # 看页面特征
    body = resp.text or ""
    markers = ["email-verification", "create-account/password", "about-you", "login", "enter password", "验证码", "code"]
    found = [m for m in markers if m.lower() in body.lower()]
    out(f"页面含关键词: {found}")
    out(f"body head 300: {body[:300]}")
except Exception as e:
    import traceback
    out(f"异常: {type(e).__name__}: {e}")
    out(traceback.format_exc())
finally:
    try:
        from core.outlook_client import release_account
        release_account(email, status="available", note="诊断落点完成")
        out("已释放邮箱")
    except Exception as e:
        out(f"释放邮箱失败: {e}")
