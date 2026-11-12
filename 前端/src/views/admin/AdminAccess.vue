<script setup>
import { computed, onMounted, reactive, ref } from 'vue'

import ConfirmDialog from '@/components/ConfirmDialog.vue'
import { api } from '@/api/admin'
import { notify } from '@/composables/useToast'

const domains = ref([])
const services = ref([])
const selectedDomainId = ref(null)
const loading = ref(true)

const showServiceForm = ref(false)
const editingService = ref(null)
const savingService = ref(false)
const showDomainForm = ref(false)
const editingDomain = ref(null)
const savingDomain = ref(false)
const secretInfo = ref(null)
const configInfo = ref(null)
const confirmOpen = ref(false)
const confirmData = ref(null)

function askConfirm(data) {
  confirmData.value = data
  confirmOpen.value = true
}

async function runConfirm() {
  const action = confirmData.value?.action
  confirmOpen.value = false
  if (action) await action()
  confirmData.value = null
}

const serviceForm = reactive({
  domain_id: null,
  name: '',
  slug: '',
  public_url: '',
  password: '',
  auth_mode: '',
  basic_auth_enabled: false,
  basic_username: '',
  basic_password: '',
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
const serviceQuery = ref('')
const filteredServices = computed(() => {
  const query = serviceQuery.value.trim().toLowerCase()
  if (!query) return domainServices.value
  return domainServices.value.filter((item) =>
    [item.name, item.slug, item.auth_mode, item.cookie_name]
      .join(' ')
      .toLowerCase()
      .includes(query),
  )
})

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
    auth_mode: '',
    basic_auth_enabled: false,
    basic_username: '',
    basic_password: '',
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
    notify(err?.message || '加载失败', 'error')
  } finally {
    loading.value = false
  }
}

function openCreateService() {
  resetServiceForm()
  showServiceForm.value = true
  showDomainForm.value = false
}

function openEditService(item) {
  Object.assign(serviceForm, {
    domain_id: item.domain_id,
    name: item.name,
    slug: item.slug,
    public_url: item.public_url,
    password: '',
    auth_mode: item.auth_mode || 'npm',
    basic_auth_enabled: !!item.basic_auth,
    basic_username: item.basic_username || '',
    basic_password: '',
    session_days: item.session_days,
    enabled: !!item.enabled,
    notes: item.notes,
  })
  editingService.value = item
  showServiceForm.value = true
  showDomainForm.value = false
}

async function saveService() {
  if (!serviceForm.auth_mode) {
    notify('请选择接入方式：NPM 或业务代码', 'error')
    return
  }
  savingService.value = true
  try {
    if (editingService.value) {
      await api(`/api/admin/services/${editingService.value.id}`, {
        method: 'PUT',
        body: JSON.stringify({
          name: serviceForm.name,
          public_url: serviceForm.public_url,
          auth_mode: serviceForm.auth_mode,
          basic_auth_enabled: serviceForm.basic_auth_enabled,
          basic_username: serviceForm.basic_username,
          basic_password: serviceForm.basic_password,
          session_days: Number(serviceForm.session_days),
          enabled: serviceForm.enabled,
          notes: serviceForm.notes,
        }),
      })
      notify('服务已更新')
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
        cookie_name: data.cookie_name,
      }
    }
    showServiceForm.value = false
    resetServiceForm()
    await load()
  } catch (err) {
    notify(err?.message || '保存失败', 'error')
  } finally {
    savingService.value = false
  }
}

function resetPassword(item) {
  askConfirm({
    title: '重置登录密码',
    message: `确定重置 ${item.name} 的登录密码？旧密码会立即失效。`,
    confirmText: '重置',
    action: async () => {
      try {
        const data = await api(`/api/admin/services/${item.id}/reset-password`, {
          method: 'POST',
          body: JSON.stringify({}),
        })
        secretInfo.value = { title: '密码已重置', password: data.password }
        await load()
      } catch (err) {
        notify(err?.message || '重置失败', 'error')
      }
    },
  })
}

async function viewPassword(item) {
  try {
    const data = await api(`/api/admin/services/${item.id}/password`)
    secretInfo.value = data.stored
      ? { title: '当前密码', password: data.password }
      : {
          title: '当前密码',
          empty: '该服务密码没有保存密文，请重置后查看。',
        }
  } catch (err) {
    notify(err?.message || '读取密码失败', 'error')
  }
}

function revoke(item) {
  askConfirm({
    title: '强制下线',
    message: `强制 ${item.name} 的所有用户下线？用户下一次访问时需要重新登录。`,
    confirmText: '下线',
    action: async () => {
      try {
        await api(`/api/admin/services/${item.id}/revoke`, { method: 'POST' })
        notify('已强制下线')
        await load()
      } catch (err) {
        notify(err?.message || '操作失败', 'error')
      }
    },
  })
}

