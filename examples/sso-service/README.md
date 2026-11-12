# 新服务接入统一登录（模板）

每个服务独立密码和 Cookie；业务服务不保存签名密钥，统一交给 auth-server 验签。

```text
examples/sso-service/
  auth.py           # FastAPI 集中验签中间件
  frontend-auth.js  # 前端登录检查 / 401 跳转 / 退出
  .env.example      # 新服务环境变量
```

## 1. 在管理界面创建服务

打开：

```text
https://auth.xct258.top/admin
```

进入「接入管理」→「添加服务」，填写：

```text
所属域名:   xct258
服务名称:   TaskOps
服务 ID:    taskops
公开地址:   https://2-cfyx.o1-1.xct258.top
登录密码:   留空自动生成
会话天数:   7
```

如果上游服务自带 Basic Auth，勾选「上游使用 Basic Auth」，填写用户名/密码。生成的 NPM 配置会自动注入 `Authorization: Basic ...`。

保存后复制：

```text
服务密码
Cookie 名：sso_taskops
```

## 2. 环境变量

```bash
cp .env.example .env
```

```dotenv
AUTH_ENABLED=true
SERVICE_ID=taskops
SSO_VERIFY_URL=http://127.0.0.1:8290/api/auth/verify
SSO_LOGIN_URL=https://auth.xct258.top/login
SSO_COOKIE_NAME=sso_taskops
SSO_COOKIE_DOMAIN=.xct258.top
```

不需要 `SERVICE_SECRET`，也不需要 `SERVICE_TOKEN_VERSION`。

## 3. 后端接入（FastAPI）

```python
import auth

app.add_middleware(auth.AuthMiddleware)
app.include_router(auth.router)
```

按新服务调整 `auth.py` 顶部常量：

```python
PUBLIC_PATHS = {
    "/api/auth/status",
    "/api/auth/logout",
    "/api/health",
}

# Webhook / 回调等公开接口
PUBLIC_API_PATHS = {"/api/webhook"}

# 未登录返回 401 而不是 302 的路径
API_PATHS = set()
API_PREFIXES = ("/api/",)

# 静态资源必须放行
PUBLIC_STATIC_PATHS = {"/favicon.ico", "/favicon.svg"}
PUBLIC_STATIC_PREFIXES = ("/assets/",)
```

行为：

```text
GET  /                 未登录 → 302 /login?service=taskops&next=...
GET  /api/private      未登录 → 401
GET  /api/health       永远公开
GET  /assets/app.js    永远公开
```

## 4. 前端接入

```js
import { requireLogin, authFetch, logout } from './frontend-auth'

await requireLogin()
const res = await authFetch('/api/todos')
await logout()
```

如果不用封装，至少处理 401：

```js
if (res.status === 401) {
  location.href = `${loginUrl}?service=taskops&next=${encodeURIComponent(location.href)}`
}
```

## 5. 验签流程

```text
浏览器 → 业务服务
          ↓ 带着 sso_taskops Cookie
       auth-server /api/auth/verify?service=taskops
          ↓ 204 / 401
       业务服务放行或跳登录
```

auth-server 每次都会检查：

- Token 签名
- Token 版本
- 服务是否启用
- 是否过期

管理后台点「下线」，下一次请求就会失效。

## 6. NPM 无代码接入

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
    return 302 https://auth.xct258.top/login?service=taskops&next=https://$host$request_uri;
}
```

如果上游服务自带 Basic Auth，在 NPM 配置里加：

```nginx
proxy_set_header Authorization "Basic ...";
```

管理界面会直接生成这一行。

## 7. 验证

```bash
# 未登录页面：302
curl -i http://127.0.0.1:9000/

# 公开接口：200
curl -i http://127.0.0.1:9000/api/health

# 受保护接口：401
curl -i http://127.0.0.1:9000/api/private

# 登录后带 Cookie：200
curl -i -b /tmp/sso.jar http://127.0.0.1:9000/api/private
```

## 8. 注意

- 每个服务使用不同的 `SSO_COOKIE_NAME`。
- 业务服务不保存 `SERVICE_SECRET`。
- auth-server 不可用时，业务服务会拒绝登录；这是集中验签的代价。
- 如果服务在 Docker bridge 网络，`SSO_VERIFY_URL` 改成 `http://host.docker.internal:8290/api/auth/verify`。
- 生产必须 HTTPS，并让 NPM 传 `X-Forwarded-Proto: https`。
- Cookie 是 HttpOnly，前端读不到，登录状态只看 `/api/auth/status`。
