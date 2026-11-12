<script setup>
import { onMounted, reactive, ref } from 'vue'

import { api } from '@/api/admin'

const domains = ref([])
const loading = ref(true)
const error = ref('')
const notice = ref('')
const showForm = ref(false)
const editingId = ref(null)
const saving = ref(false)

const form = reactive({
  name: '',
  auth_host: '',
  cookie_domain: '',
  allowed_suffix: '',
  site_name: '统一登录',
  wallpaper_url: '',
  enabled: true,
})

function resetForm() {
  Object.assign(form, {
    name: '',
    auth_host: '',
    cookie_domain: '',
    allowed_suffix: '',
    site_name: '统一登录',
    wallpaper_url: '',
    enabled: true,
  })
  editingId.value = null
}

function openCreate() {
  resetForm()
  showForm.value = true
  error.value = ''
}

function openEdit(item) {
  Object.assign(form, {
    name: item.name,
    auth_host: item.auth_host,
    cookie_domain: item.cookie_domain,
    allowed_suffix: item.allowed_suffix,
    site_name: item.site_name,
    wallpaper_url: item.wallpaper_url,
    enabled: !!item.enabled,
  })
  editingId.value = item.id
  showForm.value = true
  error.value = ''
}

async function load() {
  loading.value = true
  try {
    domains.value = await api('/api/admin/domains')
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
    if (editingId.value) {
      await api(`/api/admin/domains/${editingId.value}`, {
        method: 'PUT',
        body: JSON.stringify(form),
      })
      notice.value = '域名已更新'
    } else {
      await api('/api/admin/domains', {
        method: 'POST',
        body: JSON.stringify(form),
      })
      notice.value = '域名已添加'
    }
    showForm.value = false
    resetForm()
    await load()
  } catch (err) {
    error.value = err?.message || '保存失败'
  } finally {
    saving.value = false
  }
}

async function remove(item) {
  if (!window.confirm(`删除域名 ${item.auth_host}？`)) return
  try {
    await api(`/api/admin/domains/${item.id}`, { method: 'DELETE' })
    notice.value = '域名已删除'
    await load()
  } catch (err) {
    error.value = err?.message || '删除失败'
  }
}

onMounted(load)
</script>

<template>
  <div class="admin-page">
    <header class="admin-page-head">
      <div>
        <h1>域名管理</h1>
        <p>每个域名对应一个 auth 主机和 Cookie 父域</p>
      </div>
      <button class="admin-btn primary" type="button" @click="openCreate">
        添加域名
      </button>
    </header>

    <p v-if="error" class="admin-alert">{{ error }}</p>
    <p v-if="notice" class="admin-notice">{{ notice }}</p>

    <section v-if="showForm" class="admin-card">
      <header class="admin-card-head">
        <h2>{{ editingId ? '编辑域名' : '添加域名' }}</h2>
        <button class="admin-btn ghost" type="button" @click="showForm = false">
          取消
        </button>
      </header>
      <form class="admin-form" @submit.prevent="save">
        <label>
          名称
          <input v-model="form.name" required placeholder="o1-1" />
        </label>
        <label>
          登录主机名
          <input
            v-model="form.auth_host"
            required
            placeholder="auth.o1-1.xct258.top"
          />
        </label>
        <label>
          Cookie 父域
          <input v-model="form.cookie_domain" placeholder=".o1-1.xct258.top" />
        </label>
        <label>
          允许跳转后缀
          <input
            v-model="form.allowed_suffix"
            placeholder="留空则同 Cookie 父域"
          />
        </label>
        <label>
          登录页标题
          <input v-model="form.site_name" placeholder="统一登录" />
        </label>
        <label class="wide">
          壁纸地址
          <input
            v-model="form.wallpaper_url"
            placeholder="https://random-image.xct258.top/"
          />
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
              <th>名称</th>
              <th>登录主机</th>
              <th>Cookie 父域</th>
              <th>服务数</th>
              <th>状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in domains" :key="item.id">
              <td>{{ item.name }}</td>
              <td><code>{{ item.auth_host }}</code></td>
              <td><code>{{ item.cookie_domain || '-' }}</code></td>
              <td>{{ item.service_count }}</td>
              <td>
                <span :class="['pill', item.enabled ? 'ok' : 'off']">
                  {{ item.enabled ? '启用' : '停用' }}
                </span>
              </td>
              <td class="row-actions">
                <button class="admin-btn ghost" type="button" @click="openEdit(item)">
                  编辑
                </button>
                <button class="admin-btn danger" type="button" @click="remove(item)">
                  删除
                </button>
              </td>
            </tr>
            <tr v-if="!loading && !domains.length">
              <td colspan="6" class="admin-empty">还没有域名</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>
