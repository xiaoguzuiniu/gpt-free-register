# -*- coding: utf-8 -*-
"""
浏览器指纹与 HTTP 客户端配置

要点：
    - USER_AGENT 与 IMPERSONATE 必须严格对齐 Chrome 主版本号
      （curl_cffi 用 IMPERSONATE 决定 TLS/JA3/HTTP2 指纹，UA 决定声明版本）
    - 版本不一致 → sentinel 极易识破
"""

# ---------- UA / Client Hints ----------
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/142.0.0.0 Safari/537.36"
)
SEC_CH_UA = '"Chromium";v="142", "Google Chrome";v="142", "Not_A Brand";v="99"'
SEC_CH_UA_PLATFORM = '"Windows"'
SEC_CH_UA_MOBILE = "?0"

# ---------- curl_cffi 模拟浏览器 ----------
# 与 USER_AGENT 中声明的 Chrome 版本必须对齐
IMPERSONATE = "chrome142"

# ---------- HTTP 超时 ----------
REQUEST_TIMEOUT = 30  # 秒
