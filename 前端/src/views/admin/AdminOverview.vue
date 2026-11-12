<script setup>
import { onMounted, ref } from 'vue'

import { api } from '@/api/admin'

const data = ref({
  domains: 0,
  services: 0,
  enabled_services: 0,
  today_logins: 0,
  recent: [],
})
const loading = ref(true)
const error = ref('')

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
    error.value = err?.message || '加载失败'
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

    <p v-if="error" class="admin-alert">{{ error }}</p>

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
      <div v-else class="table-wrap">
        <table class="admin-table">
          <thead>
            <tr>
              <th>时间</th>
              <th>操作者</th>
              <th>动作</th>
              <th>对象</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in data.recent" :key="item.created_at + item.action + item.target">
              <td>{{ formatTime(item.created_at) }}</td>
              <td>{{ item.actor || '-' }}</td>
              <td><code>{{ item.action }}</code></td>
              <td>{{ item.target || item.detail || '-' }}</td>
            </tr>
            <tr v-if="!data.recent.length">
              <td colspan="4" class="admin-empty">还没有记录</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>
