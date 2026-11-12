<script setup>
import { computed, onMounted, reactive, ref } from 'vue'

import { api } from '@/api/admin'

const domains = ref([])
const services = ref([])
const selectedDomainId = ref(null)
const loading = ref(true)
const error = ref('')
const notice = ref('')

const showServiceForm = ref(false)
const editingService = ref(null)
const savingService = ref(false)
const showDomainForm = ref(false)
const editingDomain = ref(null)
const savingDomain = ref(false)
const secretInfo = ref(null)
const configInfo = ref(null)

const serviceForm = reactive({
  domain_id: null,
  name: '',
  slug: '',
  public_url: '',
  password: '',
  session_days: 7,
  enabled: true,
  notes: '',
})

const domainForm = reactive({
  name: '',
  auth_host: '',
  cookie_domain: '',
  allowed_suffix: '',
  site_name: '统一登录',
  wallpaper_url: '',
  enabled: true,
})

const selectedDomain = computed(
  () => domains.value.find((item) => item.id === selectedDomainId.value) || null,
)
const domainServices = computed(() =>
  services.value.filter((item) => item.domain_id === selectedDomainId.value),
)

function formatTime(value) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString()
}

function resetServiceForm() {
  Object.assign(serviceForm, {
    domain_id: selectedDomainId.value,
    name: '',
    slug: '',
    public_url: '',
    password: '',
    session_days: 7,
    enabled: true,
    notes: '',
  })
  editingService.value = null
}

function resetDomainForm() {
  Object.assign(domainForm, {
    name: '',
    auth_host: '',
    cookie_domain: '',
    allowed_suffix: '',
    site_name: '统一登录',
    wallpaper_url: '',
    enabled: true,
  })
  editingDomain.value = null
}

async function load() {
  loading.value = true
  try {
    ;[domains.value, services.value] = await Promise.all([
      api('/api/admin/domains'),
      api('/api/admin/services'),
    ])
    if (!domains.value.some((item) => item.id === selectedDomainId.value)) {
      const preferred =
        domains.value.find((item) => item.service_count > 0) ||
        domains.value[0] ||
        null
      selectedDomainId.value = preferred?.id ?? null
    }
    if (!serviceForm.domain_id) serviceForm.domain_id = selectedDomainId.value
  } catch (err) {
    error.value = err?.message || '加载失败'
  } finally {
    loading.value = false
  }
}

function openCreateService() {
  resetServiceForm()
  showServiceForm.value = true
  showDomainForm.value = false
  error.value = ''
  notice.value = ''
}

function openEditService(item) {
  Object.assign(serviceForm, {
    domain_id: item.domain_id,
    name: item.name,
    slug: item.slug,
    public_url: item.public_url,
    password: '',
    session_days: item.session_days,
    enabled: !!item.enabled,
    notes: item.notes,
  })
  editingService.value = item
  showServiceForm.value = true
  showDomainForm.value = false
  error.value = ''
  notice.value = ''
}

async function saveService() {
  savingService.value = true
  error.value = ''
  notice.value = ''
  try {
    if (editingService.value) {
      await api(`/api/admin/services/${editingService.value.id}`, {
        method: 'PUT',
        body: JSON.stringify({
          name: serviceForm.name,
          public_url: serviceForm.public_url,
          session_days: Number(serviceForm.session_days),
          enabled: serviceForm.enabled,
          notes: serviceForm.notes,
        }),
      })
      notice.value = '服务已更新'
    } else {
      const data = await api('/api/admin/services', {
        method: 'POST',
        body: JSON.stringify({
          ...serviceForm,
          domain_id: selectedDomainId.value,
          session_days: Number(serviceForm.session_days),
        }),
      })
      secretInfo.value = {
        title: '服务创建成功',
        password: data.password,
        secret: data.secret,
        cookie_name: data.cookie_name,
      }
    }
    showServiceForm.value = false
    resetServiceForm()
    await load()
  } catch (err) {
    error.value = err?.message || '保存失败'
  } finally {
    savingService.value = false
  }
}