function removeService(item) {
  askConfirm({
    title: '删除服务',
    message: `确定删除服务 ${item.name}？该服务的登录记录和配置会一起删除。`,
    confirmText: '删除',
    danger: true,
    action: async () => {
      try {
        await api(`/api/admin/services/${item.id}`, { method: 'DELETE' })
        notify('服务已删除')
        await load()
      } catch (err) {
        notify(err?.message || '删除失败', 'error')
      }
    },
  })
}

async function showConfig(item) {
  try {
    configInfo.value = await api(`/api/admin/services/${item.id}/config`)
  } catch (err) {
    notify(err?.message || '加载配置失败', 'error')
  }
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
}

async function saveDomain() {
  if (!editingDomain.value) return
  savingDomain.value = true
  try {
    await api(`/api/admin/domains/${editingDomain.value.id}`, {
      method: 'PUT',
      body: JSON.stringify(domainForm),
    })
    notify('登录域名已更新')
    showDomainForm.value = false
    resetDomainForm()
    await load()
  } catch (err) {
    notify(err?.message || '保存失败', 'error')
  } finally {
    savingDomain.value = false
  }
}

async function copy(text) {
  try {
    await navigator.clipboard.writeText(text)
    notify('已复制')
  } catch (_) {
    notify('复制失败，请手动选择复制', 'error')
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
        <button class="admin-btn primary" type="button" @click="openCreateService">
          添加服务
        </button>
      </div>
    </header>


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
          <button class="admin-btn ghost" type="button" @click="openEditDomain(selectedDomain)">
            登录域名设置
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

    <Transition name="admin-modal">
    <div
      v-if="showDomainForm"
      class="admin-modal-backdrop"
      @click.self="showDomainForm = false"
    >
      <div class="admin-modal wide">
      <header class="admin-card-head">
        <h2>登录域名设置</h2>
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
      </div>
    </div>
    </Transition>

    <Transition name="admin-modal">
    <div
      v-if="showServiceForm"
      class="admin-modal-backdrop"
      @click.self="showServiceForm = false"
    >
      <div class="admin-modal wide">
      <header class="admin-card-head">
        <h2>{{ editingService ? `编辑 ${editingService.name}` : '添加服务' }}</h2>
        <button class="admin-btn ghost" type="button" @click="showServiceForm = false">
          取消
        </button>
      </header>
      <form class="admin-form" @submit.prevent="saveService">
        <label>
          所属域名
          <input
            :value="selectedDomain ? `${selectedDomain.name} · ${selectedDomain.auth_host}` : ''"
            disabled
          />
        </label>
        <label>
          服务名称
          <input v-model="serviceForm.name" required placeholder="TaskOps" />
        </label>
        <fieldset class="wide auth-mode-field">
          <legend>接入方式</legend>
          <div class="auth-mode-picker">
            <label
              :class="[
                'auth-mode-option',
                { active: serviceForm.auth_mode === 'npm' },
              ]"
            >
              <input
                v-model="serviceForm.auth_mode"
                type="radio"
                value="npm"
                @change="error = ''"
              />
              <span class="auth-mode-copy">
                <strong>NPM 反代</strong>
                <small>无需改代码，适合 Webtop、opencode 等第三方服务</small>
              </span>
              <span class="auth-mode-tag">推荐</span>
            </label>

            <label
              :class="[
                'auth-mode-option',
                { active: serviceForm.auth_mode === 'middleware' },
              ]"
            >
              <input
                v-model="serviceForm.auth_mode"
                type="radio"
                value="middleware"
                @change="error = ''"
              />
              <span class="auth-mode-copy">
                <strong>业务代码</strong>
                <small>在服务里接入 auth.py，适合自己写的应用</small>
              </span>
            </label>
          </div>
        </fieldset>
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
        <label v-if="serviceForm.auth_mode === 'npm'" class="checkbox wide">
          <input v-model="serviceForm.basic_auth_enabled" type="checkbox" />
          上游使用 Basic Auth
        </label>
        <template v-if="serviceForm.auth_mode === 'npm' && serviceForm.basic_auth_enabled">
          <label>
            Basic 用户名
            <input
              v-model="serviceForm.basic_username"
              placeholder="xct258"
              autocomplete="off"
            />
          </label>
          <label>
            Basic 密码
            <input
              v-model="serviceForm.basic_password"
              type="password"
              :placeholder="editingService ? '留空则不修改' : '上游 Basic 密码'"
              autocomplete="new-password"
            />
          </label>
        </template>
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
      </div>
    </div>
    </Transition>

    <section class="admin-card">
      <header class="admin-card-head">
        <h2>{{ selectedDomain ? `${selectedDomain.name} 的服务` : '服务' }}</h2>
        <div class="admin-card-tools">
          <input
            v-model="serviceQuery"
            class="admin-search"
            placeholder="搜索服务…"
          />
          <span class="admin-muted">
            {{ filteredServices.length }} / {{ domainServices.length }}
          </span>
        </div>
      </header>
      <div v-if="loading" class="admin-empty">加载中…</div>
      <div v-else-if="!filteredServices.length" class="admin-empty">
        {{ domainServices.length ? '没有匹配的服务' : '这个域名下还没有服务' }}
      </div>
      <div v-else class="service-grid">
        <article
          v-for="item in filteredServices"
          :key="item.id"
          :class="['service-card', { disabled: !item.enabled }]"
        >
          <header class="service-card-head">
            <div class="min-w-0">
              <h3>{{ item.name }}</h3>
              <p class="admin-sub">
                {{ item.slug }} ·
                {{ item.auth_mode === 'middleware' ? '代码' : 'NPM' }}
                <span v-if="item.basic_auth"> · Basic</span>
              </p>
            </div>
            <span :class="['pill', item.enabled ? 'ok' : 'off']">
              {{ item.enabled ? '启用' : '停用' }}
            </span>
          </header>

          <div class="service-meta">
            <div>
              <span>Cookie / 会话</span>
              <div class="service-cookie-line">
                <code>{{ item.cookie_name }}</code>
                <em>{{ item.session_days }} 天</em>
              </div>
            </div>
            <div>
              <span>最近登录</span>
              <strong>{{ formatTime(item.last_login_at) }}</strong>
            </div>
          </div>

          <footer class="service-actions">
            <button class="admin-btn ghost" type="button" @click="openEditService(item)">
              编辑
            </button>
            <button class="admin-btn ghost" type="button" @click="showConfig(item)">
              配置
            </button>
            <button class="admin-btn ghost" type="button" @click="viewPassword(item)">
              查看密码
            </button>
            <button class="admin-btn ghost" type="button" @click="resetPassword(item)">
              重置密码
            </button>
            <button class="admin-btn ghost" type="button" @click="revoke(item)">
              下线
            </button>
            <button class="admin-btn danger" type="button" @click="removeService(item)">
              删除
            </button>
          </footer>
        </article>
      </div>
    </section>

    <Transition name="admin-modal">
    <div v-if="secretInfo" class="admin-modal-backdrop" @click.self="secretInfo = null">
      <div class="admin-modal">
        <header class="admin-card-head">
          <h2>{{ secretInfo.title }}</h2>
          <button class="admin-btn ghost" type="button" @click="secretInfo = null">
            关闭
          </button>
        </header>
        <p class="admin-muted">请妥善保管；服务密码可以随时在这里重新查看。</p>
        <p v-if="secretInfo.empty" class="admin-muted">{{ secretInfo.empty }}</p>
        <label v-if="secretInfo.password" class="copy-label">
          服务密码
          <span class="copy-row">
            <input :value="secretInfo.password" readonly />
            <button class="admin-btn ghost" type="button" @click="copy(secretInfo.password)">
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
    </Transition>

    <Transition name="admin-modal">
    <div v-if="configInfo" class="admin-modal-backdrop" @click.self="configInfo = null">
      <div class="admin-modal wide">
        <header class="admin-card-head">
          <h2>接入配置</h2>
          <button class="admin-btn ghost" type="button" @click="configInfo = null">
            关闭
          </button>
        </header>
        <p class="admin-muted">
          接入方式：
          {{ configInfo.mode === 'middleware' ? '业务代码（auth.py）' : 'NPM 反代（无需代码）' }}
        </p>
        <template v-if="configInfo.env">
          <label class="copy-label">
            服务环境变量
            <textarea :value="configInfo.env" readonly rows="10"></textarea>
          </label>
          <button class="admin-btn ghost" type="button" @click="copy(configInfo.env)">
            复制环境变量
          </button>
        </template>
        <template v-if="configInfo.nginx">
          <label class="copy-label">
            NPM / nginx 配置
            <textarea :value="configInfo.nginx" readonly rows="16"></textarea>
          </label>
          <button class="admin-btn ghost" type="button" @click="copy(configInfo.nginx)">
            复制 NPM 配置
          </button>
        </template>
      </div>
    </div>
    </Transition>

    <ConfirmDialog
      v-model="confirmOpen"
      :title="confirmData?.title || '确认操作'"
      :message="confirmData?.message || ''"
      :confirm-text="confirmData?.confirmText || '确定'"
      :danger="!!confirmData?.danger"
      @confirm="runConfirm"
    />

  </div>
</template>
