import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { public: true },
  },
  {
    path: '/',
    component: () => import('@/layouts/MainLayout.vue'),
    children: [
      { path: '', redirect: '/dashboard' },
      { path: 'dashboard', name: 'Dashboard', component: () => import('@/views/Dashboard.vue') },
      { path: 'tenants', name: 'Tenants', component: () => import('@/views/Tenants.vue') },
      { path: 'instances/:tenantId', name: 'Instances', component: () => import('@/views/Instances.vue') },
      { path: 'snipe', name: 'Snipe', component: () => import('@/views/Snipe.vue') },
      { path: 'bills', name: 'Bills', component: () => import('@/views/Bills.vue') },
      { path: 'notify', name: 'Notify', component: () => import('@/views/Notify.vue') },
      { path: 'users', name: 'Users', component: () => import('@/views/Users.vue') },
      { path: 'profile', name: 'Profile', component: () => import('@/views/Profile.vue') },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (!to.meta.public && !auth.token) {
    return '/login'
  }
})

export default router
