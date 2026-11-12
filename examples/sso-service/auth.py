"""通用 SSO 接入模板（FastAPI）。

复制到新服务后只需要改三处：

1. 环境变量（见同目录 .env.example）
2. main.py 里注册中间件和路由：
       import auth
       app.add_middleware(auth.AuthMiddleware)
       app.include_router(auth.router)
3. 按服务实际情况调整下面的 PUBLIC_* / API_* 常量

鉴权规则：
    - 未登录访问页面        -> 302 到 auth-server 的 /login?next=原地址
    - 未登录访问 /api/*     -> 401 JSON，由前端跳登录中心
    - 公开路径 / 静态资源    -> 直接放行
    - Cookie 由 auth-server 写入父域，业务服务只验签，不需要请求 auth-server

依赖：fastapi、starlette（FastAPI 自带）。
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

# ------------------------------------------------------------
# 配置
# ------------------------------------------------------------
APP_SECRET = os.environ.get("APP_SECRET", "")
COOKIE_NAME = os.environ.get("SSO_COOKIE_NAME", "sso_session")
COOKIE_DOMAIN = os.environ.get("SSO_COOKIE_DOMAIN", "").strip()
SSO_LOGIN_URL = os.environ.get("SSO_LOGIN_URL", "").strip()
AUTH_ENABLED_RAW = os.environ.get("AUTH_ENABLED", "").strip().lower()

# 始终公开：登录状态、退出登录、健康检查。
PUBLIC_PATHS = {
    "/api/auth/status",
    "/api/auth/logout",
    "/api/health",
}
# 需要按服务补充的公开 API（精确匹配），例如回调、Webhook。
PUBLIC_API_PATHS: set[str] = set()
# 需要按服务补充的公开 API 前缀，例如 ("/api/public/",)。
PUBLIC_API_PREFIXES: tuple[str, ...] = ()
# SPA 静态资源必须公开，否则未登录时页面脚本加载不出来。
PUBLIC_STATIC_PATHS = {"/favicon.ico", "/favicon.svg"}
PUBLIC_STATIC_PREFIXES = ("/assets/",)

# 这些路径未登录时返回 401 JSON，而不是 302；按服务补充。
API_PATHS: set[str] = set()
API_PREFIXES = ("/api/",)

router = APIRouter(prefix="/api/auth", tags=["auth"])
logger = logging.getLogger(__name__)


# ------------------------------------------------------------
# 会话校验
# ------------------------------------------------------------
def auth_enabled() -> bool:
    """AUTH_ENABLED 显式配置优先；未配置时只要配了 SSO_LOGIN_URL 就启用。"""
    if AUTH_ENABLED_RAW in ("1", "true", "yes", "on"):
        return True
    if AUTH_ENABLED_RAW in ("0", "false", "no", "off"):
        return False
    return bool(SSO_LOGIN_URL)


def _secret() -> bytes:
    return APP_SECRET.encode("utf-8")


def _sign(payload: str) -> str:
    return hmac.new(_secret(), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_token(token: str | None) -> bool:
    """校验 auth-server 签发的会话：v1.<expires>.<hmac-sha256>。"""
    if not APP_SECRET or not token:
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


# ------------------------------------------------------------
# 跳转
# ------------------------------------------------------------
def _original_url(request: Request) -> str:
    """还原浏览器地址，兼容 NPM/nginx 的 X-Forwarded-*。"""
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
        f"{SSO_LOGIN_URL}{sep}next={quote(target, safe='')}",
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


# ------------------------------------------------------------
# 中间件
# ------------------------------------------------------------
class AuthMiddleware(BaseHTTPMiddleware):
    """统一登录：页面跳登录中心，API 返回 401。"""

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


# ------------------------------------------------------------
# 状态 / 退出接口
# ------------------------------------------------------------
@router.get("/status")
def auth_status(request: Request):
    return {
        "enabled": auth_enabled(),
        "authenticated": is_authenticated(request),
        "login_url": SSO_LOGIN_URL,
    }


@router.post("/logout")
def auth_logout():
    response = JSONResponse({"ok": True})
    response.delete_cookie(COOKIE_NAME, path="/", domain=COOKIE_DOMAIN or None)
    return response


if auth_enabled() and not APP_SECRET:
    logger.warning(
        "已启用 SSO，但 APP_SECRET 为空：所有会话都会校验失败。"
        "请配置与 auth-server 相同的 APP_SECRET。"
    )
