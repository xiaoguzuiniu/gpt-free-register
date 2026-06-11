# -*- coding: utf-8 -*-
"""
Outlook 邮箱账号池配置。

注册邮箱与 OTP 均只走 Outlook 账号池：
    1. 把邮箱素材写入项目根目录 `用于注册的邮箱.txt`
    2. 每行格式：email====password====clientId====refreshToken
    3. 运行注册时会自动导入新增邮箱
"""

# True: REGISTER_EMAIL 留空时从 Outlook 账号池自动获取邮箱，OTP 自动收取
# False: 走人工输入邮箱 + 人工填 OTP 的流程
USE_EMAIL_SERVICE = True

# 固定为 outlook；保留常量是为了兼容既有调用和落库字段。
EMAIL_SOURCE = "outlook"


# ============================================================
# Outlook 模式（外购账号池 + 取信服务）
# ============================================================

OUTLOOK_ACCOUNTS_FILE = "用于注册的邮箱.txt"

# 取邮件 API 的根 URL（双协议 graph + imap，自动回退）
OUTLOOK_API_BASE = "https://mail.chatai.codes"


# ============================================================
# OTP 轮询参数
# ============================================================

OTP_POLL_INTERVAL = 3
OTP_MAX_WAIT = 90

# Outlook 双协议取件：抓到一封 OTP 后再多等多少秒看是否有更晚到达的邮件。
OTP_SETTLE_SECONDS = 5
