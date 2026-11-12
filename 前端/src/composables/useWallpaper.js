import { reactive, ref } from 'vue'

const TIMEOUT_MS = 8000
const DEFAULT_ACCENT = '#6366f1'
const DEFAULT_ACCENT_RGB = '99, 102, 241'

export const wallpaperSrc = ref('')
export const wallpaperReady = ref(false)
export const wallpaperFailed = ref(false)
export const wallpaperTimedOut = ref(false)

export const wallpaperProgress = reactive({
  phase: 'loading', // loading | decoding | ready | failed
  loaded: 0,
  total: 0,
  known: false,
  percent: 0,
})

export const wallpaperTheme = reactive({
  accent: DEFAULT_ACCENT,
  accentRgb: DEFAULT_ACCENT_RGB,
})

let seq = 0
let timer = 0
let objectUrl = ''
let loadedUrl = ''

function revoke(url) {
  if (url && url.startsWith('blob:')) URL.revokeObjectURL(url)
}

function resetProgress() {
  wallpaperProgress.phase = 'loading'
  wallpaperProgress.loaded = 0
  wallpaperProgress.total = 0
  wallpaperProgress.known = false
  wallpaperProgress.percent = 0
}

let lastProgressAt = 0

function updateProgress(loaded, total, force = false) {
  const now = Date.now()
  if (!force && now - lastProgressAt < 80) return
  lastProgressAt = now
  wallpaperProgress.loaded = loaded
  wallpaperProgress.total = total
  wallpaperProgress.known = total > 0
  wallpaperProgress.percent = total > 0 ? Math.min(99, Math.round((loaded / total) * 100)) : 0
}

function setTheme(accent) {
  if (!/^#[0-9a-f]{6}$/i.test(accent || '')) return
  const n = parseInt(accent.slice(1), 16)
  wallpaperTheme.accent = accent
  wallpaperTheme.accentRgb = `${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}`
  const root = document.documentElement
  root.style.setProperty('--wp-accent', wallpaperTheme.accent)
  root.style.setProperty('--wp-accent-rgb', wallpaperTheme.accentRgb)
}

function decodeImage(src) {
  return new Promise((resolve, reject) => {
    const image = new Image()
    image.decoding = 'async'
    image.onload = async () => {
      try {
        if (image.decode) await image.decode()
      } catch (_) {
        /* 已加载的图片 decode 失败仍可显示 */
      }
      resolve()
    }
    image.onerror = () => reject(new Error('image error'))
    image.src = src
  })
}

function nextPaint() {
  return new Promise((resolve) => {
    requestAnimationFrame(() => requestAnimationFrame(resolve))
  })
}

function fail(attempt) {
  if (attempt !== seq) return
  clearTimeout(timer)
  wallpaperFailed.value = true
  wallpaperProgress.phase = 'failed'
}

export async function loadWallpaper(url) {
  const attempt = ++seq
  clearTimeout(timer)
  resetProgress()
  wallpaperFailed.value = false
  wallpaperTimedOut.value = false

  if (!url) {
    // 没有配置壁纸不是加载失败，直接显示纯色背景和登录卡片。
    loadedUrl = ''
    wallpaperReady.value = true
    wallpaperFailed.value = false
    wallpaperProgress.phase = 'ready'
    return
  }

  // 同一张壁纸已经加载完成时直接复用，避免登录页 → 后台重复请求。
  if (wallpaperReady.value && !wallpaperFailed.value && url === loadedUrl) {
    return
  }

  let finished = false

  timer = setTimeout(() => {
    if (attempt !== seq || finished) return
    // 超时只提示并可重试，不终止当前下载；后续加载完成仍然生效。
    wallpaperTimedOut.value = true
  }, TIMEOUT_MS)

  try {
    const response = await fetch(url, { cache: 'no-store' })
    if (attempt !== seq || finished) return
    if (!response.ok) throw new Error(`HTTP ${response.status}`)

    const type = (response.headers.get('content-type') || '').toLowerCase()
    if (type && !type.startsWith('image/')) throw new Error('not an image')

    setTheme(response.headers.get('x-theme-color-hex'))

    const total = Number(response.headers.get('content-length')) || 0
    let blob

    if (response.body && typeof response.body.getReader === 'function') {
      const reader = response.body.getReader()
      const chunks = []
      let loaded = 0
      updateProgress(0, total, true)

      for (;;) {
        const { done, value } = await reader.read()
        if (done) break
        if (!value?.byteLength) continue
        chunks.push(value)
        loaded += value.byteLength
        updateProgress(loaded, total)
      }

      if (attempt !== seq || finished) return
      wallpaperProgress.phase = 'decoding'
      wallpaperProgress.percent = 99
      blob = new Blob(chunks, { type: type || 'image/jpeg' })
    } else {
      blob = await response.blob()
    }

    if (!blob.size) throw new Error('empty image')
    const nextUrl = URL.createObjectURL(blob)
    await decodeImage(nextUrl)

    if (attempt !== seq || finished) {
      revoke(nextUrl)
      return
    }

    finished = true
    clearTimeout(timer)
    revoke(objectUrl)
    objectUrl = nextUrl
    wallpaperSrc.value = nextUrl
    wallpaperProgress.loaded = blob.size
    wallpaperProgress.total = blob.size
    wallpaperProgress.known = true
    wallpaperProgress.percent = 100
    wallpaperProgress.phase = 'ready'
    loadedUrl = url

    // 等图片真正绘制到背景层后，再撤掉加载页。
    await nextPaint()
    if (attempt !== seq) return
    wallpaperReady.value = true
    wallpaperFailed.value = false
    wallpaperTimedOut.value = false
  } catch (_) {
    if (attempt !== seq || finished) return

    // fetch 失败（CORS/网络）时退回直接图片加载，仍等待解码完成。
    try {
      wallpaperProgress.phase = 'decoding'
      await decodeImage(url)
      if (attempt !== seq || finished) return

      finished = true
      clearTimeout(timer)
      revoke(objectUrl)
      objectUrl = ''
      wallpaperSrc.value = url
      wallpaperProgress.percent = 100
      wallpaperProgress.phase = 'ready'
      loadedUrl = url

      await nextPaint()
      if (attempt !== seq) return
      wallpaperReady.value = true
      wallpaperFailed.value = false
      wallpaperTimedOut.value = false
    } catch (_) {
      if (attempt !== seq || finished) return
      finished = true
      fail(attempt)
    }
  }
}
