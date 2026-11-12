"""统一登录中心（多服务版）。

每个服务独立密码、独立 Cookie、独立签名密钥；同一个父域下共用一个
auth-server，但登录态互不影响。

主要接口：
    GET  /login?service=<slug>&next=<url>   服务登录页
    GET  /api/config?service=<slug>         登录页配置
    GET  /api/auth/status?service=<slug>    登录状态
    POST /api/auth/login?service=<slug>     登录，写该服务的 Cookie
    POST /api/auth/logout?service=<slug>    退出，只清该服务的 Cookie
    GET  /api/auth/verify?service=<slug>    nginx auth_request：204 / 401

管理接口：
    POST /api/admin/login
    GET  /api/admin/status
    POST /api/admin/logout
    GET  /api/admin/overview
    GET/POST/PUT/DELETE /api/admin/domains
    GET/POST/PUT/DELETE /api/admin/services
    POST /api/admin/services/{id}/reset-password
    POST /api/admin/services/{id}/revoke
    GET  /api/admin/services/{id}/config
    GET  /api/admin/audit
    POST /api/admin/change-password

环境变量：
    AUTH_HOST                    初始登录中心主机名，默认 auth.xct258.top
    AUTH_COOKIE_DOMAIN           初始 Cookie 父域，默认 .xct258.top
    AUTH_ALLOWED_SUFFIX          初始允许跳转后缀，默认同 Cookie 父域
    AUTH_DOMAIN_NAME             初始域名名称，默认 xct258
    AUTH_SITE_NAME               登录页标题，默认 统一登录
    AUTH_WALLPAPER_URL           壁纸地址
    ADMIN_USERNAME               初始管理员用户名，默认 admin
    ADMIN_PASSWORD               初始管理员密码；不填则自动生成到 /data/initial_admin_password.txt
    ADMIN_SESSION_HOURS          管理员会话小时数，默认 12
    SSO_SESSION_DAYS             服务默认会话天数，默认 7
    AUTH_DB_PATH                 SQLite 路径，默认 /data/auth.db
    AUTH_KEY_PATH                主密钥路径，默认 /data/.master_key
    AUTH_MASTER_KEY              可选，64 位 hex 主密钥；优先级高于文件
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import html
import logging
import os
import re
import secrets
import sqlite3
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote, urlsplit

from cryptography.fernet import Fernet, InvalidToken
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
    Response,
)
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
LOGIN_PAGE = os.path.join(STATIC_DIR, "login.html")
DIST_DIR = os.path.join(STATIC_DIR, "dist")
DIST_INDEX = os.path.join(DIST_DIR, "index.html")

DATA_DIR = os.environ.get("AUTH_DATA_DIR", "/data")
DB_PATH = os.environ.get("AUTH_DB_PATH", os.path.join(DATA_DIR, "auth.db"))
KEY_PATH = os.environ.get("AUTH_KEY_PATH", os.path.join(DATA_DIR, ".master_key"))
DEFAULT_SESSION_DAYS = int(os.environ.get("SSO_SESSION_DAYS", "7"))
ADMIN_SESSION_HOURS = int(os.environ.get("ADMIN_SESSION_HOURS", "12"))

ADMIN_COOKIE = "admin_session"
CSRF_COOKIE = "admin_csrf"
MAX_FAILURES = 5
LOCK_SECONDS = 60

logger = logging.getLogger("auth-server")
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

app = FastAPI(title="统一登录中心", docs_url=None, redoc_url=None)
if os.path.isdir(os.path.join(DIST_DIR, "assets")):
    app.mount(
        "/assets",
        StaticFiles(directory=os.path.join(DIST_DIR, "assets")),
        name="assets",
    )


# ============================================================
# 基础工具
# ============================================================
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def b64e(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def b64d(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def load_master_key() -> bytes:
    raw = os.environ.get("AUTH_MASTER_KEY", "").strip()
    if raw:
        if re.fullmatch(r"[0-9a-fA-F]{64}", raw):
            return bytes.fromhex(raw)
        return hashlib.sha256(raw.encode("utf-8")).digest()

    os.makedirs(os.path.dirname(KEY_PATH) or ".", exist_ok=True)
    if os.path.exists(KEY_PATH):
        with open(KEY_PATH, "r", encoding="utf-8") as fh:
            value = fh.read().strip()
        try:
            return bytes.fromhex(value)
        except ValueError as exc:
            raise RuntimeError(f"主密钥文件格式错误：{KEY_PATH}") from exc

    key = secrets.token_bytes(32)
    with open(KEY_PATH, "w", encoding="utf-8") as fh:
        fh.write(key.hex())
    os.chmod(KEY_PATH, 0o600)
    logger.info("已生成主密钥：%s", KEY_PATH)
    return key


MASTER_KEY = load_master_key()
ADMIN_KEY = hmac.new(MASTER_KEY, b"admin-session", hashlib.sha256).digest()
PASSWORD_KEY = base64.urlsafe_b64encode(
    hashlib.sha256(MASTER_KEY + b"service-password").digest()
)
PASSWORD_CIPHER = Fernet(PASSWORD_KEY)
TOKEN_KEY = hmac.new(MASTER_KEY, b"service-token", hashlib.sha256).digest()


def encrypt_password(password: str) -> str:
    return PASSWORD_CIPHER.encrypt(password.encode("utf-8")).decode("ascii")


def decrypt_password(token: str) -> str:
    if not token:
        return ""
    try:
        return PASSWORD_CIPHER.decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        return ""


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32
    )
    return f"scrypt$16384$8$1${b64e(salt)}${b64e(digest)}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algo, n, r, p, salt_b64, digest_b64 = encoded.split("$")
        if algo != "scrypt":
            return False
        salt = b64d(salt_b64)
        expected = b64d(digest_b64)
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(expected),
        )
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def is_https(request: Request) -> bool:
    proto = request.headers.get("x-forwarded-proto", "").split(",")[0].strip().lower()
    return proto == "https" or request.url.scheme == "https"


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def request_host(request: Request) -> str:
    host = (
        request.headers.get("x-forwarded-host")
        or request.headers.get("host")
        or request.url.netloc
        or ""
    )
    return host.split(",")[0].strip().split(":")[0].lower()


def base_url(request: Request) -> str:
    proto = request.headers.get("x-forwarded-proto", "").split(",")[0].strip()
    proto = proto or request.url.scheme
    host = (
        request.headers.get("x-forwarded-host")
        or request.headers.get("host")
        or request.url.netloc
    )
    return f"{proto}://{host.split(',')[0].strip()}"


# ============================================================
# 数据库
# ============================================================
SCHEMA = """
CREATE TABLE IF NOT EXISTS domains (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    auth_host TEXT NOT NULL UNIQUE,
    cookie_domain TEXT NOT NULL DEFAULT '',
    allowed_suffix TEXT NOT NULL DEFAULT '',
    site_name TEXT NOT NULL DEFAULT '统一登录',
    wallpaper_url TEXT NOT NULL DEFAULT '',
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS services (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain_id INTEGER NOT NULL REFERENCES domains(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    public_url TEXT NOT NULL DEFAULT '',
    password_hash TEXT NOT NULL,
    password_enc TEXT NOT NULL DEFAULT '',
    basic_username TEXT NOT NULL DEFAULT '',
    basic_password_enc TEXT NOT NULL DEFAULT '',
    secret_salt TEXT NOT NULL,
    cookie_name TEXT NOT NULL,
    session_days INTEGER NOT NULL DEFAULT 7,
    token_version INTEGER NOT NULL DEFAULT 1,
    enabled INTEGER NOT NULL DEFAULT 1,
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_login_at TEXT
);

CREATE TABLE IF NOT EXISTS admin_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    is_superadmin INTEGER NOT NULL DEFAULT 1,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    last_login_at TEXT
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor TEXT NOT NULL DEFAULT '',
    action TEXT NOT NULL,
    target TEXT NOT NULL DEFAULT '',
    detail TEXT NOT NULL DEFAULT '',
    ip TEXT NOT NULL DEFAULT '',
    user_agent TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_services_domain ON services(domain_id);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_logs(created_at);
"""


@contextmanager
def db_conn():
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def row_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row else None


def init_db() -> None:
    with db_conn() as conn:
        conn.executescript(SCHEMA)
        columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(services)")
        }
        if "password_enc" not in columns:
            conn.execute(
                "ALTER TABLE services ADD COLUMN password_enc TEXT NOT NULL DEFAULT ''"
            )
        if "basic_username" not in columns:
            conn.execute(
                "ALTER TABLE services ADD COLUMN basic_username TEXT NOT NULL DEFAULT ''"
            )
        if "basic_password_enc" not in columns:
            conn.execute(
                "ALTER TABLE services ADD COLUMN basic_password_enc TEXT NOT NULL DEFAULT ''"
            )

        if not conn.execute("SELECT 1 FROM domains LIMIT 1").fetchone():
            domain_name = os.environ.get("AUTH_DOMAIN_NAME", "xct258")
            auth_host = os.environ.get("AUTH_HOST", "auth.xct258.top")
            cookie_domain = os.environ.get("AUTH_COOKIE_DOMAIN", ".xct258.top")
            allowed_suffix = (
                os.environ.get("AUTH_ALLOWED_SUFFIX", "").strip() or cookie_domain
            )
            site_name = os.environ.get("AUTH_SITE_NAME", "统一登录")
            wallpaper = os.environ.get(
                "AUTH_WALLPAPER_URL", "https://random-image.xct258.top/"
            )
            now = now_iso()
            conn.execute(
                """
                INSERT INTO domains
                  (name, auth_host, cookie_domain, allowed_suffix, site_name,
                   wallpaper_url, enabled, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
                """,
                (
                    domain_name,
                    auth_host.lower(),
                    cookie_domain,
                    allowed_suffix.lower(),
                    site_name,
                    wallpaper,
                    now,
                    now,
                ),
            )
            logger.info("已初始化域名：%s", auth_host)

        if not conn.execute("SELECT 1 FROM admin_users LIMIT 1").fetchone():
            username = os.environ.get("ADMIN_USERNAME", "admin").strip() or "admin"
            password = os.environ.get("ADMIN_PASSWORD", "").strip()
            generated = False
            if not password:
                password = secrets.token_urlsafe(12)
                generated = True
            conn.execute(
                """
                INSERT INTO admin_users
                  (username, password_hash, is_superadmin, enabled, created_at)
                VALUES (?, ?, 1, 1, ?)
                """,
                (username, hash_password(password), now_iso()),
            )
            if generated:
                path = os.path.join(DATA_DIR, "initial_admin_password.txt")
                os.makedirs(DATA_DIR, exist_ok=True)
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(f"{username}\n{password}\n")
                os.chmod(path, 0o600)
                logger.warning("已创建初始管理员 %s，密码写入 %s", username, path)
            else:
                logger.info("已创建初始管理员：%s", username)


init_db()


def audit(
    actor: str,
    action: str,
    target: str = "",
    detail: str = "",
    request: Request | None = None,
) -> None:
    ip = client_ip(request) if request else ""
    ua = (request.headers.get("user-agent", "") if request else "")[:300]
    with db_conn() as conn:
        conn.execute(
            """
            INSERT INTO audit_logs
              (actor, action, target, detail, ip, user_agent, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (actor, action, target, detail, ip, ua, now_iso()),
        )


# ============================================================
# 域名 / 服务
# ============================================================
def resolve_domain(host: str) -> dict[str, Any] | None:
    host = (host or "").lower()
    with db_conn() as conn:
        row = conn.execute(
            "SELECT * FROM domains WHERE lower(auth_host) = ? AND enabled = 1",
            (host,),
        ).fetchone()
        if row:
            return dict(row)

        for candidate in conn.execute(
            "SELECT * FROM domains WHERE enabled = 1 ORDER BY id"
        ).fetchall():
            suffix = (candidate["allowed_suffix"] or candidate["cookie_domain"] or "").lstrip(
                "."
            ).lower()
            if suffix and (host == suffix or host.endswith("." + suffix)):
                return dict(candidate)

        row = conn.execute(
            "SELECT * FROM domains WHERE enabled = 1 ORDER BY id LIMIT 1"
        ).fetchone()
        return dict(row) if row else None


def get_service(slug: str) -> dict[str, Any] | None:
    if not slug:
        return None
    with db_conn() as conn:
        row = conn.execute(
            """
            SELECT s.*,
                   d.name AS domain_name,
                   d.auth_host,
                   d.cookie_domain,
                   d.allowed_suffix,
                   d.site_name AS domain_site_name,
                   d.wallpaper_url,
                   d.enabled AS domain_enabled
            FROM services s
            JOIN domains d ON d.id = s.domain_id
            WHERE s.slug = ?
            """,
            (slug,),
        ).fetchone()
        return dict(row) if row else None


def require_service(slug: str) -> dict[str, Any]:
    service = get_service(slug)
    if not service:
        raise HTTPException(status_code=404, detail="服务不存在或已被删除")
    if not service["enabled"] or not service["domain_enabled"]:
        raise HTTPException(status_code=403, detail="服务已停用")
    return service


INTERNAL_HOSTS = {"127.0.0.1", "localhost", "host.docker.internal"}


def require_service_for_request(request: Request, slug: str) -> dict[str, Any]:
    service = require_service(slug)
    host = request_host(request)
    if host not in INTERNAL_HOSTS and host != service["auth_host"].lower():
        raise HTTPException(status_code=404, detail="服务不属于当前登录主机")
    return service


def service_login_url(request: Request, service: dict[str, Any]) -> str:
    return f"{base_url(request)}/login?service={quote(service['slug'])}"


def safe_next(raw: str, request: Request, service: dict[str, Any]) -> str:
    """只允许跳到该域名白名单后缀下的地址，防开放重定向。"""
    raw = (raw or "").strip()
    if not raw:
        return ""
    parsed = urlsplit(raw)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return ""
    host = parsed.hostname.lower()
    if host == request_host(request):
        return ""
    suffix = (
        service.get("allowed_suffix") or service.get("cookie_domain") or ""
    ).lstrip(".").lower()
    if suffix:
        if not (host == suffix or host.endswith("." + suffix)):
            return ""
    elif host not in ("127.0.0.1", "localhost"):
        return ""
    return raw


def service_token(service: dict[str, Any]) -> str:
    expires = int(time.time()) + int(service["session_days"]) * 86400
    payload = (
        f"v1.{service['slug']}.{service['token_version']}.{expires}"
    )
    signature = hmac.new(
        TOKEN_KEY, payload.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return f"{payload}.{signature}"


def verify_service_token(service: dict[str, Any], token: str | None) -> bool:
    if not token:
        return False
    parts = token.split(".")
    if len(parts) != 5:
        return False
    version, slug, token_version, expires, signature = parts
    if version != "v1" or slug != service["slug"]:
        return False
    try:
        if int(token_version) != int(service["token_version"]):
            return False
        if int(expires) <= int(time.time()):
            return False
    except ValueError:
        return False
    expected = hmac.new(
        TOKEN_KEY,
        f"v1.{slug}.{token_version}.{expires}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(signature, expected)


def service_authenticated(request: Request, service: dict[str, Any]) -> bool:
    return verify_service_token(
        service, request.cookies.get(service["cookie_name"])
    )


def set_service_cookie(
    response: Response, request: Request, service: dict[str, Any]
) -> None:
    response.set_cookie(
        service["cookie_name"],
        service_token(service),
        max_age=int(service["session_days"]) * 86400,
        httponly=True,
        samesite="lax",
        secure=is_https(request),
        domain=service["cookie_domain"] or None,
        path="/",
    )


def clear_service_cookie(response: Response, service: dict[str, Any]) -> None:
    response.delete_cookie(
        service["cookie_name"],
        path="/",
        domain=service["cookie_domain"] or None,
    )


# ============================================================
# 限流
# ============================================================
_failures: dict[str, tuple[int, float]] = {}
_failures_lock = threading.Lock()


def rate_check(key: str) -> None:
    now = time.time()
    with _failures_lock:
        count, locked_until = _failures.get(key, (0, 0.0))
    if locked_until > now:
        raise HTTPException(status_code=429, detail="尝试次数过多，请稍后再试")


def rate_fail(key: str) -> None:
    now = time.time()
    with _failures_lock:
        count, locked_until = _failures.get(key, (0, 0.0))
        count += 1
        if count >= MAX_FAILURES:
            _failures[key] = (0, now + LOCK_SECONDS)
        else:
            _failures[key] = (count, locked_until)


def rate_clear(key: str) -> None:
    with _failures_lock:
        _failures.pop(key, None)


# ============================================================
# 页面
# ============================================================
def html_error(title: str, message: str, status_code: int = 400) -> HTMLResponse:
    body = f"""<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{html.escape(title)} · 统一登录</title>
    <style>
      :root {{ color-scheme: dark; }}
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        min-height: 100vh;
        display: grid;
        place-items: center;
        padding: 24px;
        background: radial-gradient(circle at 50% 0%, #1e293b 0%, #0b1120 55%);
        color: #e6ecf5;
        font-family: system-ui, -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
      }}
      main {{
        width: 100%;
        max-width: 460px;
        padding: 32px 30px;
        border: 1px solid rgba(255,255,255,.12);
        border-radius: 20px;
        background: rgba(9,14,28,.86);
        box-shadow: 0 24px 80px rgba(0,0,0,.35);
      }}
      .icon {{
        display: grid;
        place-items: center;
        width: 46px;
        height: 46px;
        border-radius: 14px;
        background: rgba(244,63,94,.14);
        color: #fda4af;
        font-size: 24px;
        font-weight: 700;
      }}
      h1 {{ margin: 18px 0 10px; font-size: 22px; }}
      p {{ margin: 0; color: #a8b3c7; font-size: 14px; line-height: 1.8; white-space: pre-line; }}
      .foot {{ margin-top: 22px; padding-top: 16px; border-top: 1px solid rgba(255,255,255,.08); font-size: 12px; }}
      a {{ color: #a5b4fc; text-decoration: none; }}
      a:hover {{ text-decoration: underline; }}
    </style>
  </head>
  <body>
    <main>
      <div class="icon" aria-hidden="true">!</div>
      <h1>{html.escape(title)}</h1>
      <p>{html.escape(message)}</p>
      <p class="foot"><a href="/admin/login">管理员入口</a></p>
    </main>
  </body>
</html>
"""
    return HTMLResponse(
        body,
        status_code=status_code,
        headers={
            "Cache-Control": "no-store",
            "X-Frame-Options": "DENY",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
        },
    )


def index_response() -> FileResponse:
    path = DIST_INDEX if os.path.isfile(DIST_INDEX) else LOGIN_PAGE
    return FileResponse(
        path,
        media_type="text/html",
        headers={
            "Cache-Control": "no-store",
            "X-Frame-Options": "DENY",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
        },
    )


@app.get("/", include_in_schema=False)
def root_page(request: Request):
    if current_admin(request):
        return RedirectResponse("/admin", status_code=302)
    return RedirectResponse("/admin/login", status_code=302)


@app.get("/login", include_in_schema=False)
def login_page(request: Request, service: str = "", next: str = ""):
    service = (service or "").strip()
    if not service:
        return html_error(
            "缺少服务参数",
            "请从需要登录的服务页面进入。\n"
            "如果是从旧书签直接打开，请联系管理员获取正确的登录链接。",
            status_code=400,
        )

    svc = get_service(service)
    if not svc:
        return html_error(
            "服务不存在",
            f"服务“{service}”未在统一登录中心注册，可能已被删除。\n"
            "请联系管理员重新添加该服务。",
            status_code=404,
        )
    if not svc["enabled"] or not svc["domain_enabled"]:
        return html_error(
            "服务已停用",
            f"服务“{svc['name']}”当前已停用。\n请联系管理员。",
            status_code=403,
        )

    if service_authenticated(request, svc):
        target = safe_next(next, request, svc)
        if target:
            return RedirectResponse(target, status_code=302)
    return index_response()


@app.get("/admin", include_in_schema=False)
@app.get("/admin/{path:path}", include_in_schema=False)
def admin_page(path: str = ""):
    return index_response()


# ============================================================
# 服务登录接口
# ============================================================
class ServiceLoginPayload(BaseModel):
    password: str = ""


@app.get("/api/site")
def site_config(request: Request):
    """管理登录页 / 根路径使用的站点配置，不需要 service 参数。"""
    domain = resolve_domain(request_host(request))
    if not domain:
        return {"site_name": "统一登录", "wallpaper_url": ""}
    return {
        "site_name": domain["site_name"],
        "wallpaper_url": domain["wallpaper_url"],
        "auth_host": domain["auth_host"],
    }


@app.get("/api/config")
def public_config(request: Request, service: str = ""):
    svc = require_service_for_request(request, service)
    return {
        "enabled": True,
        "site_name": svc["domain_site_name"],
        "service_name": svc["name"],
        "service_slug": svc["slug"],
        "wallpaper_url": svc["wallpaper_url"],
    }


@app.get("/api/auth/status")
def auth_status(request: Request, service: str = "", next: str = ""):
    svc = require_service_for_request(request, service)
    authenticated = service_authenticated(request, svc)
    return {
        "enabled": True,
        "authenticated": authenticated,
        "service": svc["slug"],
        "service_name": svc["name"],
        "redirect": safe_next(next, request, svc) if authenticated else "",
        "login_url": service_login_url(request, svc),
    }


@app.post("/api/auth/login")
def auth_login(
    payload: ServiceLoginPayload,
    request: Request,
    service: str = "",
    next: str = "",
):
    svc = require_service_for_request(request, service)
    key = f"service:{svc['slug']}:{client_ip(request)}"
    rate_check(key)

    if not verify_password(payload.password, svc["password_hash"]):
        rate_fail(key)
        audit(
            actor=f"service:{svc['slug']}",
            action="login.failed",
            target=svc["slug"],
            request=request,
        )
        raise HTTPException(status_code=401, detail="密码错误")

    rate_clear(key)
    with db_conn() as conn:
        conn.execute(
            "UPDATE services SET last_login_at = ? WHERE id = ?",
            (now_iso(), svc["id"]),
        )
    audit(
        actor=f"service:{svc['slug']}",
        action="login.success",
        target=svc["slug"],
        request=request,
    )
    response = JSONResponse(
        {"ok": True, "redirect": safe_next(next, request, svc)}
    )
    set_service_cookie(response, request, svc)
    return response


@app.post("/api/auth/logout")
def auth_logout(request: Request, service: str = ""):
    svc = require_service_for_request(request, service)
    response = JSONResponse({"ok": True})
    clear_service_cookie(response, svc)
    audit(
        actor=f"service:{svc['slug']}",
        action="logout",
        target=svc["slug"],
        request=request,
    )
    return response


@app.get("/api/auth/service/{slug}")
def service_state(slug: str):
    """给业务服务读取当前 Token 版本；用于强制下线即时生效。"""
    svc = get_service(slug)
    if not svc:
        raise HTTPException(status_code=404, detail="服务不存在或已被删除")
    return {
        "service": svc["slug"],
        "enabled": bool(svc["enabled"] and svc["domain_enabled"]),
        "token_version": svc["token_version"],
        "updated_at": svc["updated_at"],
    }


@app.get("/api/auth/verify")
def auth_verify(request: Request, service: str = ""):
    svc = require_service_for_request(request, service)
    if service_authenticated(request, svc):
        return Response(
            status_code=204, headers={"X-Auth-Service": svc["slug"]}
        )
    return JSONResponse({"detail": "未登录或登录已过期"}, status_code=401)


@app.get("/api/health")
def health():
    return {"ok": True}


# ============================================================
# 管理员会话
# ============================================================
class AdminLoginPayload(BaseModel):
    username: str = ""
    password: str = ""

def admin_token(user: dict[str, Any]) -> str:
    expires = int(time.time()) + ADMIN_SESSION_HOURS * 3600
    payload = f"v1.{user['id']}.{expires}"
    signature = hmac.new(
        ADMIN_KEY, payload.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return f"{payload}.{signature}"


def verify_admin_token(token: str | None) -> int | None:
    if not token:
        return None
    parts = token.split(".")
    if len(parts) != 4:
        return None
    version, user_id, expires, signature = parts
    if version != "v1":
        return None
    try:
        if int(expires) <= int(time.time()):
            return None
        uid = int(user_id)
    except ValueError:
        return None
    expected = hmac.new(
        ADMIN_KEY,
        f"v1.{user_id}.{expires}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return None
    return uid


def current_admin(request: Request) -> dict[str, Any] | None:
    uid = verify_admin_token(request.cookies.get(ADMIN_COOKIE))
    if uid is None:
        return None
    with db_conn() as conn:
        row = conn.execute(
            "SELECT * FROM admin_users WHERE id = ? AND enabled = 1", (uid,)
        ).fetchone()
        return dict(row) if row else None


def require_admin(request: Request, csrf: bool = False) -> dict[str, Any]:
    user = current_admin(request)
    if not user:
        raise HTTPException(status_code=401, detail="管理员未登录")
    if csrf:
        header = request.headers.get("x-csrf-token", "")
        cookie = request.cookies.get(CSRF_COOKIE, "")
        if not header or not cookie or not hmac.compare_digest(header, cookie):
            raise HTTPException(status_code=403, detail="CSRF 校验失败")
    return user


@app.post("/api/admin/login")
def admin_login(payload: AdminLoginPayload, request: Request):
    key = f"admin:{client_ip(request)}"
    rate_check(key)
    with db_conn() as conn:
        username = payload.username.strip()
        if username:
            row = conn.execute(
                "SELECT * FROM admin_users WHERE username = ? AND enabled = 1",
                (username,),
            ).fetchone()
        else:
            row = conn.execute(
                """
                SELECT * FROM admin_users
                WHERE enabled = 1 AND is_superadmin = 1
                ORDER BY id LIMIT 1
                """
            ).fetchone()
        user = dict(row) if row else None
        if not user or not verify_password(payload.password, user["password_hash"]):
            rate_fail(key)
            audit(
                actor=username or "admin",
                action="admin.login.failed",
                request=request,
            )
            raise HTTPException(status_code=401, detail="管理密码错误")
        conn.execute(
            "UPDATE admin_users SET last_login_at = ? WHERE id = ?",
            (now_iso(), user["id"]),
        )

    rate_clear(key)
    csrf_token = secrets.token_urlsafe(24)
    response = JSONResponse(
        {"ok": True, "username": user["username"], "csrf_token": csrf_token}
    )
    response.set_cookie(
        ADMIN_COOKIE,
        admin_token(user),
        max_age=ADMIN_SESSION_HOURS * 3600,
        httponly=True,
        samesite="lax",
        secure=is_https(request),
        path="/",
    )
    response.set_cookie(
        CSRF_COOKIE,
        csrf_token,
        max_age=ADMIN_SESSION_HOURS * 3600,
        httponly=False,
        samesite="lax",
        secure=is_https(request),
        path="/",
    )
    audit(actor=user["username"], action="admin.login", request=request)
    return response


@app.get("/api/admin/status")
def admin_status(request: Request):
    user = current_admin(request)
    return {
        "authenticated": bool(user),
        "username": user["username"] if user else "",
    }


@app.post("/api/admin/logout")
def admin_logout(request: Request):
    user = current_admin(request)
    response = JSONResponse({"ok": True})
    response.delete_cookie(ADMIN_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")
    if user:
        audit(actor=user["username"], action="admin.logout", request=request)
    return response


class AdminPasswordPayload(BaseModel):
    current_password: str = ""
    new_password: str = ""


@app.post("/api/admin/change-password")
def admin_change_password(payload: AdminPasswordPayload, request: Request):
    user = require_admin(request, csrf=True)
    if not verify_password(payload.current_password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="当前密码错误")
    if len(payload.new_password) < 8:
        raise HTTPException(status_code=400, detail="新密码至少 8 位")
    with db_conn() as conn:
        conn.execute(
            "UPDATE admin_users SET password_hash = ? WHERE id = ?",
            (hash_password(payload.new_password), user["id"]),
        )
    audit(actor=user["username"], action="admin.password", request=request)
    return {"ok": True}


# ============================================================
# 管理接口：域名
# ============================================================
class DomainPayload(BaseModel):
    name: str = ""
    auth_host: str = ""
    cookie_domain: str = ""
    allowed_suffix: str = ""
    site_name: str = "统一登录"
    wallpaper_url: str = ""
    enabled: bool = True


@app.get("/api/admin/domains")
def list_domains(request: Request):
    require_admin(request)
    with db_conn() as conn:
        rows = conn.execute(
            """
            SELECT d.*, COUNT(s.id) AS service_count
            FROM domains d
            LEFT JOIN services s ON s.domain_id = d.id
            GROUP BY d.id
            ORDER BY d.id
            """
        ).fetchall()
        return [dict(row) for row in rows]


@app.post("/api/admin/domains")
def create_domain(payload: DomainPayload, request: Request):
    admin = require_admin(request, csrf=True)
    name = payload.name.strip()
    auth_host = payload.auth_host.strip().lower()
    if not name or not auth_host:
        raise HTTPException(status_code=400, detail="名称和登录主机名必填")
    cookie_domain = payload.cookie_domain.strip()
    allowed_suffix = payload.allowed_suffix.strip() or cookie_domain
    now = now_iso()
    try:
        with db_conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO domains
                  (name, auth_host, cookie_domain, allowed_suffix, site_name,
                   wallpaper_url, enabled, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    name,
                    auth_host,
                    cookie_domain,
                    allowed_suffix,
                    payload.site_name.strip() or "统一登录",
                    payload.wallpaper_url.strip(),
                    1 if payload.enabled else 0,
                    now,
                    now,
                ),
            )
            domain_id = cur.lastrowid
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="登录主机名已存在") from exc
    audit(
        actor=admin["username"],
        action="domain.create",
        target=str(domain_id),
        detail=auth_host,
        request=request,
    )
    with db_conn() as conn:
        row = conn.execute("SELECT * FROM domains WHERE id = ?", (domain_id,)).fetchone()
        return dict(row)


@app.put("/api/admin/domains/{domain_id}")
def update_domain(domain_id: int, payload: DomainPayload, request: Request):
    admin = require_admin(request, csrf=True)
    with db_conn() as conn:
        current = conn.execute(
            "SELECT * FROM domains WHERE id = ?", (domain_id,)
        ).fetchone()
        if not current:
            raise HTTPException(status_code=404, detail="域名不存在")
        name = payload.name.strip() or current["name"]
        auth_host = payload.auth_host.strip().lower() or current["auth_host"]
        cookie_domain = payload.cookie_domain.strip()
        allowed_suffix = payload.allowed_suffix.strip() or cookie_domain
        try:
            conn.execute(
                """
                UPDATE domains
                SET name = ?, auth_host = ?, cookie_domain = ?,
                    allowed_suffix = ?, site_name = ?, wallpaper_url = ?,
                    enabled = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    name,
                    auth_host,
                    cookie_domain,
                    allowed_suffix,
                    payload.site_name.strip() or "统一登录",
                    payload.wallpaper_url.strip(),
                    1 if payload.enabled else 0,
                    now_iso(),
                    domain_id,
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise HTTPException(status_code=409, detail="登录主机名已存在") from exc
    audit(
        actor=admin["username"],
        action="domain.update",
        target=str(domain_id),
        request=request,
    )
    with db_conn() as conn:
        row = conn.execute("SELECT * FROM domains WHERE id = ?", (domain_id,)).fetchone()
        return dict(row)


@app.delete("/api/admin/domains/{domain_id}")
def delete_domain(domain_id: int, request: Request):
    admin = require_admin(request, csrf=True)
    with db_conn() as conn:
        count = conn.execute(
            "SELECT COUNT(*) AS n FROM services WHERE domain_id = ?", (domain_id,)
        ).fetchone()["n"]
        if count:
            raise HTTPException(status_code=409, detail="该域名下还有服务，不能删除")
        cur = conn.execute("DELETE FROM domains WHERE id = ?", (domain_id,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="域名不存在")
    audit(
        actor=admin["username"],
        action="domain.delete",
        target=str(domain_id),
        request=request,
    )
    return {"ok": True}


# ============================================================
# 管理接口：服务
# ============================================================
class ServiceCreatePayload(BaseModel):
    domain_id: int
    name: str = ""
    slug: str = ""
    public_url: str = ""
    password: str = ""
    basic_auth_enabled: bool = False
    basic_username: str = ""
    basic_password: str = ""
    session_days: int = Field(default=DEFAULT_SESSION_DAYS, ge=1, le=365)
    enabled: bool = True
    notes: str = ""


class ServiceUpdatePayload(BaseModel):
    name: str = ""
    public_url: str = ""
    basic_auth_enabled: bool = False
    basic_username: str = ""
    basic_password: str = ""
    session_days: int = Field(default=DEFAULT_SESSION_DAYS, ge=1, le=365)
    enabled: bool = True
    notes: str = ""


class PasswordResetPayload(BaseModel):
    password: str = ""


def service_row(service_id: int) -> dict[str, Any]:
    with db_conn() as conn:
        row = conn.execute(
            """
            SELECT s.*, d.name AS domain_name, d.auth_host, d.cookie_domain,
                   d.allowed_suffix, d.site_name AS domain_site_name
            FROM services s JOIN domains d ON d.id = s.domain_id
            WHERE s.id = ?
            """,
            (service_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="服务不存在或已被删除")
        return dict(row)


def public_service(row: dict[str, Any]) -> dict[str, Any]:
    """管理接口不返回密码哈希、密钥盐和 Basic 密码密文。"""
    result = {
        key: value
        for key, value in row.items()
        if key not in {"password_hash", "password_enc", "basic_password_enc", "secret_salt"}
    }
    result["basic_auth"] = bool(row.get("basic_password_enc"))
    return result


@app.get("/api/admin/services")
def list_services(request: Request):
    require_admin(request)
    with db_conn() as conn:
        rows = conn.execute(
            """
            SELECT s.*, d.name AS domain_name, d.auth_host, d.cookie_domain
            FROM services s JOIN domains d ON d.id = s.domain_id
            ORDER BY s.id
            """
        ).fetchall()
        return [public_service(dict(row)) for row in rows]


@app.post("/api/admin/services")
def create_service(payload: ServiceCreatePayload, request: Request):
    admin = require_admin(request, csrf=True)
    slug = payload.slug.strip().lower()
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{1,40}", slug):
        raise HTTPException(
            status_code=400,
            detail="服务 ID 只能包含小写字母、数字、-、_，长度 2-41",
        )
    name = payload.name.strip() or slug
    with db_conn() as conn:
        domain = conn.execute(
            "SELECT * FROM domains WHERE id = ?", (payload.domain_id,)
        ).fetchone()
        if not domain:
            raise HTTPException(status_code=400, detail="域名不存在")

    password = payload.password or secrets.token_urlsafe(12)
    basic_user = payload.basic_username.strip()
    basic_enc = ""
    if payload.basic_auth_enabled:
        if not basic_user or not payload.basic_password:
            raise HTTPException(
                status_code=400, detail="启用 Basic Auth 时必须填写用户名和密码"
            )
        basic_enc = encrypt_password(payload.basic_password)
    salt = ""
    cookie_name = f"sso_{slug.replace('-', '_')}"
    now = now_iso()
    try:
        with db_conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO services
                  (domain_id, name, slug, public_url, password_hash, password_enc,
                   basic_username, basic_password_enc, secret_salt, cookie_name,
                   session_days, token_version, enabled, notes, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?)
                """,
                (
                    payload.domain_id,
                    name,
                    slug,
                    payload.public_url.strip(),
                    hash_password(password),
                    encrypt_password(password),
                    basic_user,
                    basic_enc,
                    salt,
                    cookie_name,
                    payload.session_days,
                    1 if payload.enabled else 0,
                    payload.notes.strip(),
                    now,
                    now,
                ),
            )
            service_id = cur.lastrowid
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="服务 ID 已存在") from exc

    audit(
        actor=admin["username"],
        action="service.create",
        target=str(service_id),
        detail=slug,
        request=request,
    )
    return {
        "service": public_service(service_row(service_id)),
        "password": password,
        "cookie_name": cookie_name,
    }


@app.put("/api/admin/services/{service_id}")
def update_service(
    service_id: int, payload: ServiceUpdatePayload, request: Request
):
    admin = require_admin(request, csrf=True)
    current = service_row(service_id)
    basic_user = payload.basic_username.strip()
    basic_enc = ""
    if payload.basic_auth_enabled:
        if not basic_user:
            raise HTTPException(status_code=400, detail="Basic Auth 用户名必填")
        if payload.basic_password:
            basic_enc = encrypt_password(payload.basic_password)
        else:
            basic_enc = current["basic_password_enc"]
            if not basic_enc:
                raise HTTPException(status_code=400, detail="Basic Auth 密码必填")
    with db_conn() as conn:
        conn.execute(
            """
            UPDATE services
            SET name = ?, public_url = ?, basic_username = ?,
                basic_password_enc = ?, session_days = ?, enabled = ?,
                notes = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                payload.name.strip(),
                payload.public_url.strip(),
                basic_user,
                basic_enc,
                payload.session_days,
                1 if payload.enabled else 0,
                payload.notes.strip(),
                now_iso(),
                service_id,
            ),
        )
    audit(
        actor=admin["username"],
        action="service.update",
        target=str(service_id),
        request=request,
    )
    return public_service(service_row(service_id))


@app.delete("/api/admin/services/{service_id}")
def delete_service(service_id: int, request: Request):
    admin = require_admin(request, csrf=True)
    with db_conn() as conn:
        cur = conn.execute("DELETE FROM services WHERE id = ?", (service_id,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="服务不存在或已被删除")
    audit(
        actor=admin["username"],
        action="service.delete",
        target=str(service_id),
        request=request,
    )
    return {"ok": True}


@app.get("/api/admin/services/{service_id}/password")
def view_service_password(service_id: int, request: Request):
    admin = require_admin(request)
    service = service_row(service_id)
    password = decrypt_password(service["password_enc"])
    audit(
        actor=admin["username"],
        action="service.password.view",
        target=str(service_id),
        detail=service["slug"],
        request=request,
    )
    return {"password": password, "stored": bool(password)}


@app.post("/api/admin/services/{service_id}/reset-password")
def reset_service_password(
    service_id: int, payload: PasswordResetPayload, request: Request
):
    admin = require_admin(request, csrf=True)
    service = service_row(service_id)
    password = payload.password or secrets.token_urlsafe(12)
    with db_conn() as conn:
        conn.execute(
            "UPDATE services SET password_hash = ?, password_enc = ?, updated_at = ? WHERE id = ?",
            (hash_password(password), encrypt_password(password), now_iso(), service_id),
        )
    audit(
        actor=admin["username"],
        action="service.password",
        target=str(service_id),
        detail=service["slug"],
        request=request,
    )
    return {"password": password}


@app.post("/api/admin/services/{service_id}/revoke")
def revoke_service_sessions(service_id: int, request: Request):
    admin = require_admin(request, csrf=True)
    service = service_row(service_id)
    with db_conn() as conn:
        conn.execute(
            """
            UPDATE services
            SET token_version = token_version + 1, updated_at = ?
            WHERE id = ?
            """,
            (now_iso(), service_id),
        )
    audit(
        actor=admin["username"],
        action="service.revoke",
        target=str(service_id),
        detail=service["slug"],
        request=request,
    )
    return {"ok": True, "token_version": service["token_version"] + 1}


@app.get("/api/admin/services/{service_id}/config")
def service_config(service_id: int, request: Request):
    require_admin(request)
    service = service_row(service_id)
    login_url = f"https://{service['auth_host']}/login"
    suffix = service["allowed_suffix"] or service["cookie_domain"]
    env = "\n".join(
        [
            "AUTH_ENABLED=true",
            f"SERVICE_ID={service['slug']}",
            f"SSO_LOGIN_URL={login_url}",
            f"SSO_COOKIE_NAME={service['cookie_name']}",
            f"SSO_COOKIE_DOMAIN={service['cookie_domain']}",
            f"SSO_ALLOWED_REDIRECT_SUFFIX={suffix}",
            f"SSO_VERIFY_URL=https://{service['auth_host']}/api/auth/verify",
            "",
        ]
    )
    basic_header = ""
    if service["basic_username"] and service["basic_password_enc"]:
        basic_password = decrypt_password(service["basic_password_enc"])
        if basic_password:
            token = base64.b64encode(
                f"{service['basic_username']}:{basic_password}".encode("utf-8")
            ).decode("ascii")
            basic_header = f'    proxy_set_header Authorization "Basic {token}";\n'
    nginx = f"""location = /_sso_auth {{
    internal;
    proxy_pass https://{service['auth_host']}/api/auth/verify?service={service['slug']};
    proxy_ssl_server_name on;
    proxy_set_header Host {service['auth_host']};
    proxy_pass_request_body off;
    proxy_set_header Content-Length "";
}}

location / {{
    auth_request /_sso_auth;
    error_page 401 = @sso_login;
{basic_header}    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection $http_connection;
    proxy_http_version 1.1;
    proxy_buffering off;
    proxy_read_timeout 3600s;
    include conf.d/include/proxy.conf;
}}

location @sso_login {{
    return 302 {login_url}?service={service['slug']}&next=https://$host$request_uri;
}}
"""
    return {"env": env, "nginx": nginx}


@app.get("/api/admin/overview")
def admin_overview(request: Request):
    require_admin(request)
    with db_conn() as conn:
        domains = conn.execute("SELECT COUNT(*) AS n FROM domains").fetchone()["n"]
        services = conn.execute("SELECT COUNT(*) AS n FROM services").fetchone()["n"]
        enabled = conn.execute(
            "SELECT COUNT(*) AS n FROM services WHERE enabled = 1"
        ).fetchone()["n"]
        today = datetime.now(timezone.utc).date().isoformat()
        logins = conn.execute(
            "SELECT COUNT(*) AS n FROM audit_logs WHERE action = 'login.success' AND created_at LIKE ?",
            (f"{today}%",),
        ).fetchone()["n"]
        recent = conn.execute(
            """
            SELECT actor, action, target, detail, created_at
            FROM audit_logs ORDER BY id DESC LIMIT 12
            """
        ).fetchall()
    return {
        "domains": domains,
        "services": services,
        "enabled_services": enabled,
        "today_logins": logins,
        "recent": [dict(row) for row in recent],
    }


@app.get("/api/admin/audit")
def admin_audit(request: Request, limit: int = 100):
    require_admin(request)
    limit = max(1, min(limit, 500))
    with db_conn() as conn:
        rows = conn.execute(
            """
            SELECT actor, action, target, detail, ip, created_at
            FROM audit_logs ORDER BY id DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=os.environ.get("UVICORN_HOST", "127.0.0.1"),
        port=int(os.environ.get("UVICORN_PORT", "8290")),
    )
