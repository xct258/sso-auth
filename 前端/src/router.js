import { createRouter, createWebHistory } from 'vue-router'

import { adminStatus } from '@/api/admin'
import LoginView from '@/views/LoginView.vue'
import AdminLoginView from '@/views/AdminLoginView.vue'
import AdminLayout from '@/views/admin/AdminLayout.vue'
import AdminOverview from '@/views/admin/AdminOverview.vue'
import AdminServices from '@/views/admin/AdminServices.vue'
import AdminDomains from '@/views/admin/AdminDomains.vue'
import AdminAudit from '@/views/admin/AdminAudit.vue'
import AdminSettings from '@/views/admin/AdminSettings.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'login', component: LoginView },
    { path: '/login', name: 'login-explicit', component: LoginView },
    { path: '/admin/login', name: 'admin-login', component: AdminLoginView },
    {
      path: '/admin',
      component: AdminLayout,
      meta: { admin: true },
      children: [
        { path: '', name: 'admin-overview', component: AdminOverview },
        { path: 'services', name: 'admin-services', component: AdminServices },
        { path: 'domains', name: 'admin-domains', component: AdminDomains },
        { path: 'audit', name: 'admin-audit', component: AdminAudit },
        { path: 'settings', name: 'admin-settings', component: AdminSettings },
      ],
    },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

router.beforeEach(async (to) => {
  if (to.meta.admin) {
    const status = await adminStatus()
    if (!status.authenticated) {
      return {
        name: 'admin-login',
        query: { next: to.fullPath },
      }
    }
  }
  if (to.name === 'admin-login') {
    const status = await adminStatus()
    if (status.authenticated) return { name: 'admin-overview' }
  }
  return true
})

router.afterEach((to) => {
  const adminMode = to.path.startsWith('/admin') && to.name !== 'admin-login'
  document.body.classList.toggle('admin-mode', adminMode)
})

export default router
