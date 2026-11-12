"""统一登录中心（SSO）。

职责：
    - 提供唯一的登录页面 /login
    - 校验访问密码，签发 HMAC 签名会话 Cookie
    - 供各业务服务共享登录态（Cookie 写到父域，见 SSO_COOKIE_DOMAIN）

接口：
    GET  /                      登录页（与 /login 相同）
    GET  /login                 登录页；已登录且带 next 时直接 302
    GET  /api/config            登录页用的站点配置（站点名 / 壁纸）
    GET  /api/auth/status       登录状态
    POST /api/auth/login        登录，写 Cookie
    POST /api/auth/logout       退出，清 Cookie
    GET  /api/auth/verify       给 nginx auth_request 用：204 放行 / 401 拒绝
    GET  /api/health            健康检查

Cookie / Token 约定（必须与业务服务保持一致）：
    Cookie 名：sso_session（SSO_COOKIE_NAME）
    Token 格式：v1.<过期时间戳>.<hmac_sha256(secret, "v1.<过期时间戳>")>
    签名密钥：APP_SECRET；未设置时由 "sso|" + 密码派生（所有服务必须一致）

环境变量：
    APP_PASSWORD                 访问密码；为空 = 不启用登录
    APP_SECRET                   会话签名密钥；三个服务必须相同
    SSO_SESSION_DAYS             会话有效天数，默认 7
    SSO_COOKIE_NAME              Cookie 名，默认 sso_session
    SSO_COOKIE_DOMAIN            父域，如 .o1-1.xct258.top；跨子域 SSO 必填
    SSO_LOGIN_URL                本服务的完整登录地址，如 https://auth.example.com/login
    SSO_ALLOWED_REDIRECT_SUFFIX  允许登录后跳转的域名后缀，如 .o1-1.xct258.top
    SSO_PUBLIC_HOST              登录中心自己的主机名，防止 next 跳回自己造成循环
    SSO_DEFAULT_REDIRECT         没有 next 时登录成功后去哪
    SSO_SITE_NAME                登录页标题
    SSO_WALLPAPER_URL            登录页背景图地址；留空则用纯渐变
    UVICORN_PORT                 监听端口，默认 8290
"""
import hashlib
import hmac
import os
import time
from typing import Dict, Tuple
from urllib.parse import quote, urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
LOGIN_PAGE = os.path.join(STATIC_DIR, "login.html")
# Vite 构建产物；存在时优先使用 Vue 登录页，否则回退到单文件 login.html。
DIST_DIR = os.path.join(STATIC_DIR, "dist")
DIST_INDEX = os.path.join(DIST_DIR, "index.html")

PASSWORD = os.environ.get("APP_PASSWORD", "") or os.environ.get("SSO_PASSWORD", "")
SECRET_RAW = os.environ.get("APP_SECRET", "")
SESSION_MAX_AGE = int(
    os.environ.get("SSO_SESSION_DAYS") or os.environ.get("APP_SESSION_DAYS") or "7"
) * 86400
COOKIE_NAME = os.environ.get("SSO_COOKIE_NAME", "sso_session")
COOKIE_DOMAIN = os.environ.get("SSO_COOKIE_DOMAIN", "").strip()
# 没单独配置跳转白名单时，默认与 Cookie 父域一致；两者都为空则登录后不跳转。
ALLOWED_SUFFIX = (
    os.environ.get("SSO_ALLOWED_REDIRECT_SUFFIX", "").strip() or COOKIE_DOMAIN
).lower()
PUBLIC_HOST = os.environ.get("SSO_PUBLIC_HOST", "").strip().lower()
DEFAULT_REDIRECT = os.environ.get("SSO_DEFAULT_REDIRECT", "").strip()
SITE_NAME = os.environ.get("SSO_SITE_NAME", "统一登录")
WALLPAPER_URL = os.environ.get("SSO_WALLPAPER_URL", "").strip()

# 与 push-server / TaskOps 的 auth.py 完全一致：APP_SECRET 优先，否则 "sso|密码"。
SECRET = (
    SECRET_RAW
    or hashlib.sha256(f"sso|{PASSWORD}".encode("utf-8")).hexdigest()
).encode("utf-8")

MAX_FAILURES = 5
LOCK_SECONDS = 60
_failures: Dict[str, Tuple[int, float]] = {}

app = FastAPI(title="统一登录中心", docs_url=None, redoc_url=None)

# Vue 构建产物（/assets/*），没有构建时退回 static/login.html。
if os.path.isdir(os.path.join(DIST_DIR, "assets")):
    app.mount("/assets", StaticFiles(directory=os.path.join(DIST_DIR, "assets")), name="login-assets")


def auth_enabled() -> bool:
    return bool(PASSWORD)


