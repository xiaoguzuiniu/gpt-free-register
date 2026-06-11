# -*- coding: utf-8 -*-
"""
Sentinel Token 生成模块
逆向自 sentinel.openai.com 的 sdk.js

核心逻辑：
1. 生成 `p` 字段（浏览器指纹数据，base64编码的 JSON 数组）
2. 发送 POST 请求到 sentinel.openai.com/backend-api/sentinel/req
3. 解析响应中的 token、turnstile、proofofwork
4. 计算 Proof of Work（FNV-1a 哈希）
5. 组装最终的 openai-sentinel-token 请求头值
"""
import json
import time
import math
import random
import base64
import hashlib
from datetime import datetime

from config import USER_AGENT, SENTINEL_SV


def generate_fingerprint_data(device_id: str, attempt: int = 1, elapsed_ms: float = 0) -> str:
    """
    生成浏览器指纹数据（p字段）。
    对应 SDK 中 getConfig() + N() 函数。

    SDK 中 getConfig() 返回的数组结构：
    [
        screen.width + screen.height,           # [0] 屏幕宽高之和
        "" + new Date,                           # [1] 当前时间字符串
        performance.memory.jsHeapSizeLimit,      # [2] JS堆大小限制
        Math.random() / attempt,                 # [3] 随机数（PoW时替换为尝试次数）
        navigator.userAgent,                     # [4] UA
        随机script src,                          # [5] 随机一个script标签的src
        data-build 属性值,                       # [6] document.documentElement 的 data-build 属性
        navigator.language,                      # [7] 语言
        navigator.languages.join(","),            # [8] 语言列表
        Math.random(),                           # [9] 随机数（PoW时替换为耗时）
        随机navigator属性,                       # [10] 随机一个navigator原型方法
        随机document key,                        # [11] 随机一个document的key
        随机window key,                          # [12] 随机一个window的key
        performance.now(),                       # [13] 高精度时间
        sid (UUID),                              # [14] 会话ID
        URL search params,                       # [15] URL查询参数
        navigator.hardwareConcurrency,           # [16] CPU核心数
        performance.timeOrigin,                  # [17] 性能时间原点
        Number("ai" in window),                  # [18] window.ai 是否存在
        Number("InstallTrigger" in window),      # [19] Firefox特有 → 0
        Number("cache" in window),               # [20] window.cache 是否存在
        Number("data" in window),                # [21] window.data 是否存在
        Number("solana" in window),              # [22] Solana钱包 → 0
        Number("dump" in window),                # [23] Firefox特有 → 0
        Number("requestIdleCallback" in window), # [24] 是否支持requestIdleCallback
    ]

    Args:
        device_id: 设备ID
        attempt: PoW尝试次数（用于替换 [3]）
        elapsed_ms: PoW耗时毫秒数（用于替换 [9]）
    """
    # 模拟Chrome浏览器环境
    now = datetime.now()
    # 模拟 Date.toString() 的格式，例如:
    # "Sun Apr 19 2026 19:46:20 GMT+0900 (日本標準時)"
    # 注：时区与代理出口 IP（JP）保持一致，避免指纹与 IP 错配。
    date_str = now.strftime("%a %b %d %Y %H:%M:%S GMT+0900 (日本標準時)")

    # 模拟 performance.timeOrigin（页面加载时的时间戳，精确到毫秒）
    time_origin = time.time() * 1000 - random.uniform(1000, 5000)

    # 模拟 performance.now()（页面加载后经过的毫秒数）
    perf_now = random.uniform(1000, 50000)

    # 生成 sid（SDK内部的会话ID）
    sid = str(device_id)

    # 模拟一些常见的 navigator 属性及其值
    navigator_props = [
        "clearOriginJoinedAdInterestGroups−function clearOriginJoinedAdInterestGroups() { [native code] }",
        "canLoadAdAuctionFencedFrame−function canLoadAdAuctionFencedFrame() { [native code] }",
        "clipboard−[object Clipboard]",
        "getBattery−function getBattery() { [native code] }",
        "getGamepads−function getGamepads() { [native code] }",
        "javaEnabled−function javaEnabled() { [native code] }",
        "sendBeacon−function sendBeacon() { [native code] }",
        "vibrate−function vibrate() { [native code] }",
    ]

    config = [
        1920 + 1080,                    # [0] screen.width + screen.height = 3000
        date_str,                        # [1] 时间字符串
        4294967296,                      # [2] jsHeapSizeLimit (Chrome 典型值: 4GB)
        attempt,                         # [3] PoW尝试次数 / Math.random()
        USER_AGENT,                      # [4] UA
        f"https://sentinel.openai.com/sentinel/{SENTINEL_SV}/sdk.js",  # [5] script src
        None,                            # [6] data-build (通常为null)
        "ja-JP",                         # [7] navigator.language（与 JP 出口 IP 对齐）
        "ja-JP,ja,en-US,en",             # [8] navigator.languages
        round(elapsed_ms) if elapsed_ms else random.randint(1, 100),  # [9] 耗时 / Math.random()
        random.choice(navigator_props),  # [10] 随机navigator属性
        "_reactListening" + "".join(random.choices("abcdefghijklmnopqrstuvwxyz0123456789", k=11)),  # [11] 随机document key
        random.choice(["requestIdleCallback", "webkitRequestAnimationFrame", "onfocus", "onblur"]),  # [12] 随机window key
        round(perf_now, 10),             # [13] performance.now()
        sid,                             # [14] sid
        "",                              # [15] URL search params (注册页面通常为空)
        32,                              # [16] hardwareConcurrency (常见值: 4-32)
        round(time_origin, 1),           # [17] performance.timeOrigin
        0,                               # [18] Number("ai" in window)
        0,                               # [19] Number("InstallTrigger" in window)  Firefox特有
        0,                               # [20] Number("cache" in window)
        0,                               # [21] Number("data" in window)
        0,                               # [22] Number("solana" in window)
        0,                               # [23] Number("dump" in window) Firefox特有
        0,                               # [24] Number("requestIdleCallback" in window)
    ]
    return config


