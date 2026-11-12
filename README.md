# 统一登录中心（多服务版）

一个登录中心 + 管理控制台，给同一父域下的多个服务使用。

每个服务拥有**独立密码、独立 Cookie**；签名密钥只存在 auth-server，业务服务不保存：

- 登录 push-server 不会登录 TaskOps
- 登录 TaskOps 不会登录 opencode
- 各服务可以单独重置密码、强制下线
- 所有服务共用同一个登录页和同一个管理后台

当前生产使用：

```text
登录入口：   https://auth.xct258.top
Cookie 父域：.xct258.top
管理后台：   https://auth.xct258.top/admin
```

同一父域下的服务都由这一个登录中心管理。以后要接入其他父域（例如 `example.com`），在管理界面新增域名即可。

## 架构

```text
                       auth.xct258.top
                       ├── /login        服务登录页
                       ├── /admin        管理控制台
                       ├── /api/auth/*   服务登录 / 验签
                       └── SQLite        域名 / 服务 / 管理员 / 审计
                                  │
          ┌───────────────────────┼───────────────────────┐
          │                       │                       │
 push-server.o1-1...       2-cfyx.o1-1...          1-cfyx.o1-1...
 sso_push                  sso_taskops              sso_opencode
 独立密码                  独立密码                 独立密码
```

同一个父域下：

```text
Cookie Domain: .xct258.top
Cookie 名:     sso_push / sso_taskops / sso_opencode
```

服务只读取自己的 Cookie，因此登录态互不影响。

## 两种接入方式

| 方式 | 是否改代码 | 适用 |
| --- | --- | --- |
| NPM `auth_request` | 不需要 | opencode、Webtop、第三方 Web 服务 |
| 业务中间件 `auth.py` | 需要 | push-server、TaskOps、自己完全控制源码的服务 |

两种方式最终都是调用 auth-server：

```text
GET https://auth.xct258.top/api/auth/verify?service=<服务ID>
```

auth-server 返回 `204` 放行，`401` 拒绝。

### NPM 方式

```text
浏览器 → NPM → auth_request → auth-server → NPM → 上游服务
```

- 不改业务代码
- 支持 WebSocket
- 可以自动注入上游 Basic Auth
- 适合不能改代码的服务

### 业务中间件方式

```text
浏览器 → 业务服务 → auth-server 验签 → 业务响应
```

- 可以区分页面 302 和 API 401
- 可以自定义公开路径
- 适合自己写的 FastAPI / Vue 应用

## 快速部署

镜像由 GitHub Actions 按 `install/app.conf` 构建并推送 Docker Hub：

- 仓库 Actions → **Build and Push Docker Image** → Run workflow
- 需要 Secrets：`DOCKERACC` / `DOCKERPWD`
- 镜像：`xct258/sso-auth:latest`

服务器上：

```bash
cd auth-server
cp .env.example .env
# 修改 .env：AUTH_HOST、AUTH_COOKIE_DOMAIN、ADMIN_PASSWORD 等
docker compose up -d
curl http://127.0.0.1:8290/api/health
```

> auth-server 默认只监听 `127.0.0.1:8290`，适合 NPM 和 auth-server 在同一台机器。对外只通过 NPM 的 HTTPS 域名访问，不要直接暴露 8290。

第一次启动会：

1. 创建 SQLite：`/data/auth.db`
2. 创建主密钥：`/data/.master_key`
3. 写入初始域名（来自 `AUTH_*`）
4. 创建初始管理员

`ADMIN_PASSWORD` 留空时自动生成，写入：

```text
/data/initial_admin_password.txt
```

> 如果先用 `uvicorn` 手动部署，数据默认在服务器 `/data`；以后切换 `docker compose` 时，
> 需要把 `/data/auth.db` 和 `/data/.master_key` 复制到仓库的 `auth-server/data/`，
> 否则容器会当成新实例重新初始化。

登录管理后台：

```text
https://auth.xct258.top/admin
```

直接用 Python 跑（开发调试）：

```bash
pip install -r requirements.txt
AUTH_HOST=127.0.0.1 \
AUTH_COOKIE_DOMAIN= \
AUTH_ALLOWED_SUFFIX= \
AUTH_DB_PATH=/tmp/auth.db \
AUTH_KEY_PATH=/tmp/auth.key \
ADMIN_USERNAME=admin \
ADMIN_PASSWORD=admin12345 \
uvicorn main:app --host 127.0.0.1 --port 8290
```

