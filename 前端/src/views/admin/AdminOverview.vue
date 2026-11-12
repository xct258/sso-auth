<script setup>
import { onMounted, ref } from 'vue'

import { api } from '@/api/admin'
import { notify } from '@/composables/useToast'

const data = ref({
  domains: 0,
  services: 0,
  enabled_services: 0,
  today_logins: 0,
})

onMounted(async () => {
  try {
    data.value = await api('/api/admin/overview')
  } catch (err) {
    notify(err?.message || '加载失败', 'error')
  }
})
</script>

<template>
  <div class="admin-page">
    <header class="admin-page-head">
      <div>
        <h1>概览</h1>
        <p>域名、服务与今日登录情况</p>
      </div>
      <router-link to="/admin/audit" class="admin-btn ghost">
        查看审计日志
      </router-link>
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

    <section class="admin-card overview-note">
      <div>
        <h2>操作记录</h2>
        <p>登录、密码、密钥和服务变更记录统一放在审计日志中查看。</p>
      </div>
      <router-link to="/admin/audit" class="admin-btn primary">
        打开审计日志
      </router-link>
    </section>
  </div>
</template>