def encode_config(config: list) -> str:
    """
    将 config 数组编码为 base64 字符串。
    对应 SDK 中的 N() 函数：
        JSON.stringify(t) → TextEncoder.encode() → btoa(String.fromCharCode(...))

    注意：SDK 使用 TextEncoder 将 JSON字符串 编码为 UTF-8 字节，然后逐个字节 btoa。
    这等效于 Python 的：json_str.encode('utf-8') → base64 encode
    """
    json_str = json.dumps(config, ensure_ascii=False, separators=(',', ':'))
    # 使用 UTF-8 编码再 base64 处理（与 SDK 的 TextEncoder + btoa 一致）
    encoded = base64.b64encode(json_str.encode('utf-8')).decode('ascii')
    return encoded


def fnv1a_hash(text: str) -> str:
    """
    FNV-1a 哈希算法（32位）。
    对应 SDK 中的哈希函数，用于 Proof of Work 校验。

    JS 原始代码：
        let e = 2166136261;
        for (let r = 0; r < t.length; r++)
            e ^= t.charCodeAt(r),
            e = Math.imul(e, 16777619) >>> 0;
        e ^= e >>> 16;
        e = Math.imul(e, 2246822507) >>> 0;
        e ^= e >>> 13;
        e = Math.imul(e, 3266489909) >>> 0;
        e ^= e >>> 16;
        return (e >>> 0).toString(16).padStart(8, "0");
    """
    h = 2166136261
    for ch in text:
        h ^= ord(ch)
        # Math.imul 模拟：32位整数乘法
        h = _imul(h, 16777619) & 0xFFFFFFFF

    h ^= (h >> 16)
    h = _imul(h, 2246822507) & 0xFFFFFFFF
    h ^= (h >> 13)
    h = _imul(h, 3266489909) & 0xFFFFFFFF
    h ^= (h >> 16)
    h = h & 0xFFFFFFFF

    return format(h, '08x')


def _imul(a: int, b: int) -> int:
    """
    模拟 JavaScript 的 Math.imul（32位整数乘法）。
    Python 的整数没有溢出，需要手动截断为32位。
    """
    # 确保是32位无符号整数
    a = a & 0xFFFFFFFF
    b = b & 0xFFFFFFFF
    # 32位整数乘法
    result = (a * b) & 0xFFFFFFFF
    return result


