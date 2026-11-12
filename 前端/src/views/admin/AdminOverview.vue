<script setup>
import { onMounted, ref } from 'vue'

import { api } from '@/api/admin'
import { notify } from '@/composables/useToast'

const data = ref({
  domains: 0,
  services: 0,
  enabled_services: 0,
  today_logins: 0,
  recent: [],
})
const loading = ref(true)

function formatTime(value) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString()
}

onMounted(async () => {
  try {
    data.value = await api('/api/admin/overview')
  } catch (err) {
    notify(err?.message || '加载失败', 'error')
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="admin-page">
    <header class="admin-page-head">
      <div>
        <h1>概览</h1>
        <p>域名、服务与最近登录情况</p>
      </div>
    </header>

    <section class="stat-grid">
      <div class="stat-card">
        <span>域名</span>
        <strong>{{ data.domains }}</strong>
      </div>
      <div class="stat-card">
        <span>服务</span>
        <strong>{{ data.services }}</strong>
      </div>
      <div class="stat-card">
        <span>已启用服务</span>
        <strong>{{ data.enabled_services }}</strong>
      </div>
      <div class="stat-card">
        <span>今日登录</span>
        <strong>{{ data.today_logins }}</strong>
      </div>
    </section>

    <section class="admin-card">
      <header class="admin-card-head">
        <h2>最近动态</h2>
      </header>
      <p v-if="loading" class="admin-muted">加载中…</p>
      <div v-else-if="!data.recent.length" class="admin-empty">还没有记录</div>
      <div v-else class="recent-list">
        <div
          v-for="item in data.recent"
          :key="item.created_at + item.action + item.target"
          class="recent-item"
        >
          <div class="recent-main">
            <code>{{ item.action }}</code>
            <span>{{ item.target || item.detail || '-' }}</span>
          </div>
          <time>{{ formatTime(item.created_at) }}</time>
        </div>
      </div>
    </section>
  </div>
</template>
