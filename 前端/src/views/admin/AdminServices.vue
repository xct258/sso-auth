<script setup>
import { onMounted, reactive, ref } from 'vue'

import { api } from '@/api/admin'

const services = ref([])
const domains = ref([])
const loading = ref(true)
const error = ref('')
const notice = ref('')
const showForm = ref(false)
const editing = ref(null)
const saving = ref(false)
const secretInfo = ref(null)
const configInfo = ref(null)

const form = reactive({
  domain_id: null,
  name: '',
  slug: '',
  public_url: '',
  password: '',
  session_days: 7,
  enabled: true,
  notes: '',
})

function resetForm() {
  Object.assign(form, {
    domain_id: domains.value[0]?.id ?? null,
    name: '',
    slug: '',
    public_url: '',
    password: '',
    session_days: 7,
    enabled: true,
    notes: '',
  })
  editing.value = null
}

function openCreate() {
  resetForm()
  showForm.value = true
  error.value = ''
  notice.value = ''
}

function openEdit(item) {
  Object.assign(form, {
    domain_id: item.domain_id,
    name: item.name,
    slug: item.slug,
    public_url: item.public_url,
    password: '',
    session_days: item.session_days,
    enabled: !!item.enabled,
    notes: item.notes,
  })
  editing.value = item
  showForm.value = true
  error.value = ''
  notice.value = ''
}

function formatTime(value) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString()
}

async function load() {
  loading.value = true
  try {
    ;[services.value, domains.value] = await Promise.all([
      api('/api/admin/services'),
      api('/api/admin/domains'),
    ])
    if (!form.domain_id && domains.value.length) {
      form.domain_id = domains.value[0].id
    }
  } catch (err) {
    error.value = err?.message || '加载失败'
  } finally {
    loading.value = false
  }
}

async function save() {
  saving.value = true
  error.value = ''
  notice.value = ''
  try {
    if (editing.value) {
      await api(`/api/admin/services/${editing.value.id}`, {
        method: 'PUT',
        body: JSON.stringify({
          name: form.name,
          public_url: form.public_url,
          session_days: Number(form.session_days),
          enabled: form.enabled,
          notes: form.notes,
        }),
      })
      notice.value = '服务已更新'
      showForm.value = false
    } else {
      const data = await api('/api/admin/services', {
        method: 'POST',
        body: JSON.stringify({
          ...form,
          session_days: Number(form.session_days),
        }),
      })
      secretInfo.value = {
        title: '服务创建成功',
        password: data.password,
        secret: data.secret,
        cookie_name: data.cookie_name,
        service: data.service,
      }
      showForm.value = false
    }
    resetForm()
    await load()
  } catch (err) {
    error.value = err?.message || '保存失败'
  } finally {
    saving.value = false
  }
}

async function resetPassword(item) {
  if (!window.confirm(`重置 ${item.name} 的登录密码？`)) return
  try {
    const data = await api(`/api/admin/services/${item.id}/reset-password`, {
      method: 'POST',
      body: JSON.stringify({}),
    })
    secretInfo.value = {
      title: '密码已重置',
      password: data.password,
      service: item,
    }
    await load()
  } catch (err) {
    error.value = err?.message || '重置失败'
  }
}

async function rotateSecret(item) {
  if (!window.confirm(`轮换 ${item.name} 的签名密钥？旧会话会立即失效。`)) return
  try {
    const data = await api(`/api/admin/services/${item.id}/rotate-secret`, {
      method: 'POST',
    })
    secretInfo.value = {
      title: '密钥已轮换',
      secret: data.secret,
      service: item,
    }
    await load()
  } catch (err) {
    error.value = err?.message || '轮换失败'
  }
}

async function revoke(item) {
  if (!window.confirm(`强制 ${item.name} 的所有用户下线？`)) return
  try {
    await api(`/api/admin/services/${item.id}/revoke`, { method: 'POST' })
    notice.value = '已强制下线'
    await load()
  } catch (err) {
    error.value = err?.message || '操作失败'
  }
}

async function remove(item) {
  if (!window.confirm(`删除服务 ${item.name}？`)) return
  try {
    await api(`/api/admin/services/${item.id}`, { method: 'DELETE' })
    notice.value = '服务已删除'
    await load()
  } catch (err) {
    error.value = err?.message || '删除失败'
  }
}

async function showConfig(item) {
  try {
    configInfo.value = await api(`/api/admin/services/${item.id}/config`)
  } catch (err) {
    error.value = err?.message || '加载配置失败'
  }
}

async function copy(text) {
  try {
    await navigator.clipboard.writeText(text)
    notice.value = '已复制'
  } catch (_) {
    notice.value = '复制失败，请手动选择复制'
  }
}

onMounted(load)
</script>