## 环境变量

### auth-server

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `AUTH_DOMAIN_NAME` | `xct258` | 初始域名名称 |
| `AUTH_HOST` | `auth.xct258.top` | 初始登录主机名 |
| `AUTH_COOKIE_DOMAIN` | `.xct258.top` | 初始 Cookie 父域；本地调试可留空 |
| `AUTH_ALLOWED_SUFFIX` | 同 Cookie 父域 | 允许 `next` 跳转的后缀 |
| `AUTH_SITE_NAME` | `统一登录` | 登录页标题 |
| `AUTH_WALLPAPER_URL` | 随机壁纸 | 登录页壁纸 |
| `ADMIN_USERNAME` | `admin` | 初始管理员用户名 |
| `ADMIN_PASSWORD` | 空 | 初始管理员密码；留空自动生成 |
| `ADMIN_SESSION_HOURS` | `12` | 管理后台会话小时数 |
| `SSO_SESSION_DAYS` | `7` | 新服务默认会话天数 |
| `AUTH_DB_PATH` | `/data/auth.db` | SQLite 路径 |
| `AUTH_KEY_PATH` | `/data/.master_key` | 主密钥路径 |
| `AUTH_MASTER_KEY` | 空 | 可选，64 位 hex；优先级高于文件 |
| `UVICORN_HOST` | `127.0.0.1` | 监听地址；NPM 同机时保持回环 |
| `UVICORN_PORT` | `8290` | 监听端口 |

### 业务服务

在管理界面创建服务后生成：

```dotenv
AUTH_ENABLED=true
SERVICE_ID=taskops
SSO_VERIFY_URL=https://auth.xct258.top/api/auth/verify
SSO_LOGIN_URL=https://auth.xct258.top/login
SSO_COOKIE_NAME=sso_taskops
SSO_COOKIE_DOMAIN=.xct258.top
SSO_ALLOWED_REDIRECT_SUFFIX=.xct258.top
```

业务服务不需要保存登录密码；auth-server 同时保存 scrypt 哈希和主密钥加密的密码密文，管理后台可以按需查看当前密码。

## 管理控制台

登录 `https://auth.xct258.top/admin` 只需要**管理密码**，不需要输入用户名。管理员用户名仅用于初始化数据库。

登录后进入「接入管理」，一个页面同时管理登录域名和服务：

### 登录域名

- 当前登录域名卡片：`auth.xct258.top` / `.xct258.top`
- 编辑登录主机名、Cookie 父域、允许跳转后缀
- 配置登录页标题和壁纸
- 有多个父域时，用顶部下拉切换

新增域名时：

1. DNS 添加 `auth.<新域名>`
2. NPM 添加 Proxy Host 指向 `127.0.0.1:8290`
3. 申请 HTTPS 证书
4. 管理界面添加域名记录
5. 该域名下的服务使用新的 `SSO_LOGIN_URL`

### 服务

- 添加 / 编辑 / 停用 / 删除服务
- 自动生成独立密码、Cookie
- 重置密码
- 强制下线（递增 Token 版本）
- 查看 / 复制 `.env` 和 NPM 配置
- 查看当前密码
- 可选「上游使用 Basic Auth」：填写用户名/密码后，生成的 NPM 配置会自动注入 `Authorization: Basic ...`
- 查看最近登录时间

服务密码可以在管理后台随时查看。

## 接入新服务

### 1. 在管理界面创建服务

填写：

```text
所属域名:   xct258
服务名称:   TaskOps
服务 ID:    taskops
公开地址:   https://2-cfyx.o1-1.xct258.top
登录密码:   留空自动生成
会话天数:   7
```

保存后会得到：

```text
服务密码
Cookie 名：sso_taskops
```

### 2. 复制鉴权模板

完整模板在 [`examples/sso-service/`](examples/sso-service/)：

```bash
cp examples/sso-service/auth.py 新服务/auth.py
cp examples/sso-service/frontend-auth.js 新服务/前端/src/auth.js
```

`auth.py` 默认放行：

