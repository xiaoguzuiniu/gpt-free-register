# -*- coding: utf-8 -*-
"""
代理池配置

每次注册随机抽取一个代理，保证不同 sid 之间彼此独立，避免风控关联。

协议说明：
    - http:// / https://   HTTP(S) 代理
    - socks5://            SOCKS5（DNS 本地解析，可能泄漏）
    - socks5h://           SOCKS5（DNS 在代理端解析，推荐，避免 DNS-IP 错配）
"""
import random


# Cliproxy 新加坡节点。未带 sid 的地址由服务端自行轮换，带 sid 的地址用于并发时分散会话。
# 统一用 socks5h://（DNS 在代理端解析），避免本地 DNS 错配导致 TLS WRONG_VERSION_NUMBER。
PROXY_POOL = [
    # Clash 本地代理（HTTP 代理端口）
    "http://127.0.0.1:7897",
    
    # 以下是海歪IP 代理（国内无法直连，已注释）
  #  "socks5h://xccf1148614-region-SG:zkvfjxtv@sg2.cliproxy.io:3010",
 ##  "socks5h://xccf1148614-region-SG-sid-D71PqY4i-t-5:zkvfjxtv@sg2.cliproxy.io:3010",
  ##  "socks5h://xccf1148614-region-SG-sid-jkGUtBeA-t-5:zkvfjxtv@sg2.cliproxy.io:3010",
  #  "socks5h://xccf1148614-region-SG-sid-HDVrSaZa-t-5:zkvfjxtv@sg2.cliproxy.io:3010",
    # "http://user-sub.xiaoguyouqu-country-us-session-EhW7N8:1204748902gkw@proxy.haiwaiip.net:1463",
    # "http://user-sub.xiaoguyouqu-country-us-session-hspp4A:1204748902gkw@proxy.haiwaiip.net:1466",
    # "http://user-sub.xiaoguyouqu-country-us-session-7sD4Yk:1204748902gkw@proxy.haiwaiip.net:1469",
    # "http://user-sub.xiaoguyouqu-country-us-session-y3XcZh:1204748902gkw@proxy.haiwaiip.net:1463",
    # "http://user-sub.xiaoguyouqu-country-us-session-6Mj4kj:1204748902gkw@proxy.haiwaiip.net:1469",
    # "http://user-sub.xiaoguyouqu-country-us-session-EMfWAb:1204748902gkw@proxy.haiwaiip.net:1461",
    # "http://user-sub.xiaoguyouqu-country-us-session-T5cFrG:1204748902gkw@proxy.haiwaiip.net:1462",
    # "http://user-sub.xiaoguyouqu-country-us-session-FD2QGR:1204748902gkw@proxy.haiwaiip.net:1470",
    # "http://user-sub.xiaoguyouqu-country-us-session-JwNABJ:1204748902gkw@proxy.haiwaiip.net:1470",
    # "http://user-sub.xiaoguyouqu-country-us-session-SCkKTx:1204748902gkw@proxy.haiwaiip.net:1469",
]


def pick_proxy() -> str:
    """从代理池中随机抽取一个代理 URL；池为空时返回空串（即不使用代理）。"""
    return random.choice(PROXY_POOL) if PROXY_POOL else ""


# 兼容入口：默认每次进程启动随机选一个，作为本次注册全程的固定代理
PROXY = pick_proxy()