def _sign(payload: str) -> str:
    return hmac.new(SECRET, payload.encode("utf-8"), hashlib.sha256).hexdigest()


def create_token() -> str:
    payload = f"v1.{int(time.time()) + SESSION_MAX_AGE}"
    return f"{payload}.{_sign(payload)}"


def verify_token(token: str | None) -> bool:
    if not token:
        return False
    try:
        version, expires, signature = token.split(".")
    except ValueError:
        return False
    if version != "v1":
        return False
    if not hmac.compare_digest(signature, _sign(f"v1.{expires}")):
        return False
    try:
        return int(expires) > int(time.time())
    except ValueError:
        return False


def is_authenticated(request: Request) -> bool:
    return (not auth_enabled()) or verify_token(request.cookies.get(COOKIE_NAME))


def _is_https(request: Request) -> bool:
    proto = request.headers.get("x-forwarded-proto", "").split(",")[0].strip().lower()
    return proto == "https" or request.url.scheme == "https"


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _safe_next(raw: str) -> str:
    """只允许跳到白名单后缀下的绝对地址，防开放重定向。"""
    raw = (raw or "").strip()
    if not raw:
        return ""
    parsed = urlsplit(raw)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return ""
    host = parsed.hostname.lower()
    if PUBLIC_HOST and host == PUBLIC_HOST:
        return ""
    if not ALLOWED_SUFFIX:
        return ""
    suffix = ALLOWED_SUFFIX.lstrip(".")
    if not (host == suffix or host.endswith("." + suffix)):
        return ""
    return raw


def _resolve_next(raw: str) -> str:
    return _safe_next(raw) or _safe_next(DEFAULT_REDIRECT)


def _set_session_cookie(response: JSONResponse, request: Request) -> JSONResponse:
    response.set_cookie(
        COOKIE_NAME,
        create_token(),
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=_is_https(request),
        domain=COOKIE_DOMAIN or None,
        path="/",
    )
    return response


@app.get("/", include_in_schema=False)
@app.get("/login", include_in_schema=False)
def login_page(request: Request, next: str = ""):
    if is_authenticated(request):
        target = _resolve_next(next)
        if target:
            return RedirectResponse(target, status_code=302)
    return FileResponse(
        DIST_INDEX if os.path.isfile(DIST_INDEX) else LOGIN_PAGE,
        media_type="text/html",
        headers={
            "Cache-Control": "no-store",
            "X-Frame-Options": "DENY",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
        },
    )


@app.get("/api/config")
def public_config():
    return {
        "enabled": auth_enabled(),
        "site_name": SITE_NAME,
        "wallpaper_url": WALLPAPER_URL,
    }


@app.get("/api/auth/status")
def auth_status(request: Request, next: str = ""):
    authenticated = is_authenticated(request)
    return {
        "enabled": auth_enabled(),
        "authenticated": authenticated,
        "redirect": _resolve_next(next) if authenticated else "",
        "login_url": os.environ.get("SSO_LOGIN_URL", ""),
    }


class LoginPayload(BaseModel):
    password: str = ""


@app.post("/api/auth/login")
def auth_login(payload: LoginPayload, request: Request, next: str = ""):
    if not auth_enabled():
        return {"ok": True, "enabled": False, "redirect": _resolve_next(next)}

    ip = _client_ip(request)
    now = time.time()
    count, locked_until = _failures.get(ip, (0, 0.0))
    if locked_until > now:
        raise HTTPException(status_code=429, detail="尝试次数过多，请稍后再试")

    if not hmac.compare_digest(payload.password.encode("utf-8"), PASSWORD.encode("utf-8")):
        count += 1
        if count >= MAX_FAILURES:
            _failures[ip] = (0, now + LOCK_SECONDS)
        else:
            _failures[ip] = (count, 0.0)
        raise HTTPException(status_code=401, detail="密码错误")

    _failures.pop(ip, None)
    return _set_session_cookie(
        JSONResponse({"ok": True, "enabled": True, "redirect": _resolve_next(next)}),
        request,
    )


@app.post("/api/auth/logout")
def auth_logout():
    response = JSONResponse({"ok": True})
    response.delete_cookie(COOKIE_NAME, path="/", domain=COOKIE_DOMAIN or None)
    return response


@app.get("/api/auth/verify")
def auth_verify(request: Request):
    """nginx auth_request 子请求：2xx 放行，401 拒绝。"""
    if is_authenticated(request):
        return Response(status_code=204, headers={"X-Auth-User": "sso"})
    return JSONResponse({"detail": "未登录或登录已过期"}, status_code=401)


@app.get("/api/health")
def health():
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.environ.get("UVICORN_PORT", "8290")),
    )