```text
/api/auth/status
/api/auth/logout
/api/health
/assets/*
/favicon.ico
/favicon.svg
```

按服务补充：

```python
# Webhook / 回调等公开接口
PUBLIC_API_PATHS = {"/api/webhook"}

# 未登录返回 401 而不是 302 的路径
API_PATHS = set()
API_PREFIXES = ("/api/",)
```

### 3. 注册中间件

```python
import auth

app.add_middleware(auth.AuthMiddleware)
app.include_router(auth.router)
```

行为：

| 请求 | 未登录时 |
| --- | --- |
| 页面 | `302` 到 `/login?service=taskops&next=...` |
| `/api/*` | `401 {"detail":"未登录或登录已过期"}` |
| `/api/health` | 放行 |
| `/assets/*` | 放行 |

### 4. NPM 无代码接入

如果服务不方便改代码，可以让 NPM 做 `auth_request`：

```nginx
location = /_sso_auth {
    internal;
    proxy_pass https://auth.xct258.top/api/auth/verify?service=taskops;
    proxy_ssl_server_name on;
    proxy_set_header Host auth.xct258.top;
    proxy_pass_request_body off;
    proxy_set_header Content-Length "";
}

location / {
    auth_request /_sso_auth;
    error_page 401 = @sso_login;

    # 可选：上游自带 Basic Auth 时注入
    # proxy_set_header Authorization "Basic <base64(用户名:密码)>";

    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection $http_connection;
    proxy_http_version 1.1;
    proxy_buffering off;
    proxy_read_timeout 3600s;

    include conf.d/include/proxy.conf;
}

location @sso_login {
    return 302 https://auth.xct258.top/login?service=taskops&next=https://$host$request_uri;
}
```

带自己 Basic Auth 的服务（例如 opencode、Webtop），在管理界面勾选「上游使用 Basic Auth」，生成的配置会自动带上：

```nginx
proxy_set_header Authorization "Basic ...";
```

Basic 密码同样用主密钥加密保存，不会出现在服务列表接口里。编辑服务时密码留空表示不修改。

## 验签方式

所有服务统一走 auth-server 集中验签。业务服务不保存 `SERVICE_SECRET`，每个受保护请求带着 Cookie 调用：

```text
GET https://auth.xct258.top/api/auth/verify?service=<服务ID>
```

auth-server 返回 `204` 放行，`401` 拒绝。

服务只需要：

```dotenv
SERVICE_ID=taskops
SSO_COOKIE_NAME=sso_taskops
SSO_LOGIN_URL=https://auth.xct258.top/login
SSO_VERIFY_URL=https://auth.xct258.top/api/auth/verify
```

当前 `push-server`、`web-TaskOps` 使用业务中间件方式；opencode、Webtop 这类第三方服务使用 NPM `auth_request`。

代价：每个受保护请求多一次 auth-server 调用；auth-server 不可用时，这些服务会拒绝登录。

## Token 与 Cookie

Token 由 auth-server 内部签名，业务服务不参与验签：

```text
Cookie: sso_<服务ID>

Token: v1.<service_id>.<token_version>.<expires>.<signature>
```

auth-server 验签时检查：

1. HMAC 签名正确
2. `service_id` 与请求的 `service` 参数一致
3. `token_version` 是数据库当前值
4. `expires` 未过期
5. 服务处于启用状态

`SERVICE_SECRET` 不再下发给业务服务；签名密钥只在 auth-server 内部使用。

### 强制下线

管理界面「强制下线」会递增服务端的 `token_version`。

- 所有服务：下一次请求立即生效，因为每次受保护请求都会查 auth-server

## 登录流程

```text
访问 TaskOps
  ↓ 未登录
302 → https://auth.xct258.top/login?service=taskops&next=...
  ↓ 输入 TaskOps 自己的密码
校验 taskops 的 password_hash
  ↓ 成功
Set-Cookie: sso_taskops=...; Domain=.xct258.top; HttpOnly
  ↓
302 回 TaskOps
  ↓
TaskOps 调 auth-server 验签
```

登录 push-server 不会产生 `sso_taskops`，因此不会登录 TaskOps。

## 增加其他父域

当前只使用 `xct258.top`。如果要接入完全不同的父域，例如 `example.com`：

