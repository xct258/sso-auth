/**
 * 新服务前端接入模板（原生 ES Module，Vue/React 通用）。
 *
 * 用法：
 *   import { requireLogin, authFetch, logout } from './frontend-auth'
 *   await requireLogin()                       // 应用启动时
 *   const res = await authFetch('/api/todos')  // 自动处理 401
 *   await logout()                             // 退出登录
 *
 * 服务 ID 可以显式传入，也可以在构建时设置 VITE_SERVICE_ID。
 * Cookie 是 HttpOnly，前端读不到，登录状态只通过后端 /api/auth/status 判断。
 */

const FALLBACK_LOGIN_URL = 'https://auth.o1-1.xct258.top/login'
const DEFAULT_SERVICE = import.meta.env?.VITE_SERVICE_ID || ''

let lastLoginUrl = FALLBACK_LOGIN_URL

export async function getAuthStatus(service = DEFAULT_SERVICE) {
  const res = await fetch(
    `/api/auth/status?service=${encodeURIComponent(service)}`,
    {
      credentials: 'same-origin',
      cache: 'no-store',
    },
  )
  if (!res.ok) {
    throw new Error(`获取登录状态失败：HTTP ${res.status}`)
  }
  const data = await res.json()
  if (data.login_url) lastLoginUrl = data.login_url
  return data
}

export function buildLoginUrl(
  loginUrl,
  service = DEFAULT_SERVICE,
  next = window.location.href,
) {
  const base = loginUrl || lastLoginUrl || FALLBACK_LOGIN_URL
  const sep = base.includes('?') ? '&' : '?'
  return `${base}${sep}service=${encodeURIComponent(service)}&next=${encodeURIComponent(next)}`
}

export function redirectToLogin(
  loginUrl,
  service = DEFAULT_SERVICE,
  next = window.location.href,
) {
  window.location.assign(buildLoginUrl(loginUrl, service, next))
}

/**
 * 应用启动时调用：未登录直接跳 auth-server。
 * 返回 true 表示已登录，可以继续渲染页面。
 */
export async function requireLogin(service = DEFAULT_SERVICE) {
  const status = await getAuthStatus(service)
  if (status.enabled && !status.authenticated) {
    redirectToLogin(status.login_url, service)
    return false
  }
  return true
}

/**
 * 带登录态的 fetch：401 时跳登录中心，避免把 HTML 登录页当 JSON 解析。
 */
export async function authFetch(input, init = {}, service = DEFAULT_SERVICE) {
  const res = await fetch(input, {
    credentials: 'same-origin',
    ...init,
  })
  if (res.status === 401) {
    redirectToLogin(lastLoginUrl, service)
    throw new Error('未登录或登录已过期')
  }
  return res
}

/**
 * 退出登录：只清除当前服务的 Cookie。
 */
export async function logout(service = DEFAULT_SERVICE) {
  await fetch(`/api/auth/logout?service=${encodeURIComponent(service)}`, {
    method: 'POST',
    credentials: 'same-origin',
  })
  window.location.assign('/')
}
