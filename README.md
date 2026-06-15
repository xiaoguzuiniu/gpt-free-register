# GPT 协议注册机

纯协议层 ChatGPT 账号自动注册工具。**不开浏览器、不用 selenium**——直接用 `curl_cffi` 模拟 Chrome TLS 指纹打 HTTP 接口，单进程多线程并发，注册成功后自动跑 Codex OAuth 并落 [CLIProxyAPI](https://github.com/router-for-me/CLIProxyAPI) 兼容凭证。

提供 **CLI** 与 **本地 WebUI** 两种入口。

---

## ✨ 功能

- **协议层注册**：providers → CSRF → OAuth signin → email-verification → create-account → OAuth 回调，全程纯 HTTP
- **Sentinel/PoW**：自动调用 Node.js 跑 OpenAI sentinel SDK 生成 turnstile + PoW token
- **Outlook 邮箱池**：自动领取邮箱、双协议（Graph + IMAP）取 OTP
- **2FA(TOTP)**：可选，注册成功后自动 enroll TOTP 并落 base32 secret
- **Codex OAuth 自动授权**：注册成功后用全新干净 session 走 phone-verification → consent → 拿 code → 换 token → 落 [CPA](https://github.com/router-for-me/CLIProxyAPI) 兼容的 `codex-邮箱.json`
- **接码自动化**：手机验证关卡接入 [GrizzlySMS](https://grizzlysms.com)，自动取号、收码、换号重试
- **WebUI 控制台**：批量启动、实时任务日志、账号管理、Codex 凭证下载、配置热加载（无需重启）
- **失败号码自动回收**：识别 `account_deactivated` 等死号错误码，自动标记不再重试

## 📋 环境要求

- **Python** 3.10+
- **Node.js** 18+（用于跑 OpenAI sentinel SDK；`sentinel-runner.js` 在 vm 沙箱里执行真实 sdk.js）
- 一个能稳定访问 `chatgpt.com` / `auth.openai.com` 的代理（本机 Clash / 商业代理皆可）
- **Outlook 邮箱池**素材（自购，4 段格式 `email----password----clientId----refreshToken`）
- **GrizzlySMS API key**（如需 Codex 自动授权，约 $0.13/号）

## 🚀 安装与启动

```bash
# 1. 克隆仓库
git clone <your-repo-url>
cd GPT协议注册-0419

# 2. 安装 Python 依赖
pip install -r requirements.txt

# 3. 验证 Node.js 可用（sentinel runner 需要）
node --version

# 4. 准备邮箱池
cp 用于注册的邮箱.txt.example 用于注册的邮箱.txt
# 编辑这个文件，填入真实 Outlook 账号（每行 4 段 ---- 分隔）

# 5. 配置代理（如有需要）
# 编辑 config/proxy.py 的 PROXY_POOL，写入你的代理地址

# 6. (可选) 启用 Codex 自动授权：填接码 key
# 编辑 config/codex.py 的 SMS_API_KEY，或先把 ENABLE_CODEX_AUTO=False 跳过
```

## ▶️ 使用方式 1：命令行（CLI）

```bash
# 注册 1 个号（默认）
python main.py

# 批量注册 10 个，3 线程并发，单个失败继续
python main.py -n 10 --workers 3 --continue-on-fail

# 显示详细日志
python main.py -n 1 --verbose

# 指定每次注册之间间隔
python main.py -n 5 --delay 3
```

完整参数：

| 参数 | 含义 | 默认 |
|---|---|---|
| `-n, --count` | 要注册的账号数量 | 1 |
| `--workers` | 并发线程数（>1 时走线程池） | 1 |
| `--delay` | 每次注册间隔秒数 | 0 |
| `--continue-on-fail` | 单个失败后继续下一个 | False |
| `--verbose` | DEBUG 级别日志 | False |

## ▶️ 使用方式 2：WebUI 控制台

```bash
python web.py
# 自动打开浏览器到 http://127.0.0.1:5000
# 默认只绑定本地，安全

# 换端口
python web.py --port 8000
# 允许局域网访问（敏感工具，请确认网络可信）
python web.py --host 0.0.0.0
```

WebUI 有 5 个 Tab：

- **注册** —— 填数量+并发，点开始；任务表每 3 秒轮询，点"日志"实时尾随
- **账号** —— 已注册账号表，一键复制全部 Token / 整行
- **Codex 授权** —— 已生成的 CPA 兼容凭证列表，一键下载 JSON（下载后自动标记已导出）
- **邮箱池** —— 粘贴导入素材、查看状态、手动标失败/删除
- **配置** —— 可视化改 14 项运行配置，保存即生效（**无需重启**）

## 🔑 Codex OAuth 授权说明

注册成功后会自动跑 Codex 授权（如果 `ENABLE_CODEX_AUTO=True`）：

1. 用**全新干净 session**重新登录该邮箱（不复用注册 session，避开 `choose-an-account` 卡死）
2. 走标准风控路径：邮箱 OTP → **手机短信验证（接码自动）** → consent → 拿 code → 换 token
3. 落盘到 `codex_accounts/codex-邮箱-plan.json`，格式严格对照 [CPA 源码](https://github.com/router-for-me/CLIProxyAPI/blob/main/internal/auth/codex/token.go)
4. 文件可**直接拷到 CPA 的 `auths/` 目录使用**

如果暂时不需要 Codex 凭证，把 `config/codex.py` 里 `ENABLE_CODEX_AUTO = False` 即可跳过整个步骤。

### 单独补跑 Codex

如果一个号注册时 Codex 那步失败了，可以单独补跑（不需要重新注册）：

```bash
python tools/test_codex_oauth.py --email <已注册邮箱> --verbose
```

会消耗一封邮箱 OTP + 一个接码短信（约 $0.13）。

## ⚙️ 配置项

所有配置在 `config/` 目录下，按主题分文件。**WebUI 配置 Tab 暴露的 14 项支持热加载**（保存即生效），其它需重启进程：

| 文件 | 内容 | WebUI 可改 |
|---|---|---|
| `config/codex.py` | Codex OAuth + 接码（GrizzlySMS） | ✅ ENABLE_CODEX_AUTO / SMS_COUNTRY / SMS_SERVICE / SMS_API_KEY / SMS_MAX_RETRIES / SMS_CODE_WAIT |
| `config/email.py` | Outlook 邮箱池 + OTP 轮询 | ✅ USE_EMAIL_SERVICE / OTP_MAX_WAIT / OTP_POLL_INTERVAL |
| `config/twofa.py` | 2FA 开关 | ✅ ENABLE_2FA |
| `config/flow_trigger.py` | 注册成功后触发自定义 Flow | ✅ ENABLE_FLOW_TRIGGER |
| `config/register.py` | 注册默认信息 | ✅ REGISTER_BIRTHDAY |
| `config/proxy.py` | 代理池 | ✅ PROXY_POOL |
| `config/browser.py` | 浏览器指纹 | ❌（协议级，改了易触发风控）|
| `config/openai_protocol.py` | OpenAI OAuth 客户端参数、Sentinel 版本 | ❌（同上）|

## 📁 数据文件

注册产物全部以文件形式落在项目根。**全部已加入 `.gitignore`，不会进仓库**：

| 文件/目录 | 内容 |
|---|---|
| `用于注册的邮箱.{json,txt}` | Outlook 邮箱池（含密码/clientId/refreshToken），运行时状态机 |
| `注册成功的邮箱.{json,txt}` | 已注册账号列表 |
| `注册成功的token.txt` | 每行一个 accessToken |
| `accounts/` | 历史批次归档目录（按日期命名） |
| `codex_accounts/` | Codex OAuth 凭证（CPA 兼容） |
| `codex_导出状态.json` | Codex 凭证的 WebUI 导出标记 |
| `注册任务.json` | WebUI 任务表 |
| `注册日志/` | 每个任务一份 `<uuid>.log` |
| `accounts_viewer.html` | 自动生成的静态查看页（直接双击打开） |

## 🗂️ 项目结构

```
.
├── main.py                # CLI 入口
├── web.py                 # WebUI 入口
├── config/                # 配置（分模块；支持热加载）
│   ├── codex.py           #   Codex OAuth + 接码
│   ├── email.py           #   邮箱 / OTP
│   ├── proxy.py           #   代理池
│   └── ...
├── core/                  # 核心实现
│   ├── session.py         #   BrowserSession：TLS 指纹 / cookies / 代理
│   ├── chatgpt_auth.py    #   步骤 1-3（providers / CSRF / signin）
│   ├── openai_auth.py     #   步骤 4-12（authorize 链 / OTP / 创建账号）
│   ├── sentinel.py        #   Sentinel token 生成
│   ├── sentinel_runner.py #   通过 subprocess 调 Node 跑 sdk.js
│   ├── email_provider.py  #   邮箱调度（封装 outlook_client）
│   ├── outlook_client.py  #   Outlook 双协议取件
│   ├── codex_oauth.py     #   Codex OAuth 全流程
│   ├── sms_provider.py    #   GrizzlySMS 接码客户端
│   ├── account_export.py  #   注册后处理：取 token / 设 2FA / 落盘
│   ├── flow_trigger.py    #   注册后可选 Flow 触发
│   ├── db.py              #   文件持久化层
│   └── registration_service.py  # 线程池服务层（给 WebUI 用）
├── webui/                 # Flask 控制台
│   ├── app.py             #   所有 JSON API 路由
│   ├── config_editor.py   #   安全读写 config/*.py
│   └── templates/index.html  # 单页前端（原生 JS + fetch）
├── sentinel/              # Node.js 资源
│   ├── sdk.js             #   OpenAI sentinel SDK（真实代码，不动）
│   └── sentinel-runner.js #   在 vm 沙箱里执行 sdk.js 并产出 token
└── tools/
    └── test_codex_oauth.py  # Codex 单独补跑工具
```

## 🔧 工作流程一览

```
单次注册（CLI / WebUI 都走同一套）
   │
   ▼
[1-3] providers / CSRF / signin   ─── chatgpt.com
   ▼
[4]   follow authorize             ─── auth.openai.com
   ▼
[9]   sentinel token (authorize_continue, 带 PoW)
   ▼
[10]  validate email OTP            ─── 从 Outlook 取件
   ▼
[11]  sentinel token (oauth_create_account)
   ▼
[12]  create account                ─── 名称 / 生日
   ▼
[12.5] follow continue_url          ─── 拿到 ChatGPT 登录 cookie
   ▼
[13]  fetch /api/auth/session       ─── 提取 accessToken
   ▼
[14-20] (可选) 2FA enroll            ─── 收第二封 OTP / TOTP / activate
   ▼
[Codex] (可选) 全新 session 跑 Codex OAuth
   ├── 邮箱 OTP（再收一封）
   ├── 手机验证（GrizzlySMS 自动收码，失败换号重试）
   ├── consent → workspace/select
   └── 拿 code → 换 token → 落盘 codex_accounts/
   ▼
保存账号 → 批次归档 → (可选) 触发 Flow
```

## 🛡️ 安全 & 责任声明

- **本工具仅供学习交流**。批量注册可能违反 OpenAI 服务条款，请自行评估风险
- **不要把 `用于注册的邮箱.txt`、`注册成功的*.txt`、`codex_accounts/` 推到公开仓库**，`.gitignore` 已默认屏蔽，clone 后请勿手动 `git add -f` 这些文件
- **API key 别硬编码**。`config/codex.py` 的 `SMS_API_KEY` 默认为空，请运行时填或通过 WebUI 改
- **WebUI 默认只绑 127.0.0.1**。如要 `--host 0.0.0.0` 暴露到局域网，请确认网络可信
- 注册产生的 access token 是敏感凭证，等同于该账号的密码，妥善保管

## ❓ 常见问题

**Q: `curl: (35) TLS connect error`**
A: 代理抖动 / TLS 握手失败。检查代理是否正常（特别是 Clash 节点）。注册流程自带 3 次重试，偶发抖动会自动恢复；持续失败说明代理本身有问题。

**Q: 验证码收到了，但提交时返回 `account_deactivated`**
A: 这个邮箱对应的 ChatGPT 账号已被 OpenAI 删除/停用，邮箱本身废了。新代码会**自动**把这个邮箱标记为 `failed`，不再重试。换批新邮箱即可。

**Q: 我没有接码平台，能用吗**
A: 能。注册主流程**不依赖接码**，只有 Codex OAuth 自动授权那步要。把 `config/codex.py` 里 `ENABLE_CODEX_AUTO = False`，注册照常跑，只是不会自动产出 Codex 凭证。

**Q: Codex 授权失败，但账号本身注册成功了**
A: 主流程把 Codex 当成"成功后的额外步骤"，它失败**不影响**账号注册结果。可以单独用 `python tools/test_codex_oauth.py --email <邮箱>` 补跑。

**Q: 配置改了没生效**
A: WebUI 配置 Tab 暴露的 14 项支持热加载（保存后 banner 显示"立即生效"）。如果你直接改 `.py` 文件，则需要重启 `python web.py` / 重启 CLI 进程。

**Q: 多线程并发是怎么实现的**
A: 每个线程一个 `BrowserSession` + 一个代理（从 PROXY_POOL 随机抽），邮箱池用 `threading.RLock` + 原子领取保证不冲突。建议 workers ≤ 代理池大小，避免同代理多线程被风控关联。

## 📜 License

MIT