1. DNS 添加 `auth.example.com`
2. NPM 添加 Proxy Host 指向 `127.0.0.1:8290`
3. 申请 `auth.example.com` 的 HTTPS 证书
4. 管理界面「接入管理」→「添加域名」：

```text
名称:           example
登录主机:       auth.example.com
Cookie 父域:    .example.com
允许跳转后缀:   .example.com
```

5. 该域名下的服务使用：

```dotenv
SSO_LOGIN_URL=https://auth.example.com/login
SSO_COOKIE_DOMAIN=.example.com
SSO_VERIFY_URL=https://auth.example.com/api/auth/verify
```

不同父域之间 Cookie 不共享，所以用户在不同父域下需要分别登录。这是浏览器 Cookie 的限制，不是系统缺陷。

## NPM 与 auth-server 不在同一台机器

当前生产是：

```nginx
proxy_pass https://auth.xct258.top/api/auth/verify?service=webtop;
proxy_ssl_server_name on;
proxy_set_header Host auth.xct258.top;
```

如果 NPM 和 auth-server 分开部署：

### 内网地址（推荐）

```nginx
proxy_pass http://10.0.0.5:8290/api/auth/verify?service=webtop;
proxy_set_header Host auth.xct258.top;
```

auth-server 需要监听内网地址：

```dotenv
UVICORN_HOST=10.0.0.5
```

或者监听 `0.0.0.0`，并用防火墙只允许 NPM 的 IP。

### 公网 HTTPS

```nginx
proxy_pass https://auth.xct258.top/api/auth/verify?service=webtop;
proxy_ssl_server_name on;
proxy_set_header Host auth.xct258.top;
```

注意：如果 NPM 自己就负责 `auth.xct258.top`，这条路径会绕 Cloudflare 再回到自己，延迟会变大。实际部署后如果出现 502、403 或明显变慢，可以把 NPM 这一处单独改回内网地址，业务服务的 `SSO_VERIFY_URL` 继续使用公网 HTTPS。

## 安全说明

- 管理后台使用独立的管理员账号和 host-only Cookie，不设置父域
- 管理接口使用 CSRF Token
- 服务密码使用 scrypt 哈希校验，同时用主密钥加密保存，供管理员查看
- 上游 Basic Auth 密码同样用主密钥加密保存，不会出现在服务列表接口里
- Token 签名密钥只存在 auth-server；业务服务不保存
- 登录接口按服务 + IP 限流：5 次失败锁 60 秒
- `next` 只允许跳到该域名配置的后缀
- 修改服务密码不会影响其他服务
- 主密钥 `/data/.master_key` 和数据库 `/data/auth.db` 必须一起备份；丢失主密钥会导致 Token 签名和密码密文无法恢复

## 验证

```bash
# 健康检查
curl http://127.0.0.1:8290/api/health

# 管理后台
curl -I https://auth.xct258.top/admin

# 服务登录页
curl -I 'https://auth.xct258.top/login?service=taskops'

# 未登录接口
curl -i 'https://auth.xct258.top/api/auth/verify?service=taskops'   # 401

# 登录后
curl -i -c /tmp/sso.jar \
  -H 'Content-Type: application/json' \
  -d '{"password":"服务密码"}' \
  'https://auth.xct258.top/api/auth/login?service=taskops'

curl -i -b /tmp/sso.jar \
  'https://auth.xct258.top/api/auth/verify?service=taskops'        # 204
```

