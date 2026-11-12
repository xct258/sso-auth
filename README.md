# 统一登录中心（SSO）

一个独立的登录页面 + 会话签发服务，给 `push-server`、`web-TaskOps` 以及后续新增的同父域服务共用。

登录一次后，Cookie 写到父域（如 `.o1-1.xct258.top`），所有子域自动带上，业务服务只负责校验签名，不再各自弹登录框。新增服务不需要修改 auth-server 代码。

## 架构

```
                        ┌─ push-server.o1-1.xct258.top ─→ 127.0.0.1:8383
浏览器 ─→ NPM/nginx ────┤
                        ├─ 2-cfyx.o1-1.xct258.top ─────→ 127.0.0.1:8281
                        └─ auth.o1-1.xct258.top ──────→ 127.0.0.1:8290
                                   │
                                   └─ 登录成功写 Cookie: sso_session
                                      Domain=.o1-1.xct258.top
```

- 未登录访问任意业务页面 → 302 到 `https://auth.o1-1.xct258.top/login?next=<原地址>`
- 登录成功 → 写共享 Cookie → 跳回 `next`
- 业务服务的 `/api/*` 未登录仍返回 401，前端据此跳到登录中心（不会把 HTML 当 JSON）
- 退出登录 → 清除父域 Cookie，所有服务同时退出
- 新服务只要在同一父域下，复用同一个 Cookie 和 `APP_SECRET` 即可，不需要修改登录中心

## 快速部署

镜像由 GitHub Actions 按 `install/app.conf` 构建并推送 Docker Hub：

- 仓库 Actions → **Build and Push Docker Image** → Run workflow
- 需要 Secrets：`DOCKERACC` / `DOCKERPWD`
- 镜像：`xct258/sso-auth:latest`

服务器上：

```bash
cd auth-server
cp .env.example .env
# 修改 .env：APP_PASSWORD、APP_SECRET、SSO_COOKIE_DOMAIN、SSO_LOGIN_URL 等
docker compose up -d
curl http://127.0.0.1:8290/api/health
```

容器启动时：

1. `template/start.sh` 执行 `startup/prepare.sh`
2. 把镜像里 `/opt/sso-auth` 的 `main.py`、`static/dist` 同步到 `/data`
3. `startup/services.sh` 启动 `uvicorn main:app --app-dir /data --port 8290`
4. 日志写入 `/data/logs`，服务日志在 `/data/logs/service/api.log`

直接用 Python 跑（开发调试）：

```bash
pip install -r requirements.txt
APP_PASSWORD=test APP_SECRET=dev-secret \
SSO_COOKIE_DOMAIN=.o1-1.xct258.top \
SSO_LOGIN_URL=http://127.0.0.1:8290/login \
SSO_ALLOWED_REDIRECT_SUFFIX=.o1-1.xct258.top \
SSO_PUBLIC_HOST=127.0.0.1 \
uvicorn main:app --host 0.0.0.0 --port 8290
```

## Docker 镜像结构（docker-image-template）

与 `xct258/docker-image-template` 一致：

```text
check.sh
docker-compose.yml
.github/workflows/build-image.yml
install/
  app.conf
  install.sh
  custom-install.sh
startup/
  main.sh
  once.sh
  prepare.sh
  services.sh
  update.sh
template/
  Dockerfile
  start.sh
  supervisor.sh
```

- `install/app.conf`：镜像名、架构、apt/pip 依赖
- `install/custom-install.sh`：下载当前提交源码，下载 Node 构建 `前端/`，产物放到 `/opt/sso-auth/static/dist`
- `startup/prepare.sh`：每次启动把应用和前端同步到 `/data`
- `startup/services.sh`：声明 `uvicorn` 服务
- `template/`：固定模板，不修改
- `check.sh`：构建前校验，CI 会先执行
- `examples/sso-service/`：新服务接入模板，不参与镜像构建

## 登录页（Vue 3 + Vite）

登录页源码在 `前端/`，构建产物输出到 `static/dist/`，由 FastAPI 直接托管；运行镜像不需要 Node。

```bash
cd 前端
npm install
npm run dev      # http://127.0.0.1:5182，/api 自动反代到 8290
npm run build    # 输出到 ../static/dist
```

