# 统一登录中心（多服务版）

一个登录中心 + 管理控制台，给同一父域下的多个服务使用。

每个服务拥有**独立密码、独立 Cookie、独立签名密钥**：

- 登录 push-server 不会登录 TaskOps
- 登录 TaskOps 不会登录 opencode
- 各服务可以单独重置密码、强制下线、轮换密钥
- 所有服务共用同一个登录页和同一个管理后台

当前默认域名：

```text
auth.o1-1.xct258.top
Cookie Domain: .o1-1.xct258.top
```

后续可以增加 `auth.xct258.top` 等域名；域名、服务都在管理界面维护。

## 架构

```text
                       auth.o1-1.xct258.top
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
Cookie Domain: .o1-1.xct258.top
Cookie 名:     sso_push / sso_taskops / sso_opencode
```

服务只读取自己的 Cookie，因此登录态互不影响。

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

第一次启动会：

1. 创建 SQLite：`/data/auth.db`
2. 创建主密钥：`/data/.master_key`
3. 写入初始域名（来自 `AUTH_*`）
4. 创建初始管理员

`ADMIN_PASSWORD` 留空时自动生成，写入：

```text
/data/initial_admin_password.txt
```

登录管理后台：

```text
https://auth.o1-1.xct258.top/admin
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
uvicorn main:app --host 0.0.0.0 --port 8290
```

## 环境变量

### auth-server

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `AUTH_DOMAIN_NAME` | `o1-1` | 初始域名名称 |
| `AUTH_HOST` | `auth.o1-1.xct258.top` | 初始登录主机名 |
| `AUTH_COOKIE_DOMAIN` | `.o1-1.xct258.top` | 初始 Cookie 父域；本地调试可留空 |
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

### 业务服务

在管理界面创建服务后生成：

```dotenv
AUTH_ENABLED=true
SERVICE_ID=taskops
SERVICE_SECRET=该服务自己的密钥
SERVICE_TOKEN_VERSION=1
SSO_LOGIN_URL=https://auth.o1-1.xct258.top/login
SSO_COOKIE_NAME=sso_taskops
SSO_COOKIE_DOMAIN=.o1-1.xct258.top
SSO_ALLOWED_REDIRECT_SUFFIX=.o1-1.xct258.top
```

业务服务不需要保存登录密码，密码哈希只存在 auth-server 数据库里。

## 管理控制台

登录 `https://auth.o1-1.xct258.top/admin` 后可以：

### 域名管理

- 添加 / 编辑 / 停用域名
- 配置登录主机名、Cookie 父域、允许跳转后缀
- 配置登录页标题和壁纸

新增域名时：

1. DNS 添加 `auth.<新域名>`
2. NPM 添加 Proxy Host 指向 `127.0.0.1:8290`
3. 申请 HTTPS 证书
4. 管理界面添加域名记录
5. 该域名下的服务使用新的 `SSO_LOGIN_URL`

### 服务管理

- 添加 / 编辑 / 停用 / 删除服务
- 自动生成独立密码、Cookie 名、签名密钥
- 重置密码
- 轮换密钥
- 强制下线（递增 Token 版本）
- 查看 / 复制 `.env` 和 NPM 配置
- 查看最近登录时间

服务创建成功后，密码和密钥只显示一次，请及时复制。

## 接入新服务

### 1. 在管理界面创建服务

填写：

```text
所属域名:   o1-1
服务名称:   TaskOps
服务 ID:    taskops
公开地址:   https://2-cfyx.o1-1.xct258.top
登录密码:   留空自动生成
会话天数:   7
```

保存后会得到：

```text
服务密码
SERVICE_SECRET
SERVICE_TOKEN_VERSION
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
    proxy_pass http://127.0.0.1:8290/api/auth/verify?service=taskops;
    proxy_pass_request_body off;
    proxy_set_header Content-Length "";
}

location / {
    auth_request /_sso_auth;
    error_page 401 = @sso_login;
    include conf.d/include/proxy.conf;
}

location @sso_login {
    return 302 https://auth.o1-1.xct258.top/login?service=taskops&next=https://$host$request_uri;
}
```

带自己 Basic Auth 的服务（例如 opencode），在 SSO 通过后再注入它自己的 `Authorization` 头。

## Token 与 Cookie

每个服务独立签名：

