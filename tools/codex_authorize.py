# -*- coding: utf-8 -*-
"""
Codex OAuth 授权链接生成器（独立模块，可单独迁移使用）。

本模块只负责一件事：按 OpenAI Codex 客户端的 PKCE 流程，拼出标准 OAuth 授权 URL。
参数严格对照 CLIProxyAPI 源码 internal/auth/codex/openai_auth.go:71-82 (GenerateAuthURL)
以及 internal/auth/codex/pkce.go (GeneratePKCECodes)。

零依赖（仅标准库）：
    - 不依赖本项目的 BrowserSession / config / 数据库
    - 不发任何网络请求
    - 不读取本地任何文件

用法（迁移到新项目后）：
    from codex_authorize import build_codex_authorize_url

    url, verifier, challenge, state = build_codex_authorize_url(prompt="login")
    print(url)              # 浏览器打开这个 URL，让用户登录后会被跳到 localhost:1455/auth/callback?code=...&state=...
    # 后续：浏览器/代理从 callback URL 提取 code，结合 verifier 去换 access_token

如果新项目里也要做"换 token"或"落 CPA JSON"，可再追加相关函数，本文件暂只放授权 URL 生成。
"""
from __future__ import annotations

import base64
import hashlib
import secrets
from urllib.parse import urlencode


# ====== Codex 客户端固定参数（来自 CLIProxyAPI openai_auth.go）======

# 客户端 ID（Codex CLI 的公开 client_id，固定值）
CODEX_CLIENT_ID: str = "app_EMoamEEZ73f0CkXaXp7hrann"

# 授权端点
CODEX_AUTH_URL: str = "https://auth.openai.com/oauth/authorize"

# 换 token 端点
CODEX_TOKEN_URL: str = "https://auth.openai.com/oauth/token"

# 回调地址（不真起 1455 端口，仅作为 OAuth 注册的 redirect_uri；
#              真实流程里浏览器跳到这，自动化会从 Location 拦截提取 code）
CODEX_REDIRECT_URI: str = "http://localhost:1455/auth/callback"

# OAuth scopes
CODEX_SCOPE: str = "openid email profile offline_access"


# ====== PKCE 生成（对照 CLIProxyAPI pkce.go）======

def generate_pkce() -> tuple[str, str]:
    """
    生成 PKCE 代码对。

    对照 pkce.go:
        code_verifier  = base64url(96 随机字节) 无填充   (128 字符)
        code_challenge = base64url(sha256(verifier)) 无填充  (S256)

    Returns:
        (code_verifier, code_challenge)
    """
    verifier_bytes = secrets.token_bytes(96)
    code_verifier = base64.urlsafe_b64encode(verifier_bytes).rstrip(b"=").decode("ascii")

    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return code_verifier, code_challenge


def generate_state() -> str:
    """生成 OAuth state 随机串，防 CSRF。"""
    return secrets.token_urlsafe(32)


# ====== 授权 URL 构造（对照 openai_auth.go:66 GenerateAuthURL）======

def build_codex_authorize_url(
    state: str,
    code_challenge: str,
    prompt: str = "login",
) -> str:
    """
    按 CLIProxyAPI openai_auth.go:71-82 的参数集拼 Codex 授权 URL。

    参数说明:
        state:           防 CSRF 随机串（用 generate_state() 生成）
        code_challenge:  PKCE challenge（用 generate_pkce()[1] 拿到）
        prompt:          "login" 强制展示登录页（首次/新会话推荐）
                         "none"  静默放行（已有登录态时用，OIDC 标准）

    其余字段（codex_cli_simplified_flow / id_token_add_organizations）逐字对照源码。
    """
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


# ====== 一站式便利函数 ======

def make_codex_authorize(prompt: str = "login") -> dict:
    """
    一次性返回授权 URL + PKCE + state，便于调用方一行拿到全套参数。

    Returns:
        {
            "url":             完整授权 URL（直接给浏览器打开）,
            "state":           OAuth state,
            "code_verifier":   PKCE verifier（换 token 时要带）,
            "code_challenge":  PKCE challenge,
            "prompt":          透传的 prompt,
            "redirect_uri":    回调地址,
            "client_id":       客户端 ID,
        }
    """
    code_verifier, code_challenge = generate_pkce()
    state = generate_state()
    url = build_codex_authorize_url(state, code_challenge, prompt=prompt)
    return {
        "url": url,
        "state": state,
        "code_verifier": code_verifier,
        "code_challenge": code_challenge,
        "prompt": prompt,
        "redirect_uri": CODEX_REDIRECT_URI,
        "client_id": CODEX_CLIENT_ID,
    }


# ====== 命令行调试入口 ======

if __name__ == "__main__":
    import json as _json
    import sys

    prompt = sys.argv[1] if len(sys.argv) > 1 else "login"
    result = make_codex_authorize(prompt=prompt)
    print(_json.dumps(result, ensure_ascii=False, indent=2))