镜像构建阶段由 `install/custom-install.sh` 自动完成前端构建。

- `static/dist/index.html` 存在时，`/` 和 `/login` 返回 Vue 页面；
- 没有构建产物时，回退到单文件 `static/login.html`；
- 当前登录页为居中卡片 + 清晰壁纸 + TaskOps 风格加载页；
- 密码使用页面内自定义安全键盘，不调用原生输入框，支持光标定位、粘贴、双击全选和横向滚动。

## NPM（Nginx Proxy Manager）配置

新增一个 Proxy Host：

| 字段 | 值 |
| --- | --- |
| Domain Names | `auth.o1-1.xct258.top` |
| Scheme | `http` |
| Forward Hostname / IP | `127.0.0.1`（NPM 用 host 网络时）或 `host.docker.internal` |
| Forward Port | `8290` |
| Websockets Support | 开（可选） |
| SSL | 申请 Let's Encrypt 并开启 Force SSL |

现有业务和新服务的 Proxy Host **不需要改转发规则**，只要在它们的环境变量里加上 SSO 配置即可。

> 关键：NPM 必须把 `X-Forwarded-Proto` 传给后端（NPM 默认会传）。否则 Cookie 的 `Secure` 判断会出错。

## 配置分工

**登录中心 `auth-server/.env`**：

```dotenv
APP_PASSWORD=访问密码
APP_SECRET=随机长字符串               # openssl rand -hex 32
SSO_SESSION_DAYS=7
SSO_COOKIE_NAME=sso_session
SSO_COOKIE_DOMAIN=.o1-1.xct258.top    # 注意前面的点
SSO_LOGIN_URL=https://auth.o1-1.xct258.top/login
SSO_ALLOWED_REDIRECT_SUFFIX=.o1-1.xct258.top
SSO_PUBLIC_HOST=auth.o1-1.xct258.top
SSO_DEFAULT_REDIRECT=
```

**业务服务（`push-server` / `web-TaskOps` / 新服务）**（不再需要访问密码，也不再提供本地登录页）：

```dotenv
AUTH_ENABLED=true
APP_SECRET=和登录中心完全相同          # 只用于验签
SSO_LOGIN_URL=https://auth.o1-1.xct258.top/login
SSO_COOKIE_NAME=sso_session
SSO_COOKIE_DOMAIN=.o1-1.xct258.top
```

> 业务服务必须显式配置 `APP_SECRET`。它们不再持有 `APP_PASSWORD`，所以没有“由密码派生密钥”的兜底路径。
> 修改 `APP_SECRET` 会让所有已登录会话立即失效，可用于强制全员下线。

## 新服务接入

任何和 auth-server 在同一父域下的新服务都可以接入，**不需要修改 auth-server 代码**。

完整可复制模板在 [`examples/sso-service/`](examples/sso-service/)：

| 文件 | 用途 |
| --- | --- |
| `auth.py` | FastAPI 鉴权中间件，复制到新服务根目录 |
| `frontend-auth.js` | 前端登录检查、401 跳转、退出登录 |
| `.env.example` | 新服务环境变量 |
| `README.md` | 模板的详细使用说明 |

### 1. 域名与反代

新服务使用同一父域下的子域，例如：

```text
new-service.o1-1.xct258.top → 127.0.0.1:9000
```

在 NPM 新增一个 Proxy Host 指向新服务端口即可。

- 同一父域：自动被 `SSO_ALLOWED_REDIRECT_SUFFIX=.o1-1.xct258.top` 覆盖，登录中心不用改。
- 换到其他父域：需要同时修改 `SSO_COOKIE_DOMAIN` 和 `SSO_ALLOWED_REDIRECT_SUFFIX`；当前实现只支持一个后缀。
- 生产必须 HTTPS，并确保 NPM 传入 `X-Forwarded-Proto: https`，否则 `Secure` Cookie 不生效。

### 2. 新服务环境变量

```dotenv
AUTH_ENABLED=true
APP_SECRET=和 auth-server 完全相同
SSO_LOGIN_URL=https://auth.o1-1.xct258.top/login
SSO_COOKIE_NAME=sso_session
SSO_COOKIE_DOMAIN=.o1-1.xct258.top
```

