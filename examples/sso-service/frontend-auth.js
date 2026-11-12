/**
 * 新服务前端接入模板（原生 ES Module，Vue/React 通用）。
 *
 * 用法：
 *   import { requireLogin, authFetch, logout } from './frontend-auth'
 *   await requireLogin()                       // 应用启动时
 *   const res = await authFetch('/api/todos')  // 自动处理 401
 *   await logout()                             // 退出登录
 *
 * 注意：Cookie 是 HttpOnly，前端读不到，也不需要读；
 * 登录状态只通过后端 /api/auth/status 判断。
 */

const FALLBACK_LOGIN_URL = 'https://auth.o1-1.xct258.top/login'

export async function getAuthStatus() {
  const res = await fetch('/api/auth/status', {
    credentials: 'same-origin',
    cache: 'no-store',
  })
  if (!res.ok) {
    throw new Error(`获取登录状态失败：HTTP ${res.status}`)
  }
  return res.json()
}

export function buildLoginUrl(loginUrl, next = window.location.href) {
  const base = loginUrl || FALLBACK_LOGIN_URL
  const sep = base.includes('?') ? '&' : '?'
  return `${base}${sep}next=${encodeURIComponent(next)}`
}

export function redirectToLogin(loginUrl = FALLBACK_LOGIN_URL) {
  window.location.assign(buildLoginUrl(loginUrl))
}

/**
 * 应用启动时调用：未登录直接跳 auth-server。
 * 返回 true 表示已登录，可以继续渲染页面。
 */
export async function requireLogin() {
  const status = await getAuthStatus()
  if (status.enabled && !status.authenticated) {
    redirectToLogin(status.login_url)
    return false
  }
  return true
}

/**
 * 带登录态的 fetch：401 时跳登录中心，避免把 HTML 登录页当 JSON 解析。
 */
export async function authFetch(input, init = {}) {
  const res = await fetch(input, {
    credentials: 'same-origin',
    ...init,
  })
  if (res.status === 401) {
    redirectToLogin()
    throw new Error('未登录或登录已过期')
  }
  return res
}

/**
 * 退出登录：清除父域 Cookie，所有接入服务同时退出。
 */
export async function logout() {
  await fetch('/api/auth/logout', {
    method: 'POST',
    credentials: 'same-origin',
  })
  window.location.assign('/')
}
