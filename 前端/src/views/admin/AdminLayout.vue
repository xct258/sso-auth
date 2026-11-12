<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import LoadingScreen from '@/components/LoadingScreen.vue'
import {
  loadWallpaper,
  wallpaperFailed,
  wallpaperProgress,
  wallpaperReady,
  wallpaperSrc,
  wallpaperTimedOut,
} from '@/composables/useWallpaper'
import { adminLogout, adminStatus } from '@/api/admin'

const router = useRouter()
const username = ref('')
const siteName = ref('统一登录')

async function fetchSite() {
  return fetch('/api/site', { credentials: 'same-origin', cache: 'no-store' })
    .then((response) => response.json())
    .catch(() => ({}))
}

onMounted(async () => {
  const [status, config] = await Promise.all([adminStatus(), fetchSite()])
  username.value = status.username || ''
  if (config.site_name) siteName.value = config.site_name

  if (wallpaperReady.value) {
    // 登录页已经加载过同一张壁纸，直接复用；不会重复请求。
    loadWallpaper(config.wallpaper_url || '')
    return
  }

  await loadWallpaper(config.wallpaper_url || '')
})

async function retryWallpaper() {
  const config = await fetchSite()
  if (config.site_name) siteName.value = config.site_name
  await loadWallpaper(config.wallpaper_url || '')
}

async function logout() {
  await adminLogout()
  await router.replace('/admin/login')
}
</script>

<template>
  <div class="bg admin-bg" :class="{ loaded: wallpaperReady }">
    <img v-if="wallpaperSrc" :src="wallpaperSrc" alt="" />
  </div>

  <LoadingScreen
    v-if="!wallpaperReady"
    :progress="wallpaperProgress"
    :site-name="siteName"
    :failed="wallpaperFailed"
    :timed-out="wallpaperTimedOut"
    @retry="retryWallpaper"
  />

  <div v-else class="admin-shell">
    <aside class="admin-sidebar">
      <div class="admin-brand">
        <span class="admin-brand-mark">S</span>
        <div>
          <strong>统一登录</strong>
          <small>管理控制台</small>
        </div>
      </div>

      <nav class="admin-nav">
        <router-link to="/admin" exact-active-class="active">概览</router-link>
        <router-link to="/admin/access" active-class="active">接入管理</router-link>
        <router-link to="/admin/audit" active-class="active">审计日志</router-link>
        <router-link to="/admin/settings" active-class="active">系统设置</router-link>
      </nav>

      <div class="admin-user">
        <span>{{ username || '管理员' }}</span>
        <button type="button" @click="logout">退出</button>
      </div>
    </aside>

    <main class="admin-main">
      <router-view v-slot="{ Component }">
        <transition name="admin-page" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>
  </div>
</template>
