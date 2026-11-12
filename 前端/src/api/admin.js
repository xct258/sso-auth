const CSRF_COOKIE = 'admin_csrf'

export function csrfToken() {
  for (const part of document.cookie.split(';')) {
    const [name, ...rest] = part.trim().split('=')
    if (name === CSRF_COOKIE) return rest.join('=')
  }
  return ''
}

export async function adminStatus() {
  const res = await fetch('/api/admin/status', {
    credentials: 'same-origin',
    cache: 'no-store',
  })
  if (!res.ok) return { authenticated: false, username: '' }
  return res.json()
}

export async function adminLogin(password) {
  const res = await fetch('/api/admin/login', {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ password }),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    throw new Error(data.detail || `登录失败（${res.status}）`)
  }
  return data
}

export async function adminLogout() {
  await fetch('/api/admin/logout', {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'X-CSRF-Token': csrfToken() },
  })
}

export async function api(path, options = {}) {
  const method = (options.method || 'GET').toUpperCase()
  const headers = { ...(options.headers || {}) }
  if (options.body && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json'
  }
  if (method !== 'GET' && method !== 'HEAD') {
    headers['X-CSRF-Token'] = csrfToken()
  }

  const res = await fetch(path, {
    credentials: 'same-origin',
    ...options,
    headers,
  })
  const data = await res.json().catch(() => ({}))

  if (res.status === 401) {
    const next = encodeURIComponent(window.location.pathname + window.location.search)
    window.location.assign(`/admin/login?next=${next}`)
    throw new Error('管理员未登录')
  }
  if (!res.ok) {
    throw new Error(data.detail || `请求失败（${res.status}）`)
  }
  return data
}
