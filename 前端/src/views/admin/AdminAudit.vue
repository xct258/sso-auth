<script setup>
import { onMounted, ref } from 'vue'

import { api } from '@/api/admin'

const logs = ref([])
const loading = ref(true)
const error = ref('')
const limit = ref(100)

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
      <select v-model.number="limit" class="admin-select" @change="load">
        <option :value="50">最近 50 条</option>
        <option :value="100">最近 100 条</option>
        <option :value="300">最近 300 条</option>
      </select>
    </header>

    <p v-if="error" class="admin-alert">{{ error }}</p>

    <section class="admin-card">
      <div class="table-wrap">
        <table class="admin-table">
          <thead>
            <tr>
              <th>时间</th>
              <th>操作者</th>
              <th>动作</th>
              <th>对象</th>
              <th>IP</th>
              <th>详情</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in logs" :key="item.created_at + item.action + item.target + item.ip">
              <td>{{ formatTime(item.created_at) }}</td>
              <td>{{ item.actor || '-' }}</td>
              <td><code>{{ item.action }}</code></td>
              <td>{{ item.target || '-' }}</td>
              <td>{{ item.ip || '-' }}</td>
              <td class="admin-detail">{{ item.detail || '-' }}</td>
            </tr>
            <tr v-if="!loading && !logs.length">
              <td colspan="6" class="admin-empty">还没有日志</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>
