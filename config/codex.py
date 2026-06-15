# -*- coding: utf-8 -*-
"""
注册成功后自动跑 Codex OAuth 授权的配置项。
设置 ENABLE_CODEX = False 可完全跳过此步骤。

参数来源：CLIProxyAPI 源码 internal/auth/codex/openai_auth.go + pkce.go，
对照 https://github.com/router-for-me/CLIProxyAPI 逐行确认。
"""

# 是否启用 Codex OAuth 授权（False = 跳过，不影响注册结果）
ENABLE_CODEX: bool = True

# Codex OAuth 客户端 ID（固定值，来自 CLIProxyAPI openai_auth.go:27 ClientID）
CODEX_CLIENT_ID: str = "app_EMoamEEZ73f0CkXaXp7hrann"

# 授权端点（openai_auth.go:25 AuthURL）
CODEX_AUTH_URL: str = "https://auth.openai.com/oauth/authorize"

# 换 token 端点（openai_auth.go:26 TokenURL）
CODEX_TOKEN_URL: str = "https://auth.openai.com/oauth/token"

# 回调地址（openai_auth.go:28 RedirectURI）
# 注意：本地并不真的起这个 server，只用来拦截重定向并从 Location 提取 code。
CODEX_REDIRECT_URI: str = "http://localhost:1455/auth/callback"

# OAuth scopes（openai_auth.go:75 GenerateAuthURL 里的 scope）
CODEX_SCOPE: str = "openid email profile offline_access"

# 输出目录名（仅名字，运行时拼到项目根；与 OUTLOOK_ACCOUNTS_FILE 同级风格）
CODEX_OUTPUT_DIRNAME: str = "codex_accounts"

# 请求超时（秒）
CODEX_REQUEST_TIMEOUT: int = 30


# ============================================================
# Codex 授权方式（2026-06-15 改造）
#
# 旧方案"复用注册的已登录 session"会撞 /choose-an-account 卡死；
# 新方案用全新干净 session 从头登录，走 OpenAI 标准风控路径
# （邮箱 OTP → 手机短信验证 → 选 workspace → 拿 code），
# 手机验证靠接码平台 GrizzlySMS 自动收码。
# ============================================================

# 注册成功后是否自动跑 Codex 授权（True=自动，False=跳过）
ENABLE_CODEX_AUTO: bool = True


# ============================================================
# 接码平台 GrizzlySMS（手机短信验证用）
# 接口说明见 https://api.grizzlysms.com
# ============================================================

# 接码 API 基址（GET handler）
SMS_API_BASE: str = "https://api.grizzlysms.com/stubs/handler_api.php"

# 接码 API 密钥（在 GrizzlySMS 后台 → 设置 获取）
# 留空时 Codex 授权的手机验证步会失败；如不需要 Codex 自动授权，把 ENABLE_CODEX_AUTO=False。
SMS_API_KEY: str = "472ab4df46a4c97d61089fac760fb0d2"

# 服务代码：OpenAI = "dr"
SMS_SERVICE: str = "dr"

# 国家代码：美国 = "187"（OpenAI 接受度高）
SMS_COUNTRY: str = "151"

# 单个号愿意支付的最高价格（留空=不限）。透传给 getNumber 的 maxPrice。
SMS_MAX_PRICE: str = ""

# 一个号收不到短信/被拒时，换号重试的最大次数
SMS_MAX_RETRIES: int = 3

# 单个号等待短信的最长秒数（超时则取消该号换下一个）
SMS_CODE_WAIT: int = 120

# 轮询接码平台查短信的间隔（秒）
SMS_POLL_INTERVAL: int = 5

# 接码平台 HTTP 请求超时（秒）
SMS_REQUEST_TIMEOUT: int = 30
