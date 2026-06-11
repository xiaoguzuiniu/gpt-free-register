# -*- coding: utf-8 -*-
"""
curl_cffi Session 封装
统一管理 Cookie、请求头和 TLS 指纹
"""
import uuid
from curl_cffi.requests import Session

from config import (
    USER_AGENT, SEC_CH_UA, SEC_CH_UA_PLATFORM, SEC_CH_UA_MOBILE,
    IMPERSONATE, REQUEST_TIMEOUT, pick_proxy,
)


class BrowserSession:
    """
    模拟 Chrome 浏览器的 HTTP 会话管理器。
    使用 curl_cffi 的 impersonate 功能绕过 Cloudflare TLS 指纹检测。
    """

    def __init__(self, proxy: str = None):
        """
        初始化会话。

        Args:
            proxy: 代理地址，如 "socks5h://user:pass@host:port"。
                   不传则从 config.PROXY_POOL 随机抽一个。
                   显式传 "" 表示禁用代理。
        """
        # proxy=None  → 从池里随机抽（默认行为）
        # proxy=""    → 禁用代理（直连）
        # proxy="..." → 使用指定代理
        if proxy is None:
            self.proxy = pick_proxy()
        else:
            self.proxy = proxy

        # 生成设备ID（oai-did），整个注册流程复用
        self.device_id = str(uuid.uuid4())

        # 生成 auth_session_logging_id
        self.auth_session_logging_id = str(uuid.uuid4())

        # 创建 curl_cffi 会话
        self.session = Session(impersonate=IMPERSONATE)

        # 设置代理
        if self.proxy:
            self.session.proxies = {
                "http": self.proxy,
                "https": self.proxy,
            }

        # 设置超时
        self.session.timeout = REQUEST_TIMEOUT

    def _get_common_headers(self) -> dict:
        """获取通用请求头"""
        return {
            "User-Agent": USER_AGENT,
            "sec-ch-ua": SEC_CH_UA,
            "sec-ch-ua-platform": SEC_CH_UA_PLATFORM,
            "sec-ch-ua-mobile": SEC_CH_UA_MOBILE,
            "accept-language": "ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7",
        }

    def get_chatgpt_headers(self, referer: str = "https://chatgpt.com/login") -> dict:
        """
        获取 chatgpt.com 域名的请求头。
        用于步骤1-3。
        """
        headers = self._get_common_headers()
        headers.update({
            "accept": "*/*",
            "content-type": "application/json",
            "sec-fetch-site": "same-origin",
            "sec-fetch-mode": "cors",
            "sec-fetch-dest": "empty",
            "referer": referer,
            "priority": "u=1, i",
        })
        return headers

    def get_auth_headers(self, referer: str = "https://auth.openai.com/create-account/password") -> dict:
        """
        获取 auth.openai.com 域名的请求头。
        用于步骤7、10、12。
        """
        headers = self._get_common_headers()
        headers.update({
            "accept": "application/json",
            "content-type": "application/json",
            "sec-fetch-site": "same-origin",
            "sec-fetch-mode": "cors",
            "sec-fetch-dest": "empty",
            "referer": referer,
            "priority": "u=1, i",
            "origin": "https://auth.openai.com",
        })
        return headers

    def get_auth_navigate_headers(self, referer: str = "https://chatgpt.com/") -> dict:
        """
        获取 auth.openai.com 导航请求头（用于GET页面请求）。
        用于步骤4、5、8。
        """
        headers = self._get_common_headers()
        headers.update({
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "sec-fetch-site": "cross-site",
            "sec-fetch-mode": "navigate",
            "sec-fetch-dest": "document",
            "referer": referer,
            "priority": "u=0, i",
            "upgrade-insecure-requests": "1",
        })
        return headers

    def get_sentinel_headers(self) -> dict:
        """
        获取 sentinel.openai.com 的请求头。
        用于步骤6、9、11。
        """
        from config import SENTINEL_SV
        headers = self._get_common_headers()
        headers.update({
            "accept": "*/*",
            "content-type": "text/plain;charset=UTF-8",
            "origin": "https://sentinel.openai.com",
            "referer": f"https://sentinel.openai.com/backend-api/sentinel/frame.html?sv={SENTINEL_SV}",
            "sec-fetch-site": "same-origin",
            "sec-fetch-mode": "cors",
            "sec-fetch-dest": "empty",
            "priority": "u=1, i",
        })
        return headers

    def get(self, url: str, headers: dict = None, **kwargs):
        """发送 GET 请求"""
        return self.session.get(url, headers=headers, **kwargs)

    def post(self, url: str, headers: dict = None, **kwargs):
        """发送 POST 请求"""
        return self.session.post(url, headers=headers, **kwargs)