- 新服务**不需要配置 `APP_PASSWORD`**，密码只在 auth-server。
- `APP_SECRET` 必须和 auth-server 完全一致，否则表现为“登录后又跳回登录页”。
- 本机用 `127.0.0.1:端口` 调试时，`SSO_COOKIE_DOMAIN` 留空即可；同一主机的不同端口共享 Cookie。

### 3. 复制鉴权模板

```bash
cp examples/sso-service/auth.py 新服务/auth.py
cp examples/sso-service/frontend-auth.js 新服务/前端/src/auth.js
```

`auth.py` 默认公开以下路径：

```text
/api/auth/status
/api/auth/logout
/api/health
/assets/*
/favicon.ico
/favicon.svg
```

按新服务的实际情况修改文件顶部的常量：

```python
# 回调 / Webhook 等不需要浏览器登录的接口
PUBLIC_API_PATHS = {"/api/webhook"}
PUBLIC_API_PREFIXES = ()

# 未登录时返回 401 JSON 而不是 302 的路径
API_PATHS = set()
API_PREFIXES = ("/api/",)

# SPA 静态资源
PUBLIC_STATIC_PATHS = {"/favicon.ico", "/favicon.svg"}
PUBLIC_STATIC_PREFIXES = ("/assets/",)
```

> 如果是纯 API 服务，把 `API_PREFIXES` 配全即可，不需要页面跳转。
> 如果有 WebSocket，需要在 WebSocket 握手处单独校验 Cookie，或在 NPM 层放行对应路径。

### 4. 注册中间件

在 `main.py` 里加两行：

```python
import auth

app.add_middleware(auth.AuthMiddleware)
app.include_router(auth.router)
```

接入后行为：

| 请求 | 未登录时 |
| --- | --- |
| 页面（如 `/`、`/todos`） | `302` 到 `auth-server/login?next=原地址` |
| `/api/*` | `401 {"detail":"未登录或登录已过期"}` |
| `/api/health` | 正常放行 |
| `/assets/*` | 正常放行 |

业务服务只做本地验签，不会在每次请求时访问 auth-server。

### 5. 前端接入

应用启动时检查登录状态：

```js
import { requireLogin, authFetch, logout } from './auth'

await requireLogin()                  // 未登录会直接跳登录中心
const res = await authFetch('/api/todos')  // 401 自动跳登录中心
await logout()                        // 清除父域 Cookie
```

如果不用封装，至少处理 401：

```js
if (res.status === 401) {
  location.href = `${loginUrl}?next=${encodeURIComponent(location.href)}`
}
```

不要在前端读取 Cookie：`sso_session` 是 `HttpOnly`，登录状态以 `/api/auth/status` 为准。

### 6. 非 Python 服务

Cookie 的签名格式是固定的：

```text
sso_session = v1.<expires>.<signature>

signature = hex( HMAC-SHA256(APP_SECRET, "v1." + expires) )
expires   = Unix 秒级时间戳
```

校验步骤：

1. 按 `.` 拆成三段；
2. 第一段必须是 `v1`；
3. 用 `APP_SECRET` 对 `v1.<expires>` 做 HMAC-SHA256；
4. 常量时间比较签名；
5. `expires` 大于当前时间。

可以直接参考 `examples/sso-service/auth.py` 里的 `_sign()` 和 `verify_token()`。

### 7. 接入检查清单

```bash
# 未登录页面：302
curl -i http://127.0.0.1:9000/

# 公开接口：200
curl -i http://127.0.0.1:9000/api/health

# 受保护接口：401
curl -i http://127.0.0.1:9000/api/private

# 登录拿到 Cookie 后：200
curl -i -b /tmp/sso.jar http://127.0.0.1:9000/api/private
```

浏览器端：

1. 打开新服务 → 跳到 auth 登录页；
2. 登录成功 → 回到新服务；
3. 再打开 push-server / TaskOps → 不再要求登录；
4. 在任意服务退出 → 所有服务同时退出；
5. 刷新新服务，静态资源不能出现 401。

## 验证

