# 新服务接入统一登录（模板）

把本目录复制到新服务，按下面几步改：

```text
examples/sso-service/
  auth.py           # FastAPI 鉴权中间件，复制到新服务根目录
  frontend-auth.js  # 前端登录检查 / 401 跳转 / 退出
  .env.example      # 新服务环境变量
```

## 1. 环境变量

```bash
cp .env.example .env
```

至少确认：

```dotenv
AUTH_ENABLED=true
APP_SECRET=与 auth-server 完全相同
SSO_LOGIN_URL=https://auth.o1-1.xct258.top/login
SSO_COOKIE_NAME=sso_session
SSO_COOKIE_DOMAIN=.o1-1.xct258.top
```

新服务不需要 `APP_PASSWORD`，密码只在 auth-server。

## 2. 后端接入（FastAPI）

```python
import auth

app.add_middleware(auth.AuthMiddleware)
app.include_router(auth.router)
```

然后按新服务调整 `auth.py` 顶部的常量：

```python
# 健康检查、登录状态、退出登录默认已包含
PUBLIC_PATHS = {
    "/api/auth/status",
    "/api/auth/logout",
    "/api/health",
}

# 服务间回调 / Webhook 等不需要浏览器登录的接口
PUBLIC_API_PATHS = {"/api/webhook"}

# 未登录时返回 401 而不是 302 的路径
API_PATHS = {"/records"}
API_PREFIXES = ("/api/",)

# 静态资源必须放行
PUBLIC_STATIC_PATHS = {"/favicon.ico", "/favicon.svg"}
PUBLIC_STATIC_PREFIXES = ("/assets/",)
```

接入后的行为：

```text
GET  /                 未登录 → 302 auth-server/login?next=...
GET  /api/private      未登录 → 401 {"detail":"未登录或登录已过期"}
GET  /api/health       永远公开
GET  /assets/app.js    永远公开
```

## 3. 前端接入

```js
import { requireLogin, authFetch, logout } from './frontend-auth'

// 应用启动时
await requireLogin()

// 所有需要登录的请求
const res = await authFetch('/api/todos')

// 退出
await logout()
```

如果不想用封装，至少处理 401：

```js
if (res.status === 401) {
  location.href = `${loginUrl}?next=${encodeURIComponent(location.href)}`
}
```

## 4. 非 Python 服务

Cookie 格式固定为：

```text
sso_session = v1.<expires>.<signature>

signature = hex( HMAC-SHA256(APP_SECRET, "v1." + expires) )
expires   = Unix 秒级时间戳
```

校验步骤：

1. 按 `.` 拆成三段
2. 第一段必须是 `v1`
3. 用 `APP_SECRET` 对 `v1.<expires>` 做 HMAC-SHA256
4. 常量时间比较签名
5. `expires` 必须大于当前时间

Python 模板的 `verify_token()`、`_sign()` 就是完整实现，可以直接照抄。

## 5. 验证

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

浏览器完整流程：

1. 打开新服务 → 跳转 auth 登录页
2. 登录成功 → 回到新服务
3. 再打开 push-server / TaskOps → 不再要求登录
4. 在任意服务退出 → 所有服务同时退出

## 6. 注意

- 新服务必须和 auth-server 在同一个父域下，Cookie 才能共享。
- `APP_SECRET` 必须完全一致；不一致会表现为“登录后又跳回登录页”。
- `SSO_COOKIE_DOMAIN` 要写成 `.父域`，前面有点。
- 本机用 `127.0.0.1:端口` 调试时，`SSO_COOKIE_DOMAIN` 留空即可。
- 生产必须 HTTPS，并让 NPM/nginx 传 `X-Forwarded-Proto: https`。
- 业务服务只验签，不需要每次请求 auth-server。
- Cookie 是 HttpOnly，前端读不到，登录状态只看 `/api/auth/status`。
