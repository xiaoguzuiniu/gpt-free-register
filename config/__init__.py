# -*- coding: utf-8 -*-
"""
config 包的统一入口。

为保留 `from config import USER_AGENT` 这种历史用法，本文件把所有子模块的常量
重新导出到包顶层。新代码推荐按子模块直接导入：
    from config.email import EMAIL_SOURCE
    from config.proxy import pick_proxy

子模块清单：
    config.browser           浏览器指纹 / curl_cffi impersonate / HTTP 超时
    config.openai_protocol   OpenAI OAuth 固定参数 / Sentinel 版本
    config.proxy             代理池 + 随机抽取
    config.register          注册默认信息（邮箱、密码、名称、生日）
    config.email             Outlook 邮箱账号池 + OTP 轮询
    config.twofa             2FA 开关
"""

# ---------- 浏览器 / HTTP ----------
from config.browser import (
    USER_AGENT,
    SEC_CH_UA,
    SEC_CH_UA_PLATFORM,
    SEC_CH_UA_MOBILE,
    IMPERSONATE,
    REQUEST_TIMEOUT,
)

# ---------- OpenAI 协议 ----------
from config.openai_protocol import (
    OPENAI_CLIENT_ID,
    OPENAI_SCOPE,
    OPENAI_AUDIENCE,
    OPENAI_REDIRECT_URI,
    SENTINEL_SV,
)

# ---------- 代理池 ----------
from config.proxy import (
    PROXY_POOL,
    pick_proxy,
    PROXY,
)

# ---------- 注册默认信息 ----------
from config.register import (
    REGISTER_EMAIL,
    REGISTER_PASSWORD,
    REGISTER_NAME,
    REGISTER_BIRTHDAY,
)

# ---------- 邮箱服务 ----------
from config.email import (
    USE_EMAIL_SERVICE,
    EMAIL_SOURCE,
    OUTLOOK_ACCOUNTS_FILE,
    OUTLOOK_API_BASE,
    OTP_POLL_INTERVAL,
    OTP_MAX_WAIT,
    OTP_SETTLE_SECONDS,
)

# ---------- 2FA ----------
from config.twofa import ENABLE_2FA


__all__ = [
    # browser
    "USER_AGENT", "SEC_CH_UA", "SEC_CH_UA_PLATFORM", "SEC_CH_UA_MOBILE",
    "IMPERSONATE", "REQUEST_TIMEOUT",
    # openai_protocol
    "OPENAI_CLIENT_ID", "OPENAI_SCOPE", "OPENAI_AUDIENCE", "OPENAI_REDIRECT_URI",
    "SENTINEL_SV",
    # proxy
    "PROXY_POOL", "pick_proxy", "PROXY",
    # register
    "REGISTER_EMAIL", "REGISTER_PASSWORD", "REGISTER_NAME", "REGISTER_BIRTHDAY",
    # email
    "USE_EMAIL_SERVICE", "EMAIL_SOURCE",
    "OUTLOOK_ACCOUNTS_FILE", "OUTLOOK_API_BASE",
    "OTP_POLL_INTERVAL", "OTP_MAX_WAIT", "OTP_SETTLE_SECONDS",
    # twofa
    "ENABLE_2FA",
]
