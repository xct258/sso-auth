<script setup>
import { reactive, ref } from 'vue'

import { api } from '@/api/admin'
import { notify } from '@/composables/useToast'

const form = reactive({
  current_password: '',
  new_password: '',
  confirm: '',
})
const saving = ref(false)

async function save() {
  if (form.new_password.length < 8) {
    notify('新密码至少 8 位', 'error')
    return
  }
  if (form.new_password !== form.confirm) {
    notify('两次输入的新密码不一致', 'error')
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
    notify('管理员密码已更新')
    form.current_password = ''
    form.new_password = ''
    form.confirm = ''
  } catch (err) {
    notify(err?.message || '保存失败', 'error')
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
        <li>每个服务拥有独立密码和 Cookie；签名密钥只存在 auth-server。</li>
        <li>管理后台 Cookie 不设置父域，不会发送给业务子域。</li>
        <li>主密钥保存在 <code>/data/.master_key</code>，请与数据库一起备份。</li>
        <li>修改登录域名后，需要同步更新业务服务的环境变量。</li>
      </ul>
    </section>
  </div>
</template>
