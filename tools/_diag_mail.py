# -*- coding: utf-8 -*-
"""快速测取信服务是否可用：用 WehnesStmarie76（之前注册时信箱里有 OpenAI 邮件）。"""
import sys
sys.path.insert(0, r"D:\devApp\GPT协议注册-0419")

log = []
def out(msg):
    log.append(str(msg))
    with open(r"D:\devApp\GPT协议注册-0419\tools\_diag_mail.out", "w", encoding="utf-8") as f:
        f.write("\n".join(log))

try:
    from core.outlook_client import get_account_context, _fetch_via
    acct = get_account_context("WehnesStmarie76@outlook.com")
    out(f"账号获取 OK, email={acct.email}")

    out("尝试 graph 拉信箱 (top 3)...")
    r = _fetch_via("graph", acct, folder="Inbox", select_field="subject,receivedDateTime", top_n=3)
    out(f"graph 完成, 类型={type(r).__name__}")
    if isinstance(r, list):
        out(f"邮件数={len(r)}")
        for m in r[:3]:
            out(f"  - {m.get('subject','?')} | {m.get('receivedDateTime','?')}")
    else:
        out(f"返回: {str(r)[:300]}")
except Exception as e:
    import traceback
    out(f"异常: {type(e).__name__}: {e}")
    out(traceback.format_exc())
