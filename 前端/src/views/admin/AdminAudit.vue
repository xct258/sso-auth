<script setup>
import { computed, onMounted, ref } from 'vue'

import { api } from '@/api/admin'

const logs = ref([])
const loading = ref(true)
const error = ref('')
const limit = ref(100)
const query = ref('')

const filteredLogs = computed(() => {
  const value = query.value.trim().toLowerCase()
  if (!value) return logs.value
  return logs.value.filter((item) =>
    [item.actor, item.action, item.target, item.detail, item.ip]
      .join(' ')
      .toLowerCase()
      .includes(value),
  )
})

function formatTime(value) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString()
}

async function load() {
  loading.value = true
  try {
    logs.value = await api(`/api/admin/audit?limit=${limit.value}`)
  } catch (err) {
    error.value = err?.message || '加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="admin-page">
    <header class="admin-page-head">
      <div>
        <h1>审计日志</h1>
        <p>登录、密码、密钥和服务变更记录</p>
      </div>
      <div class="admin-card-tools">
        <input
          v-model="query"
          class="admin-search"
          placeholder="搜索操作者、动作、IP…"
        />
        <select v-model.number="limit" class="admin-select" @change="load">
          <option :value="50">最近 50 条</option>
          <option :value="100">最近 100 条</option>
          <option :value="300">最近 300 条</option>
        </select>
      </div>
    </header>

    <p v-if="error" class="admin-alert">{{ error }}</p>

    <section class="admin-card">
      <div v-if="loading" class="admin-empty">加载中…</div>
      <div v-else-if="!filteredLogs.length" class="admin-empty">
        {{ logs.length ? '没有匹配的日志' : '还没有日志' }}
      </div>
      <div v-else class="audit-list">
        <article
          v-for="item in filteredLogs"
          :key="item.created_at + item.action + item.target + item.ip"
          class="audit-item"
        >
          <div class="audit-item-head">
            <code>{{ item.action }}</code>
            <span>{{ item.actor || 'system' }}</span>
            <time>{{ formatTime(item.created_at) }}</time>
          </div>
          <div class="audit-meta">
            <span v-if="item.target">对象：{{ item.target }}</span>
            <span v-if="item.ip">IP：{{ item.ip }}</span>
          </div>
          <p v-if="item.detail" class="audit-detail">{{ item.detail }}</p>
        </article>
      </div>
    </section>
  </div>
</template>
