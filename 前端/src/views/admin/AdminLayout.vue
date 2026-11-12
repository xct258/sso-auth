<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { adminLogout, adminStatus } from '@/api/admin'
import {
  loadWallpaper,
  wallpaperReady,
  wallpaperSrc,
} from '@/composables/useWallpaper'

const router = useRouter()
const username = ref('')

onMounted(async () => {
  const [status, config] = await Promise.all([
    adminStatus(),
    fetch('/api/site', { credentials: 'same-origin', cache: 'no-store' })
      .then((response) => response.json())
      .catch(() => ({})),
  ])
  username.value = status.username || ''
  await loadWallpaper(config.wallpaper_url || '')
})

async function logout() {
  await adminLogout()
  await router.replace('/admin/login')
}
</script>

<template>
  <div class="bg admin-bg" :class="{ loaded: wallpaperReady }">
    <img v-if="wallpaperSrc" :src="wallpaperSrc" alt="" />
  </div>

  <div class="admin-shell">
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
      <router-view />
    </main>
  </div>
</template>