```text
Cookie: sso_<服务ID>

Token: v1.<service_id>.<token_version>.<expires>.<signature>

signature = HMAC-SHA256(
  SERVICE_SECRET,
  "v1.<service_id>.<token_version>.<expires>"
)
```

服务端校验：

1. `service_id` 必须等于自己的 `SERVICE_ID`
2. `token_version` 必须等于自己的 `SERVICE_TOKEN_VERSION`
3. HMAC 签名正确
4. `expires` 未过期

这样 `sso_push` 的 Cookie 无法用于访问 TaskOps。

### 强制下线

管理界面「强制下线」会递增服务端的 `token_version`。

- NPM `auth_request` 模式：立即生效，因为每次都查 auth-server
- 业务中间件模式：需要把新的 `SERVICE_TOKEN_VERSION` 更新到服务环境变量并重启

「轮换密钥」会同时更换 `SERVICE_SECRET` 和 Token 版本，旧 Token 立即失效；同样需要把新配置更新到业务服务。

## 登录流程

```text
访问 TaskOps
  ↓ 未登录
302 → https://auth.o1-1.xct258.top/login?service=taskops&next=...
  ↓ 输入 TaskOps 自己的密码
校验 taskops 的 password_hash
  ↓ 成功
Set-Cookie: sso_taskops=...; Domain=.o1-1.xct258.top; HttpOnly
  ↓
302 回 TaskOps
  ↓
TaskOps 用 SERVICE_SECRET 验签
```

登录 push-server 不会产生 `sso_taskops`，因此不会登录 TaskOps。

## 后续切换到 auth.xct258.top

当前先用：

```text
auth.o1-1.xct258.top
Cookie Domain: .o1-1.xct258.top
```

以后切换时不需要改代码：

1. 给 `auth.xct258.top` 加 DNS 和 NPM Proxy Host
2. 管理界面添加域名：

```text
名称:           xct258
登录主机:       auth.xct258.top
Cookie 父域:    .xct258.top
允许跳转后缀:   .xct258.top
```

3. 把服务环境变量改为：

```dotenv
SSO_LOGIN_URL=https://auth.xct258.top/login
SSO_COOKIE_DOMAIN=.xct258.top
```

4. 用户重新登录一次

旧域名可以保留一段时间，做 302 跳到新域名。

> `.xct258.top` 会覆盖所有子域，包括 `o1-1.xct258.top`。如果 `o1-1` 下有可信度较低的服务，可以继续隔离在 `.o1-1.xct258.top`。

## 安全说明

- 管理后台使用独立的管理员账号和 host-only Cookie，不设置父域
- 管理接口使用 CSRF Token
- 服务密码使用 scrypt 哈希
- 服务密钥由主密钥 + 服务 ID + 随机盐派生，不直接存明文
- 登录接口按服务 + IP 限流：5 次失败锁 60 秒
- `next` 只允许跳到该域名配置的后缀
- 修改服务密码不会影响其他服务
- 主密钥 `/data/.master_key` 和数据库 `/data/auth.db` 必须一起备份；丢失主密钥会导致所有服务密钥无法恢复

## 验证

```bash
# 健康检查
curl http://127.0.0.1:8290/api/health

# 管理后台
curl -I https://auth.o1-1.xct258.top/admin

# 服务登录页
curl -I 'https://auth.o1-1.xct258.top/login?service=taskops'

# 未登录接口
curl -i 'https://auth.o1-1.xct258.top/api/auth/verify?service=taskops'   # 401

# 登录后
curl -i -c /tmp/sso.jar \
  -H 'Content-Type: application/json' \
  -d '{"password":"服务密码"}' \
  'https://auth.o1-1.xct258.top/api/auth/login?service=taskops'

curl -i -b /tmp/sso.jar \
  'https://auth.o1-1.xct258.top/api/auth/verify?service=taskops'        # 204
```

## 从旧版本迁移

新版本不再兼容旧的全局密码 / 全局 `APP_SECRET` / `sso_session`。

迁移步骤：

1. 备份旧 `.env`
2. 部署新版本，初始化数据库和管理员
3. 登录 `/admin`，创建域名和服务
4. 为每个服务复制新的 `.env`，更新业务中间件
5. 逐个重启业务服务，用户重新登录

全部迁移完成后，旧环境变量可以删除。
