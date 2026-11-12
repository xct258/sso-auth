# 统一登录中心（SSO）

一个独立的登录页面 + 会话签发服务，给 `push-server`、`web-TaskOps` 等同一父域下的服务共用。

登录一次后，Cookie 写到父域（如 `.o1-1.xct258.top`），所有子域自动带上，业务服务只负责校验签名，不再各自弹登录框。

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

## 模板结构

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

另外两个业务的 Proxy Host **不需要改转发规则**，只要在它们的环境变量里加上 SSO 配置即可。

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

**业务服务 `push-server` / `web-TaskOps`**（不再需要访问密码，也不再提供本地登录页）：

```dotenv
AUTH_ENABLED=true
APP_SECRET=和登录中心完全相同          # 只用于验签
SSO_LOGIN_URL=https://auth.o1-1.xct258.top/login
SSO_COOKIE_NAME=sso_session
SSO_COOKIE_DOMAIN=.o1-1.xct258.top
```

> 业务服务必须显式配置 `APP_SECRET`。它们不再持有 `APP_PASSWORD`，所以没有“由密码派生密钥”的兜底路径。
> 修改 `APP_SECRET` 会让所有已登录会话立即失效，可用于强制全员下线。

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

**业务服务直连端口还能绕过登录**

`network_mode: host` 的端口只应让本机/NPM 访问。公网只放行 80/443，用防火墙或安全组挡住 8281/8383/8290。
