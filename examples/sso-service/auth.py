"""通用 SSO 接入模板（FastAPI，多服务版）。

每个服务独立密码、Cookie、签名密钥；登录 A 不会登录 B。

复制到新服务后：
1. 在 auth-server 管理界面创建服务，拿到环境变量
2. main.py 里注册中间件和路由：
       import auth
       app.add_middleware(auth.AuthMiddleware)
       app.include_router(auth.router)
3. 按服务调整 PUBLIC_* / API_* 常量

环境变量：
    AUTH_ENABLED             true/false；默认 true
    SERVICE_ID               管理界面里的服务 ID，例如 taskops
    SERVICE_SECRET           该服务自己的签名密钥
    SERVICE_TOKEN_VERSION    该服务的 Token 版本，管理界面生成，默认 1
    SSO_LOGIN_URL            登录页地址，例如 https://auth.o1-1.xct258.top/login
    SSO_COOKIE_NAME          管理界面生成的 Cookie 名，例如 sso_taskops
    SSO_COOKIE_DOMAIN        父域，例如 .o1-1.xct258.top
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import time
from urllib.parse import quote

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware

APP_SECRET = os.environ.get("SERVICE_SECRET", "")
SERVICE_ID = os.environ.get("SERVICE_ID", "").strip()
TOKEN_VERSION = os.environ.get("SERVICE_TOKEN_VERSION", "1").strip()
COOKIE_NAME = os.environ.get("SSO_COOKIE_NAME", "").strip()
COOKIE_DOMAIN = os.environ.get("SSO_COOKIE_DOMAIN", "").strip()
SSO_LOGIN_URL = os.environ.get("SSO_LOGIN_URL", "").strip()
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
logger = logging.getLogger(__name__)


def auth_enabled() -> bool:
    if AUTH_ENABLED_RAW in ("1", "true", "yes", "on"):
        return True
    if AUTH_ENABLED_RAW in ("0", "false", "no", "off"):
        return False
    return bool(SERVICE_ID and APP_SECRET and SSO_LOGIN_URL)


def _secret() -> bytes:
    return APP_SECRET.encode("utf-8")


def _sign(payload: str) -> str:
    return hmac.new(_secret(), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_token(token: str | None) -> bool:
    """校验 auth-server 签发的服务 Token。"""
    if not SERVICE_ID or not APP_SECRET or not token:
        return False
    parts = token.split(".")
    if len(parts) != 5:
        return False
    version, service_id, token_version, expires, signature = parts
    if version != "v1" or service_id != SERVICE_ID:
        return False
    if token_version != TOKEN_VERSION:
        return False
    if not hmac.compare_digest(
        signature, _sign(f"v1.{service_id}.{token_version}.{expires}")
    ):
        return False
    try:
        return int(expires) > int(time.time())
    except ValueError:
        return False


def is_authenticated(request: Request) -> bool:
    return (not auth_enabled()) or verify_token(request.cookies.get(COOKIE_NAME))


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


def redirect_to_login(request: Request) -> RedirectResponse | JSONResponse:
    if not SSO_LOGIN_URL:
        return JSONResponse(
            {"detail": "未登录，且未配置 SSO_LOGIN_URL"}, status_code=401
        )
    target = _original_url(request)
    sep = "&" if "?" in SSO_LOGIN_URL else "?"
    return RedirectResponse(
        f"{SSO_LOGIN_URL}{sep}service={quote(SERVICE_ID)}"
        f"&next={quote(target, safe='')}",
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
        "login_url": SSO_LOGIN_URL,
    }


@router.post("/logout")
def auth_logout():
    response = JSONResponse({"ok": True})
    response.delete_cookie(COOKIE_NAME, path="/", domain=COOKIE_DOMAIN or None)
    return response


if auth_enabled() and (not SERVICE_ID or not APP_SECRET or not COOKIE_NAME):
    logger.warning(
        "已启用 SSO，但 SERVICE_ID / SERVICE_SECRET / SSO_COOKIE_NAME 有空值，"
        "所有会话都会校验失败。"
    )
