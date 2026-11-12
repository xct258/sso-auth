"""通用 SSO 接入模板（FastAPI，云端集中验签）。

每个受保护请求都带着浏览器 Cookie 调用 auth-server：

    GET {SSO_VERIFY_URL}?service=<SERVICE_ID>

auth-server 返回 204 放行，401 拒绝。业务服务不需要 SERVICE_SECRET。

复制到新服务后：
1. 在 auth-server 管理界面创建服务，复制环境变量
2. main.py 里注册中间件和路由：
       import auth
       app.add_middleware(auth.AuthMiddleware)
       app.include_router(auth.router)
3. 按服务调整 PUBLIC_* / API_* 常量

环境变量：
    AUTH_ENABLED          true/false；默认 true
    SERVICE_ID            服务 ID，例如 taskops
    SSO_VERIFY_URL        auth-server 验签地址
    SSO_LOGIN_URL         登录页地址
    SSO_COOKIE_NAME       该服务的 Cookie 名
    SSO_COOKIE_DOMAIN     父域，退出登录时清 Cookie
"""

from __future__ import annotations

import os
import urllib.error
import urllib.request
from urllib.parse import quote

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware

SERVICE_ID = os.environ.get("SERVICE_ID", "").strip()
COOKIE_NAME = os.environ.get("SSO_COOKIE_NAME", "").strip()
COOKIE_DOMAIN = os.environ.get("SSO_COOKIE_DOMAIN", "").strip()
SSO_LOGIN_URL = os.environ.get("SSO_LOGIN_URL", "").strip()
SSO_VERIFY_URL = os.environ.get(
    "SSO_VERIFY_URL", "https://auth.xct258.top/api/auth/verify"
).rstrip("/")
AUTH_ENABLED_RAW = os.environ.get("AUTH_ENABLED", "true").strip().lower()

PUBLIC_PATHS = {
    "/api/auth/status",
    "/api/auth/logout",
    "/api/health",
}
PUBLIC_API_PATHS: set[str] = set()
PUBLIC_API_PREFIXES: tuple[str, ...] = ()
PUBLIC_STATIC_PATHS = {"/favicon.ico", "/favicon.svg"}
PUBLIC_STATIC_PREFIXES = ("/assets/",)

API_PATHS: set[str] = set()
API_PREFIXES = ("/api/",)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def auth_enabled() -> bool:
    if AUTH_ENABLED_RAW in ("1", "true", "yes", "on"):
        return True
    if AUTH_ENABLED_RAW in ("0", "false", "no", "off"):
        return False
    return bool(SERVICE_ID and SSO_LOGIN_URL)


def _auth_server_verify(request: Request) -> bool:
    if not SERVICE_ID or not COOKIE_NAME:
        return False
    cookie = request.headers.get("cookie", "")
    if not cookie:
        return False
    url = f"{SSO_VERIFY_URL}?service={quote(SERVICE_ID, safe='')}"
    req = urllib.request.Request(
        url, headers={"Cookie": cookie, "User-Agent": "Mozilla/5.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=2.0) as response:
            return 200 <= response.status < 300
    except urllib.error.HTTPError as exc:
        return exc.code in (204, 304)
    except Exception:
        return False


def is_authenticated(request: Request) -> bool:
    return (not auth_enabled()) or _auth_server_verify(request)


def _original_url(request: Request) -> str:
    proto = request.headers.get("x-forwarded-proto", "").split(",")[0].strip()
    proto = proto or request.url.scheme
    host = (
        request.headers.get("x-forwarded-host")
        or request.headers.get("host")
        or request.url.netloc
    )
    url = f"{proto}://{host}{request.url.path}"
    if request.url.query:
        url += f"?{request.url.query}"
    return url


def login_url() -> str:
    if not SSO_LOGIN_URL:
        return ""
    sep = "&" if "?" in SSO_LOGIN_URL else "?"
    return f"{SSO_LOGIN_URL}{sep}service={quote(SERVICE_ID)}"


def redirect_to_login(request: Request) -> RedirectResponse | JSONResponse:
    base = login_url()
    if not base:
        return JSONResponse(
            {"detail": "未登录，且未配置 SSO_LOGIN_URL"}, status_code=401
        )
    target = _original_url(request)
    sep = "&" if "?" in base else "?"
    return RedirectResponse(
        f"{base}{sep}next={quote(target, safe='')}",
        status_code=302,
    )


def _is_api(path: str) -> bool:
    return path in API_PATHS or path.startswith(API_PREFIXES)


def _is_public(path: str) -> bool:
    return (
        path in PUBLIC_PATHS
        or path in PUBLIC_API_PATHS
        or path in PUBLIC_STATIC_PATHS
        or path.startswith(PUBLIC_API_PREFIXES)
        or path.startswith(PUBLIC_STATIC_PREFIXES)
    )


class AuthMiddleware(BaseHTTPMiddleware):
    """未登录页面跳登录中心；/api/* 返回 401。"""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if (
            not auth_enabled()
            or request.method == "OPTIONS"
            or _is_public(path)
            or is_authenticated(request)
        ):
            return await call_next(request)

        if _is_api(path):
            return JSONResponse({"detail": "未登录或登录已过期"}, status_code=401)
        return redirect_to_login(request)


@router.get("/status")
def auth_status(request: Request):
    return {
        "enabled": auth_enabled(),
        "authenticated": is_authenticated(request),
        "service": SERVICE_ID,
        "login_url": login_url(),
    }


@router.post("/logout")
def auth_logout():
    response = JSONResponse({"ok": True})
    response.delete_cookie(COOKIE_NAME, path="/", domain=COOKIE_DOMAIN or None)
    return response