def solve_proof_of_work(seed: str, difficulty: str, device_id: str, max_attempts: int = 500000) -> str:
    """
    计算 Proof of Work。

    SDK 中 _runCheck 的逻辑：
    1. 将 config[3] 设为尝试次数（nonce）
    2. 将 config[9] 设为 Math.round(performance.now() - startTime)
    3. 编码 config → base64 字符串 c
    4. 计算 fnv1a(seed + c) → 8位hex
    5. 如果 hex[:len(difficulty)] <= difficulty，则返回 c + "~S"

    Args:
        seed: 服务端返回的 seed
        difficulty: 服务端返回的 difficulty（16进制前缀）
        device_id: 设备ID
        max_attempts: 最大尝试次数

    Returns:
        PoW答案字符串，格式为 base64_encoded_config + "~S"
    """
    start_time = time.time() * 1000  # 毫秒

    # 生成初始 config
    config = generate_fingerprint_data(device_id, attempt=0, elapsed_ms=0)

    diff_len = len(difficulty)

    for i in range(max_attempts):
        # 更新尝试次数和耗时
        config[3] = i
        config[9] = round(time.time() * 1000 - start_time)

        # 编码为 base64
        encoded = encode_config(config)

        # 计算哈希
        hash_input = seed + encoded
        hash_result = fnv1a_hash(hash_input)

        # 检查是否满足难度要求
        if hash_result[:diff_len] <= difficulty:
            return encoded + "~S"

    # 如果达到最大尝试次数仍未找到，返回错误前缀
    return "wQ8Lk5FbGpA2NcR9dShT6gYjU7VxZ4D" + encode_config(["e"])


def generate_requirements_token(device_id: str) -> str:
    """
    生成 requirements token（p 字段的值）。
    对应 SDK 中的 getRequirementsToken() / _generateRequirementsTokenAnswerBlocking()

    这是第一次调用 sentinel/req 时 p 字段的值。
    它就是简单的 config 编码 + "~S" 后缀，不需要PoW。
    """
    config = generate_fingerprint_data(device_id, attempt=1, elapsed_ms=0)
    encoded = encode_config(config)
    return "gAAAAAC" + encoded + "~S"


def build_sentinel_request_body(p: str, device_id: str, flow: str) -> str:
    """
    构建 sentinel/req 的请求体。

    Args:
        p: 指纹数据（requirements token）
        device_id: 设备ID
        flow: 流程类型
            - "username_password_create": 步骤6（注册前）
            - "authorize_continue": 步骤9（验证码验证后）
            - "oauth_create_account": 步骤11（创建账号前）
    """
    body = {
        "p": p,
        "id": device_id,
        "flow": flow,
    }
    return json.dumps(body, separators=(',', ':'))


def build_sentinel_token_header(
    p: str,
    turnstile_token: str,
    sentinel_token: str,
    device_id: str,
    flow: str
) -> str:
    """
    构建 openai-sentinel-token 请求头的值。

    最终格式为 JSON 字符串：
    {"p":"<proof>","t":"<turnstile>","c":"<token>","id":"<device_id>","flow":"<flow>"}
    """
    header_value = {
        "p": p,
        "t": turnstile_token or "",
        "c": sentinel_token,
        "id": device_id,
        "flow": flow,
    }
    return json.dumps(header_value, separators=(',', ':'))


def get_enforcement_token(sentinel_response: dict, seed: str, difficulty: str, device_id: str) -> str:
    """
    在有 PoW 要求时，计算 enforcement token（带PoW的p字段）。
    对应 SDK 中的 getEnforcementToken()。

    Args:
        sentinel_response: sentinel/req 的响应 JSON
        seed: proofofwork.seed
        difficulty: proofofwork.difficulty
        device_id: 设备ID

    Returns:
        PoW 结果字符串（base64 + ~S）
    """
    pow_data = sentinel_response.get("proofofwork", {})

    if pow_data.get("required"):
        pow_seed = pow_data.get("seed", "")
        pow_difficulty = pow_data.get("difficulty", "")
        answer = solve_proof_of_work(pow_seed, pow_difficulty, device_id)
        return "gAAAAAB" + answer

    # 不需要PoW时，返回简单的指纹
    return generate_requirements_token(device_id)