async function resetPassword(item) {
  if (!window.confirm(`重置 ${item.name} 的登录密码？`)) return
  try {
    const data = await api(`/api/admin/services/${item.id}/reset-password`, {
      method: 'POST',
      body: JSON.stringify({}),
    })
    secretInfo.value = { title: '密码已重置', password: data.password }
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
    secretInfo.value = { title: '密钥已轮换', secret: data.secret }
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

async function removeService(item) {
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

function openCreateDomain() {
  resetDomainForm()
  showDomainForm.value = true
  showServiceForm.value = false
  error.value = ''
  notice.value = ''
}

function openEditDomain(item) {
  Object.assign(domainForm, {
    name: item.name,
    auth_host: item.auth_host,
    cookie_domain: item.cookie_domain,
    allowed_suffix: item.allowed_suffix,
    site_name: item.site_name,
    wallpaper_url: item.wallpaper_url,
    enabled: !!item.enabled,
  })
  editingDomain.value = item
  showDomainForm.value = true
  showServiceForm.value = false
  error.value = ''
  notice.value = ''
}

async function saveDomain() {
  savingDomain.value = true
  error.value = ''
  notice.value = ''
  try {
    let saved
    if (editingDomain.value) {
      saved = await api(`/api/admin/domains/${editingDomain.value.id}`, {
        method: 'PUT',
        body: JSON.stringify(domainForm),
      })
      notice.value = '域名已更新'
    } else {
      saved = await api('/api/admin/domains', {
        method: 'POST',
        body: JSON.stringify(domainForm),
      })
      notice.value = '域名已添加'
    }
    showDomainForm.value = false
    resetDomainForm()
    await load()
    if (saved?.id) selectedDomainId.value = saved.id
  } catch (err) {
    error.value = err?.message || '保存失败'
  } finally {
    savingDomain.value = false
  }
}

async function removeDomain(item) {
  if (!window.confirm(`删除域名 ${item.auth_host}？`)) return
  try {
    await api(`/api/admin/domains/${item.id}`, { method: 'DELETE' })
    notice.value = '域名已删除'
    await load()
  } catch (err) {
    error.value = err?.message || '删除失败'
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
        <h1>接入管理</h1>
        <p>登录域名、服务密码和接入配置</p>
      </div>
      <div class="row-actions">
        <button class="admin-btn ghost" type="button" @click="openCreateDomain">
          添加域名
        </button>
        <button class="admin-btn primary" type="button" @click="openCreateService">
          添加服务
        </button>
      </div>
    </header>

    <p v-if="error" class="admin-alert">{{ error }}</p>
    <p v-if="notice" class="admin-notice">{{ notice }}</p>

    <section v-if="selectedDomain" class="admin-card access-domain">
      <div class="access-domain-main">
        <div>
          <span class="admin-sub">当前登录域名</span>
          <h2>{{ selectedDomain.name }}</h2>
          <p class="access-domain-line">
            <code>{{ selectedDomain.auth_host }}</code>
            <span>Cookie <code>{{ selectedDomain.cookie_domain }}</code></span>
          </p>
        </div>
        <div class="row-actions">
          <select
            v-if="domains.length > 1"
            v-model.number="selectedDomainId"
            class="admin-select"
          >
            <option v-for="domain in domains" :key="domain.id" :value="domain.id">
              {{ domain.name }} · {{ domain.auth_host }}
            </option>
          </select>
          <button class="admin-btn ghost" type="button" @click="openEditDomain(selectedDomain)">
            编辑域名
          </button>
          <button
            v-if="selectedDomain.service_count === 0"
            class="admin-btn danger"
            type="button"
            @click="removeDomain(selectedDomain)"
          >
            删除域名
          </button>
        </div>
      </div>
      <div class="access-domain-meta">
        <span>服务 {{ selectedDomain.service_count }}</span>
        <span :class="['pill', selectedDomain.enabled ? 'ok' : 'off']">
          {{ selectedDomain.enabled ? '启用' : '停用' }}
        </span>
      </div>
    </section>

    <section v-if="showDomainForm" class="admin-card">
      <header class="admin-card-head">
        <h2>{{ editingDomain ? '编辑登录域名' : '添加登录域名' }}</h2>
        <button class="admin-btn ghost" type="button" @click="showDomainForm = false">
          取消
        </button>
      </header>
      <form class="admin-form" @submit.prevent="saveDomain">
        <label>
          名称
          <input v-model="domainForm.name" required placeholder="xct258" />
        </label>
        <label>
          登录主机名
          <input v-model="domainForm.auth_host" required placeholder="auth.xct258.top" />
        </label>
        <label>
          Cookie 父域
          <input v-model="domainForm.cookie_domain" placeholder=".xct258.top" />
        </label>
        <label>
          允许跳转后缀
          <input v-model="domainForm.allowed_suffix" placeholder="留空则同 Cookie 父域" />
        </label>
        <label>
          登录页标题
          <input v-model="domainForm.site_name" placeholder="统一登录" />
        </label>
        <label class="wide">
          壁纸地址
          <input v-model="domainForm.wallpaper_url" placeholder="https://random-image.xct258.top/" />
        </label>
        <label class="checkbox">
          <input v-model="domainForm.enabled" type="checkbox" />
          启用
        </label>
        <div class="form-actions">
          <button class="admin-btn primary" type="submit" :disabled="savingDomain">
            {{ savingDomain ? '保存中…' : '保存' }}
          </button>
        </div>
      </form>
    </section>

    <section v-if="showServiceForm" class="admin-card">
      <header class="admin-card-head">
        <h2>{{ editingService ? `编辑 ${editingService.name}` : '添加服务' }}</h2>
        <button class="admin-btn ghost" type="button" @click="showServiceForm = false">
          取消
        </button>
      </header>
      <form class="admin-form" @submit.prevent="saveService">
        <label>
          所属域名
          <select v-model.number="serviceForm.domain_id" disabled>
            <option v-for="domain in domains" :key="domain.id" :value="domain.id">
              {{ domain.name }} · {{ domain.auth_host }}
            </option>
          </select>
        </label>
        <label>
          服务名称
          <input v-model="serviceForm.name" required placeholder="TaskOps" />
        </label>
        <label>
          服务 ID
          <input
            v-model="serviceForm.slug"
            :disabled="!!editingService"
            required
            placeholder="taskops"
          />
        </label>
        <label>
          公开地址
          <input
            v-model="serviceForm.public_url"
            placeholder="https://2-cfyx.o1-1.xct258.top"
          />
        </label>
        <label v-if="!editingService">
          登录密码
          <input
            v-model="serviceForm.password"
            placeholder="留空自动生成"
            autocomplete="new-password"
          />
        </label>
        <label>
          会话天数
          <input v-model.number="serviceForm.session_days" type="number" min="1" max="365" />
        </label>
        <label class="wide">
          备注
          <input v-model="serviceForm.notes" placeholder="可选" />
        </label>
        <label class="checkbox">
          <input v-model="serviceForm.enabled" type="checkbox" />
          启用
        </label>
        <div class="form-actions">
          <button class="admin-btn primary" type="submit" :disabled="savingService">
            {{ savingService ? '保存中…' : '保存' }}
          </button>
        </div>
      </form>
    </section>

    <section class="admin-card">
      <header class="admin-card-head">
        <h2>{{ selectedDomain ? `${selectedDomain.name} 的服务` : '服务' }}</h2>
        <span class="admin-muted">{{ domainServices.length }} 个</span>
      </header>
      <div class="table-wrap">
        <table class="admin-table">
          <thead>
            <tr>
              <th>服务</th>
              <th>Cookie</th>
              <th>会话</th>
              <th>最近登录</th>
              <th>状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in domainServices" :key="item.id">
              <td>
                <strong>{{ item.name }}</strong>
                <div class="admin-sub">{{ item.slug }}</div>
              </td>
              <td><code>{{ item.cookie_name }}</code></td>
              <td>{{ item.session_days }} 天</td>
              <td>{{ formatTime(item.last_login_at) }}</td>
              <td>
                <span :class="['pill', item.enabled ? 'ok' : 'off']">
                  {{ item.enabled ? '启用' : '停用' }}
                </span>
              </td>
              <td class="row-actions">
                <button class="admin-btn ghost" type="button" @click="openEditService(item)">
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
                <button class="admin-btn danger" type="button" @click="removeService(item)">
                  删除
                </button>
              </td>
            </tr>
            <tr v-if="!loading && !domainServices.length">
              <td colspan="6" class="admin-empty">这个域名下还没有服务</td>
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
        <label v-if="secretInfo.password" class="copy-label">
          服务密码
          <span class="copy-row">
            <input :value="secretInfo.password" readonly />
            <button class="admin-btn ghost" type="button" @click="copy(secretInfo.password)">
              复制
            </button>
          </span>
        </label>
        <label v-if="secretInfo.secret" class="copy-label">
          签名密钥
          <span class="copy-row">
            <input :value="secretInfo.secret" readonly />
            <button class="admin-btn ghost" type="button" @click="copy(secretInfo.secret)">
              复制
            </button>
          </span>
        </label>
        <label v-if="secretInfo.cookie_name" class="copy-label">
          Cookie 名
          <span class="copy-row">
            <input :value="secretInfo.cookie_name" readonly />
          </span>
        </label>
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