<template>
  <div class="admin-page">
    <header class="admin-page-head">
      <div>
        <h1>服务管理</h1>
        <p>每个服务独立密码、Cookie 和签名密钥</p>
      </div>
      <button class="admin-btn primary" type="button" @click="openCreate">
        添加服务
      </button>
    </header>

    <p v-if="error" class="admin-alert">{{ error }}</p>
    <p v-if="notice" class="admin-notice">{{ notice }}</p>

    <section v-if="showForm" class="admin-card">
      <header class="admin-card-head">
        <h2>{{ editing ? `编辑 ${editing.name}` : '添加服务' }}</h2>
        <button class="admin-btn ghost" type="button" @click="showForm = false">
          取消
        </button>
      </header>
      <form class="admin-form" @submit.prevent="save">
        <label>
          所属域名
          <select v-model="form.domain_id" :disabled="!!editing" required>
            <option v-for="domain in domains" :key="domain.id" :value="domain.id">
              {{ domain.name }} · {{ domain.auth_host }}
            </option>
          </select>
        </label>
        <label>
          服务名称
          <input v-model="form.name" required placeholder="TaskOps" />
        </label>
        <label>
          服务 ID
          <input
            v-model="form.slug"
            :disabled="!!editing"
            required
            placeholder="taskops"
          />
        </label>
        <label>
          公开地址
          <input
            v-model="form.public_url"
            placeholder="https://2-cfyx.o1-1.xct258.top"
          />
        </label>
        <label v-if="!editing">
          登录密码
          <input
            v-model="form.password"
            placeholder="留空自动生成"
            autocomplete="new-password"
          />
        </label>
        <label>
          会话天数
          <input v-model.number="form.session_days" type="number" min="1" max="365" />
        </label>
        <label class="wide">
          备注
          <input v-model="form.notes" placeholder="可选" />
        </label>
        <label class="checkbox">
          <input v-model="form.enabled" type="checkbox" />
          启用
        </label>
        <div class="form-actions">
          <button class="admin-btn primary" type="submit" :disabled="saving">
            {{ saving ? '保存中…' : '保存' }}
          </button>
        </div>
      </form>
    </section>

    <section class="admin-card">
      <div class="table-wrap">
        <table class="admin-table">
          <thead>
            <tr>
              <th>服务</th>
              <th>域名</th>
              <th>Cookie</th>
              <th>会话</th>
              <th>最近登录</th>
              <th>状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in services" :key="item.id">
              <td>
                <strong>{{ item.name }}</strong>
                <div class="admin-sub">{{ item.slug }}</div>
              </td>
              <td>{{ item.domain_name }}</td>
              <td><code>{{ item.cookie_name }}</code></td>
              <td>{{ item.session_days }} 天</td>
              <td>{{ formatTime(item.last_login_at) }}</td>
              <td>
                <span :class="['pill', item.enabled ? 'ok' : 'off']">
                  {{ item.enabled ? '启用' : '停用' }}
                </span>
              </td>
              <td class="row-actions">
                <button class="admin-btn ghost" type="button" @click="openEdit(item)">
                  编辑
                </button>
                <button class="admin-btn ghost" type="button" @click="showConfig(item)">
                  配置
                </button>
                <button class="admin-btn ghost" type="button" @click="resetPassword(item)">
                  密码
                </button>
                <button class="admin-btn ghost" type="button" @click="rotateSecret(item)">
                  密钥
                </button>
                <button class="admin-btn ghost" type="button" @click="revoke(item)">
                  下线
                </button>
                <button class="admin-btn danger" type="button" @click="remove(item)">
                  删除
                </button>
              </td>
            </tr>
            <tr v-if="!loading && !services.length">
              <td colspan="7" class="admin-empty">还没有服务</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <div v-if="secretInfo" class="admin-modal-backdrop" @click.self="secretInfo = null">
      <div class="admin-modal">
        <header class="admin-card-head">
          <h2>{{ secretInfo.title }}</h2>
          <button class="admin-btn ghost" type="button" @click="secretInfo = null">
            关闭
          </button>
        </header>
        <p class="admin-muted">这些值只在这里显示，请及时复制保存。</p>
        <template v-if="secretInfo.password">
          <label class="copy-label">
            服务密码
            <span class="copy-row">
              <input :value="secretInfo.password" readonly />
              <button class="admin-btn ghost" type="button" @click="copy(secretInfo.password)">
                复制
              </button>
            </span>
          </label>
        </template>
        <template v-if="secretInfo.secret">
          <label class="copy-label">
            签名密钥
            <span class="copy-row">
              <input :value="secretInfo.secret" readonly />
              <button class="admin-btn ghost" type="button" @click="copy(secretInfo.secret)">
                复制
              </button>
            </span>
          </label>
        </template>
        <template v-if="secretInfo.cookie_name">
          <label class="copy-label">
            Cookie 名
            <span class="copy-row">
              <input :value="secretInfo.cookie_name" readonly />
            </span>
          </label>
        </template>
      </div>
    </div>

    <div v-if="configInfo" class="admin-modal-backdrop" @click.self="configInfo = null">
      <div class="admin-modal wide">
        <header class="admin-card-head">
          <h2>接入配置</h2>
          <button class="admin-btn ghost" type="button" @click="configInfo = null">
            关闭
          </button>
        </header>
        <label class="copy-label">
          服务环境变量
          <textarea :value="configInfo.env" readonly rows="10"></textarea>
        </label>
        <button class="admin-btn ghost" type="button" @click="copy(configInfo.env)">
          复制环境变量
        </button>
        <label class="copy-label">
          NPM / nginx 配置
          <textarea :value="configInfo.nginx" readonly rows="16"></textarea>
        </label>
        <button class="admin-btn ghost" type="button" @click="copy(configInfo.nginx)">
          复制 NPM 配置
        </button>
      </div>
    </div>
  </div>
</template>
