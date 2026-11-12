# 新服务接入统一登录（模板）

每个服务独立密码、Cookie、签名密钥；登录 A 不会登录 B。

```text
examples/sso-service/
  auth.py           # FastAPI 鉴权中间件，复制到新服务根目录
  frontend-auth.js  # 前端登录检查 / 401 跳转 / 退出
  .env.example      # 新服务环境变量
```

## 1. 在管理界面创建服务

打开：

```text
https://auth.xct258.top/admin
```

进入「服务管理」→「添加服务」，填写：

```text
所属域名:   o1-1
服务名称:   TaskOps
服务 ID:    taskops
公开地址:   https://2-cfyx.o1-1.xct258.top
登录密码:   留空自动生成
会话天数:   7
```

保存后复制：

```text
服务密码
SERVICE_SECRET
SERVICE_TOKEN_VERSION
Cookie 名：sso_taskops
```

## 2. 环境变量

```bash
cp .env.example .env
```

填入管理界面生成的值：

```dotenv
AUTH_ENABLED=true
SERVICE_ID=taskops
SERVICE_SECRET=...
SERVICE_TOKEN_VERSION=1
SSO_STATE_URL=http://127.0.0.1:8290/api/auth/service
SSO_LOGIN_URL=https://auth.xct258.top/login
SSO_COOKIE_NAME=sso_taskops
SSO_COOKIE_DOMAIN=.xct258.top
```

新服务不需要 `APP_PASSWORD`。

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

## 5. Token 格式

```text
Cookie: sso_<服务ID>

Token: v1.<service_id>.<token_version>.<expires>.<signature>

signature = HMAC-SHA256(
  SERVICE_SECRET,
  "v1.<service_id>.<token_version>.<expires>"
)
```

校验：

1. `service_id` 等于自己的 `SERVICE_ID`
2. `token_version` 等于 auth-server 当前值（每次访问时读取一次 `/api/auth/service/<slug>`）
3. HMAC 签名正确
4. 未过期

`auth.py` 已经实现，其他语言照抄逻辑即可。

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

如果服务自带 Basic Auth，在 SSO 通过后追加：

```nginx
proxy_set_header Authorization "Basic <base64(user:password)>";
```

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

- 每个服务使用不同的 `SSO_COOKIE_NAME`，否则会互相覆盖。
- `SERVICE_SECRET` 不能混用；不同服务必须不同。
- 管理界面「强制下线」后，业务服务在下一次访问时失效，不需要改环境变量。
- 「轮换密钥」会更换 `SERVICE_SECRET`，仍需要更新服务环境变量并重启。
- NPM `auth_request` 模式强制下线立即生效。
- 生产必须 HTTPS，并让 NPM 传 `X-Forwarded-Proto: https`。
- Cookie 是 HttpOnly，前端读不到，登录状态只看 `/api/auth/status`。
