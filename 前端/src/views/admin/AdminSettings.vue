<script setup>
import { reactive, ref } from 'vue'

import { api } from '@/api/admin'

const form = reactive({
  current_password: '',
  new_password: '',
  confirm: '',
})
const saving = ref(false)
const error = ref('')
const notice = ref('')

async function save() {
  error.value = ''
  notice.value = ''
  if (form.new_password.length < 8) {
    error.value = '新密码至少 8 位'
    return
  }
  if (form.new_password !== form.confirm) {
    error.value = '两次输入的新密码不一致'
    return
  }
  saving.value = true
  try {
    await api('/api/admin/change-password', {
      method: 'POST',
      body: JSON.stringify({
        current_password: form.current_password,
        new_password: form.new_password,
      }),
    })
    notice.value = '管理员密码已更新'
    form.current_password = ''
    form.new_password = ''
    form.confirm = ''
  } catch (err) {
    error.value = err?.message || '保存失败'
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="admin-page">
    <header class="admin-page-head">
      <div>
        <h1>系统设置</h1>
        <p>管理员账号与安全设置</p>
      </div>
    </header>

    <p v-if="error" class="admin-alert">{{ error }}</p>
    <p v-if="notice" class="admin-notice">{{ notice }}</p>

    <section class="admin-card narrow">
      <header class="admin-card-head">
        <h2>修改管理员密码</h2>
      </header>
      <form class="admin-form single" @submit.prevent="save">
        <label>
          当前密码
          <input v-model="form.current_password" type="password" autocomplete="current-password" required />
        </label>
        <label>
          新密码
          <input v-model="form.new_password" type="password" autocomplete="new-password" required />
        </label>
        <label>
          确认新密码
          <input v-model="form.confirm" type="password" autocomplete="new-password" required />
        </label>
        <div class="form-actions">
          <button class="admin-btn primary" type="submit" :disabled="saving">
            {{ saving ? '保存中…' : '保存' }}
          </button>
        </div>
      </form>
    </section>

    <section class="admin-card narrow">
      <header class="admin-card-head">
        <h2>部署提示</h2>
      </header>
      <ul class="admin-list">
        <li>每个服务在「服务管理」中拥有独立密码、Cookie 和签名密钥。</li>
        <li>管理后台 Cookie 不设置父域，不会发送给业务子域。</li>
        <li>主密钥保存在 <code>/data/.master_key</code>，请与数据库一起备份。</li>
        <li>切换登录中心域名时，新增域名记录并更新服务环境变量即可。</li>
      </ul>
    </section>
  </div>
</template>
