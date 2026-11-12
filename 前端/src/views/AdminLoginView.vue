<script setup>
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { adminLogin } from '@/api/admin'

const route = useRoute()
const router = useRouter()

const username = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

const nextPath = computed(() => {
  const raw = String(route.query.next || '')
  return raw.startsWith('/admin') ? raw : '/admin'
})

async function submit() {
  if (loading.value) return
  error.value = ''
  if (!username.value || !password.value) {
    error.value = '请输入用户名和密码'
    return
  }
  loading.value = true
  try {
    await adminLogin(username.value, password.value)
    await router.replace(nextPath.value)
  } catch (err) {
    error.value = err?.message || '登录失败'
    password.value = ''
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <main class="wrap">
    <form class="card" novalidate @submit.prevent="submit">
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
          <h1>管理控制台</h1>
          <p>登录后管理域名与服务</p>
        </div>
      </div>

      <label>用户名</label>
      <input
        v-model="username"
        class="field"
        type="text"
        autocomplete="username"
        autofocus
      />

      <label>管理密码</label>
      <input
        v-model="password"
        class="field"
        type="password"
        autocomplete="current-password"
      />

      <p class="error" role="alert" aria-live="polite">{{ error }}</p>

      <button class="submit" type="submit" :class="{ loading }" :disabled="loading">
        <span class="label">登 录</span>
        <span class="spinner" aria-hidden="true"></span>
      </button>

      <p class="foot">仅管理员可访问</p>
    </form>
  </main>
</template>
