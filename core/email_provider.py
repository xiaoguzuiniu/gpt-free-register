# -*- coding: utf-8 -*-
"""
邮箱来源调度层。

当前只支持 Outlook 账号池。
"""
import logging

logger = logging.getLogger(__name__)


def acquire_email() -> str:
    """从 Outlook 账号池领取一个用于注册的邮箱地址。"""
    from core.outlook_client import pick_account

    account = pick_account()
    return account.email


def wait_for_otp(email: str, after_ts: float) -> str:
    """
    等待并返回该邮箱最新的 ChatGPT OTP（6 位数字字符串）。

    Args:
        email: 目标邮箱
        after_ts: UTC 时间戳，只看比这更新的邮件，避免取到旧 OTP
    """
    from core.outlook_client import fetch_latest_otp

    return fetch_latest_otp(email, after_ts=after_ts)