## API 端点

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/api/health` | 健康检查 |
| `GET` | `/api/site` | 管理登录页的站点名和壁纸 |
| `GET` | `/api/config?service=slug` | 服务登录页配置 |
| `GET` | `/api/auth/status?service=slug` | 服务登录状态 |
| `POST` | `/api/auth/login?service=slug` | 服务登录 |
| `POST` | `/api/auth/logout?service=slug` | 退出当前服务 |
| `GET` | `/api/auth/verify?service=slug` | 集中验签：204 / 401 |
| `GET` | `/api/auth/service/slug` | 服务启用状态 / Token 版本 |
| `POST` | `/api/admin/login` | 管理员登录，只需要密码 |
| `GET` | `/api/admin/services` | 服务列表 |
| `GET` | `/api/admin/services/{id}/config` | 生成 `.env` 和 NPM 配置 |
| `GET` | `/api/admin/services/{id}/password` | 查看当前服务密码 |
| `POST` | `/api/admin/services/{id}/reset-password` | 重置服务密码 |
| `POST` | `/api/admin/services/{id}/revoke` | 强制下线 |
| `GET` | `/api/admin/audit` | 审计日志 |

## 常见问题

### 停用服务后访问会发生什么

如果服务走 NPM `auth_request`：

1. 访问服务域名
2. NPM 调 `/api/auth/verify`
3. auth-server 返回 401（服务停用或不存在）
4. NPM 302 到统一登录页
5. 登录页显示“服务已停用”或“服务不存在”的明确错误页

不会只返回裸的 `403 Forbidden`。

### 登录页提示“服务不存在”

说明访问地址里的 `service` 没有在 auth-server 注册，或者服务已经被删除。

处理：

1. 登录 `/admin`
2. 进入「接入管理」
3. 确认服务 ID 是否存在
4. 删除过就重新添加
5. 重新从业务服务跳转登录

如果只是访问 `/login` 没有带 `service`，会显示“缺少服务参数”，这是正常的；登录页必须由业务服务跳转进入。

### 登录后又跳回登录页

1. 检查 `SSO_COOKIE_NAME` 是否和服务记录里的 Cookie 名一致
2. 检查 `SSO_COOKIE_DOMAIN` 是否是 `.xct258.top`
3. 检查服务域名是否也在 `.xct258.top` 下
4. 检查 `SSO_VERIFY_URL` 是否能访问：

```bash
curl -I 'https://auth.xct258.top/api/auth/verify?service=taskops'
```

### NPM 返回 502 / 403

NPM 的 `auth_request` 如果使用公网：

```nginx
proxy_pass https://auth.xct258.top/api/auth/verify?service=webtop;
```

会经过 Cloudflare 再回到 NPM。可能遇到：

- Cloudflare 403：检查 User-Agent / WAF
- 502：NPM 无法访问公网或 DNS
- 延迟明显：NPM 这一处改回内网地址

内网地址示例：

```nginx
proxy_pass http://10.0.0.5:8290/api/auth/verify?service=webtop;
proxy_set_header Host auth.xct258.top;
```

### 返回 404：服务不属于当前登录主机

auth-server 会检查请求 Host 是否等于服务的 `auth_host`。

远程 NPM 调用时加上：

```nginx
proxy_set_header Host auth.xct258.top;
```

### 下线后还能访问

1. 确认业务服务用的是最新代码和 `SSO_VERIFY_URL`
2. 确认 auth-server 可以从业务服务访问
3. 确认管理后台点的是对应服务，不是别的服务

### 管理后台密码忘了

初始密码在：

```bash
cat /data/initial_admin_password.txt
```

如果修改后忘记，需要直接修改数据库里的管理员密码哈希，或者重新初始化管理员。

### 服务密码忘了

管理后台：

```text
接入管理 → 服务 → 查看密码
```

如果密码密文也无法解密，只能重置。

### auth-server 挂了

集中验签模式下，所有业务服务都会拒绝登录或返回 401。

这是集中验签的代价。需要保证 auth-server 的可用性：

- NPM 和 auth-server 同机时优先走回环
- 配置进程自动重启
- 监控 `/api/health`

## 备份与恢复

必须一起备份：

```text
/data/auth.db
/data/.master_key
```

建议同时备份：

```text
/data/initial_admin_password.txt
/data/sso-service-passwords.txt
/data/*-sso-nginx.conf
```

注意：

- `/data/.master_key` 丢失后，Token 签名和密码密文都无法恢复
- 数据库和主密钥不要放在同一个未加密备份里
- 恢复时保持文件权限 `600`
- 恢复后重启 auth-server

## 从旧版本迁移

新版本不再兼容旧的全局密码 / 全局 `APP_SECRET` / `sso_session`。

迁移步骤：

1. 备份旧 `.env`
2. 部署新版本，初始化数据库和管理员
3. 登录 `/admin`，创建域名和服务
4. 为每个服务复制新的 `.env`，更新业务中间件
5. 逐个重启业务服务，用户重新登录

全部迁移完成后，旧环境变量可以删除。
