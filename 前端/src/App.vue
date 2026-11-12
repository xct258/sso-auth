<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'

import LoadingScreen from '@/components/LoadingScreen.vue'
import SecureInput from '@/components/SecureInput.vue'
import {
  loadWallpaper,
  wallpaperFailed,
  wallpaperProgress,
  wallpaperReady,
  wallpaperSrc,
  wallpaperTimedOut,
} from '@/composables/useWallpaper'

const params = new URLSearchParams(window.location.search)
const next = params.get('next') || ''
const isFinePointer = window.matchMedia?.('(pointer: fine)').matches ?? true

const siteName = ref('统一登录')
const password = ref('')
const error = ref('')
const loading = ref(false)
const showPassword = ref(false)
const success = ref(false)
const successMessage = ref('')
const wallpaperUrl = ref('')
const keyboardHeight = ref(0)

function onKeyboardChange(event) {
  keyboardHeight.value = event?.open ? event.height || 0 : 0
}

const homeHref = computed(() => (isSafeNext(next) ? next : '/'))
const homeText = computed(() => (isSafeNext(next) ? '返回刚才的页面' : '首页'))

// 只允许跳回登录中心同一父域下的地址，避免 next 被塞入任意外链。
function isSafeNext(value) {
  if (!/^https?:\/\//i.test(value)) return false
  try {
    const target = new URL(value)
    const host = target.hostname.toLowerCase()
    const base = window.location.hostname.toLowerCase()
    const parent = base.split('.').slice(1).join('.')
    return (
      host === base ||
      (!!parent && (host === parent || host.endsWith('.' + parent)))
    )
  } catch (_) {
    return false
  }
}

async function fetchConfig() {
  return fetch('/api/config', { credentials: 'same-origin' })
    .then((response) => response.json())
    .catch(() => ({}))
}

async function boot() {
  let config = {}
  let status = {}

  try {
    ;[config, status] = await Promise.all([
      fetchConfig(),
      fetch('/api/auth/status?next=' + encodeURIComponent(next), {
        credentials: 'same-origin',
      })
        .then((response) => response.json())
        .catch(() => ({})),
    ])

    if (config.site_name) {
      siteName.value = config.site_name
      document.title = config.site_name
    }
  } catch (_) {
    /* 配置加载失败时仍然进入壁纸加载/重试流程 */
  }

  if (status.authenticated) {
    if (status.redirect) {
      window.location.replace(status.redirect)
      return
    }
    success.value = true
    successMessage.value = '当前已是登录状态，可以关闭此页面。'
    return
  }

  wallpaperUrl.value = config.wallpaper_url || ''
  await loadWallpaper(wallpaperUrl.value)
}

async function retryWallpaper() {
  const config = await fetchConfig()
  if (config.wallpaper_url) wallpaperUrl.value = config.wallpaper_url

  await loadWallpaper(wallpaperUrl.value)
}

function onPasteError(message) {
  error.value = message
}

async function submit() {
  if (loading.value) return

  if (!password.value) {
    error.value = '请输入密码'
    return
  }

  loading.value = true
  error.value = ''

  try {
    const response = await fetch('/api/auth/login?next=' + encodeURIComponent(next), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify({ password: password.value }),
    })
    const data = await response.json().catch(() => ({}))

    if (!response.ok) {
      throw new Error(data.detail || `登录失败（${response.status}）`)
    }
    if (data.redirect) {
      window.location.replace(data.redirect)
      return
    }
    success.value = true
    successMessage.value = ''
  } catch (err) {
    error.value = err?.message || '登录失败'
    password.value = ''
  } finally {
    loading.value = false
  }
}

onMounted(boot)
</script>

<template>
  <div class="bg" :class="{ loaded: wallpaperReady }">
    <img v-if="wallpaperSrc" :src="wallpaperSrc" alt="" />
  </div>

  <LoadingScreen
    v-if="!wallpaperReady && !success"
    :progress="wallpaperProgress"
    :site-name="siteName"
    :failed="wallpaperFailed"
    :timed-out="wallpaperTimedOut"
    @retry="retryWallpaper"
  />

  <main
    v-else
    class="wrap"
    :style="keyboardHeight ? { paddingBottom: `${keyboardHeight}px` } : undefined"
  >
    <form v-if="!success" class="card" novalidate @submit.prevent="submit">
      <div class="brand">
        <div class="logo" aria-hidden="true">
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="white"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <rect x="4" y="10.5" width="16" height="10" rx="2.5" />
            <path d="M8 10.5V8a4 4 0 0 1 8 0v2.5" />
            <circle cx="12" cy="15.5" r="1.2" fill="white" stroke="none" />
          </svg>
        </div>
        <div class="brand-text">
          <h1>{{ siteName }}</h1>
          <p>一次登录，访问全部服务</p>
        </div>
      </div>

      <label>访问密码</label>

      <SecureInput
        v-model="password"
        :visible="showPassword"
        :autofocus="isFinePointer"
        @change="error = ''"
        @paste-error="onPasteError"
        @toggle-visibility="showPassword = !showPassword"
        @keyboard-change="onKeyboardChange"
        @submit="submit"
      />

      <p class="error" role="alert" aria-live="polite">{{ error }}</p>

      <button class="submit" type="submit" :class="{ loading }" :disabled="loading">
        <span class="label">登 录</span>
        <span class="spinner" aria-hidden="true"></span>
      </button>

      <p class="foot">登录状态将在同一父域下的服务间共享</p>
    </form>

    <div v-else class="success">
      <div class="check" aria-hidden="true">✓</div>
      <h1>已登录</h1>
      <p v-if="successMessage">{{ successMessage }}</p>
      <p v-else>
        可以关闭此页面，或前往
        <a :href="homeHref">{{ homeText }}</a>。
      </p>
    </div>
  </main>
</template>