```bash
# 1. 登录并保存 Cookie
curl -i -c /tmp/sso.jar \
  -H 'Content-Type: application/json' \
  -d '{"password":"你的密码"}' \
  'http://127.0.0.1:8290/api/auth/login?next=https%3A%2F%2Fpush-server.o1-1.xct258.top%2F'

# 2. 应看到 Set-Cookie: sso_session=...; Domain=.o1-1.xct258.top; HttpOnly
# 3. 带 Cookie 校验
curl -i -b /tmp/sso.jar http://127.0.0.1:8290/api/auth/verify   # 204
curl -i http://127.0.0.1:8290/api/auth/verify                  # 401
```

浏览器端：先打开 `https://2-cfyx.o1-1.xct258.top`（TaskOps 当前的隧道域名，换成你的实际域名也可以），应跳到 `auth.../login?next=...`；登录后回到 TaskOps；再打开 `https://push-server.o1-1.xct258.top`，应直接进入，不再要求登录。

## 可选：nginx 层再兜一道（auth_request）

业务服务自身已经会校验 Cookie，下面的配置是“网关级”兜底，适合以后接入更多服务。放在 NPM 对应 Proxy Host 的 **Advanced** 里：

```nginx
location = /_sso_auth {
    internal;
    proxy_pass http://127.0.0.1:8290/api/auth/verify;
    proxy_pass_request_body off;
    proxy_set_header Content-Length "";
    proxy_set_header X-Original-URI $request_uri;
}

location / {
    auth_request /_sso_auth;
    auth_request_set $sso_user $upstream_http_x_auth_user;

    error_page 401 = @sso_login;

    proxy_set_header X-Auth-User $sso_user;
    # NPM 原有的 proxy_pass 等配置保留
}

location @sso_login {
    return 302 https://auth.o1-1.xct258.top/login?next=$scheme://$host$request_uri;
}
```

注意：

- `/api/push`、`/api/task*` 这类服务间回调要放行，否则会被拦。
- `/api/*` 建议不要走 `auth_request`，让业务返回 401 JSON，避免前端拿到 302 后的 HTML。
- 如果 NPM 和后端不在同一个网络，`proxy_pass` 里用 `host.docker.internal:8290`。

## 安全说明

- 生产必须走 HTTPS；`Secure` Cookie 依赖 `X-Forwarded-Proto: https`。
- `SSO_COOKIE_DOMAIN` 覆盖整个父域，任何子域都能收到这个 Cookie。只把你信任的服务放在该父域下。
- `next` 只允许跳到 `SSO_ALLOWED_REDIRECT_SUFFIX` 指定的后缀，避免开放重定向。
- 登录接口有 5 次/60 秒的 IP 限流；公网部署建议再在 NPM 加 `limit_req`。
- 修改 `APP_SECRET` 会让所有已登录会话立即失效，这是预期的“强制下线”手段。

## 常见问题

**登录成功后又跳回登录页**

1. 登录中心和业务服务的 `APP_SECRET` 不一致；
2. `SSO_COOKIE_DOMAIN` 写错（必须是 `.o1-1.xct258.top` 这种父域，且服务都在该域下）；
3. 站点不是 HTTPS，或 NPM 没传 `X-Forwarded-Proto`，导致浏览器拒收 `Secure` Cookie；
4. 浏览器里残留了旧的 `push_session` / `taskops_session`，清一下即可。

**页面一直 302 循环**

检查 `SSO_PUBLIC_HOST` 是否等于登录中心自己的域名；登录中心不会把 `next` 指回自己。

**新服务登录后又跳回登录页**

优先检查新服务的 `APP_SECRET` 是否和 auth-server 完全一致；其次检查 `SSO_COOKIE_DOMAIN` 是否写成 `.父域`，以及新服务域名是否真的在该父域下。浏览器里残留旧 Cookie 也会造成类似现象。

**新服务登录页白屏或静态资源 401**

`auth.py` 里的 `PUBLIC_STATIC_PREFIXES` 必须放行 SPA 的静态资源目录，默认是 `("/assets/",)`；如果构建产物放在别的目录，按实际路径补充。

**新服务接口拿到的是登录页 HTML**

说明 API 路径没有被识别成 API，未登录时走了 302。把该路径加到 `API_PATHS`，或把前缀加到 `API_PREFIXES`。

**业务服务直连端口还能绕过登录**

`network_mode: host` 的端口只应让本机/NPM 访问。公网只放行 80/443，用防火墙或安全组挡住 8281/8383/8290。
