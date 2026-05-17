<template>
  <div class="flex h-screen overflow-hidden bg-surface-50 dark:bg-surface-950">
    <!-- Sidebar -->
    <aside
      class="flex flex-col border-r border-surface-200 dark:border-surface-800 bg-white dark:bg-surface-900 transition-all duration-300"
      :class="collapsed ? 'w-16' : 'w-56'"
    >
      <!-- Logo -->
      <div
        class="flex items-center h-16 px-4 border-b border-surface-200 dark:border-surface-800 cursor-pointer gap-3 shrink-0"
        @click="collapsed = !collapsed"
      >
        <div class="w-8 h-8 rounded-lg bg-gradient-to-br from-primary-600 to-accent-500 flex items-center justify-center shrink-0">
          <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 15a4 4 0 004 4h9a5 5 0 10-.1-9.999 5.002 5.002 0 10-9.78 2.096A4.001 4.001 0 003 15z" />
          </svg>
        </div>
        <span v-if="!collapsed" class="text-base font-bold text-surface-900 dark:text-white whitespace-nowrap">
          OCI Manager
        </span>
      </div>

      <!-- Nav -->
      <nav class="flex-1 overflow-y-auto py-3 px-2 space-y-0.5">
        <router-link
          v-for="item in navItems"
          :key="item.path"
          :to="item.path"
          class="nav-item"
          :class="isActive(item.path) ? 'nav-item-active' : 'nav-item-inactive'"
        >
          <component :is="item.icon" class="w-5 h-5 shrink-0" />
          <span v-if="!collapsed" class="truncate">{{ item.label }}</span>
        </router-link>

        <!-- Admin section -->
        <template v-if="auth.isAdmin">
          <div v-if="!collapsed" class="pt-3 pb-1 px-3">
            <span class="text-xs font-medium text-surface-400 dark:text-surface-500 uppercase tracking-wider">管理</span>
          </div>
          <router-link
            to="/users"
            class="nav-item"
            :class="isActive('/users') ? 'nav-item-active' : 'nav-item-inactive'"
          >
            <IconUsers class="w-5 h-5 shrink-0" />
            <span v-if="!collapsed" class="truncate">用户管理</span>
          </router-link>
        </template>
      </nav>
    </aside>

    <!-- Main area -->
    <div class="flex-1 flex flex-col overflow-hidden">
      <!-- Header -->
      <header class="flex items-center justify-between h-16 px-6 border-b border-surface-200 dark:border-surface-800 bg-white dark:bg-surface-900 shrink-0">
        <div class="flex items-center gap-2 text-sm text-surface-500 dark:text-surface-400">
          <router-link to="/dashboard" class="hover:text-primary-600 dark:hover:text-primary-400 transition-colors">首页</router-link>
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" /></svg>
          <span class="text-surface-900 dark:text-surface-100 font-medium">{{ currentTitle }}</span>
        </div>
        <div class="flex items-center gap-3">
          <!-- Theme toggle -->
          <button @click="theme.toggle()" class="p-2 rounded-lg hover:bg-surface-100 dark:hover:bg-surface-800 transition-colors">
            <svg v-if="theme.isDark" class="w-5 h-5 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
            </svg>
            <svg v-else class="w-5 h-5 text-surface-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
            </svg>
          </button>

          <!-- User info -->
          <div class="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-surface-100 dark:bg-surface-800">
            <div class="w-6 h-6 rounded-full bg-gradient-to-br from-primary-500 to-accent-500 flex items-center justify-center">
              <span class="text-xs text-white font-medium">{{ auth.user?.username?.charAt(0).toUpperCase() }}</span>
            </div>
            <span class="text-sm font-medium text-surface-700 dark:text-surface-300">{{ auth.user?.username }}</span>
            <span v-if="auth.isAdmin" class="badge-info text-[10px]">管理员</span>
          </div>

          <!-- Logout -->
          <button @click="handleLogout" class="p-2 rounded-lg hover:bg-red-50 dark:hover:bg-red-950/30 text-surface-500 hover:text-red-600 dark:hover:text-red-400 transition-colors" title="退出登录">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
            </svg>
          </button>
        </div>
      </header>

      <!-- Content -->
      <main class="flex-1 overflow-y-auto p-6">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, h } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores/theme'
import { useModal } from '@/composables/useModal'
import IconUsers from '@/components/icons/IconUsers.vue'

const auth = useAuthStore()
const theme = useThemeStore()
const route = useRoute()
const router = useRouter()
const { confirm } = useModal()
const collapsed = ref(false)

// Nav icons as inline SVG components
const IconDashboard = { render: () => h('svg', { fill: 'none', stroke: 'currentColor', viewBox: '0 0 24 24', class: 'w-5 h-5' }, [h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'stroke-width': '2', d: 'M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zm10 0a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zm10 0a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z' })]) }
const IconTenants = { render: () => h('svg', { fill: 'none', stroke: 'currentColor', viewBox: '0 0 24 24', class: 'w-5 h-5' }, [h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'stroke-width': '2', d: 'M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4' })]) }
const IconSnipe = { render: () => h('svg', { fill: 'none', stroke: 'currentColor', viewBox: '0 0 24 24', class: 'w-5 h-5' }, [h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'stroke-width': '2', d: 'M13 10V3L4 14h7v7l9-11h-7z' })]) }
const IconIpData = { render: () => h('svg', { fill: 'none', stroke: 'currentColor', viewBox: '0 0 24 24', class: 'w-5 h-5' }, [h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'stroke-width': '2', d: 'M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z' }), h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'stroke-width': '2', d: 'M15 11a3 3 0 11-6 0 3 3 0 016 0z' })]) }
const IconCloudflare = { render: () => h('svg', { fill: 'none', stroke: 'currentColor', viewBox: '0 0 24 24', class: 'w-5 h-5' }, [h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'stroke-width': '2', d: 'M3 15a4 4 0 004 4h9a5 5 0 10-.1-9.999 5.002 5.002 0 10-9.78 2.096A4.001 4.001 0 003 15z' })]) }
const IconBills = { render: () => h('svg', { fill: 'none', stroke: 'currentColor', viewBox: '0 0 24 24', class: 'w-5 h-5' }, [h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'stroke-width': '2', d: 'M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z' })]) }
const IconNotify = { render: () => h('svg', { fill: 'none', stroke: 'currentColor', viewBox: '0 0 24 24', class: 'w-5 h-5' }, [h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'stroke-width': '2', d: 'M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9' })]) }
const IconProfile = { render: () => h('svg', { fill: 'none', stroke: 'currentColor', viewBox: '0 0 24 24', class: 'w-5 h-5' }, [h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'stroke-width': '2', d: 'M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z' }), h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'stroke-width': '2', d: 'M15 12a3 3 0 11-6 0 3 3 0 016 0z' })]) }

const navItems = [
  { path: '/dashboard', label: '控制台', icon: IconDashboard },
  { path: '/tenants', label: '云账户管理', icon: IconTenants },
  { path: '/snipe', label: '抢机任务', icon: IconSnipe },
  { path: '/ip-data', label: 'IP 数据', icon: IconIpData },
  { path: '/cloudflare', label: 'Cloudflare DNS', icon: IconCloudflare },
  { path: '/bills', label: '账单监控', icon: IconBills },
  { path: '/notify', label: '通知配置', icon: IconNotify },
  { path: '/profile', label: '个人设置', icon: IconProfile },
]

const titleMap: Record<string, string> = {
  '/dashboard': '控制台',
  '/tenants': '云账户管理',
  '/snipe': '抢机任务',
  '/ip-data': 'IP 数据',
  '/cloudflare': 'Cloudflare DNS',
  '/bills': '账单监控',
  '/notify': '通知配置',
  '/users': '用户管理',
  '/profile': '个人设置',
  '/terminal': 'SSH 终端',
}

const routeNameMap: Record<string, string> = {
  Instances: '实例管理',
  SecurityRules: '安全列表',
  Traffic: '流量统计',
  BootVolumes: '引导卷',
  VcnManage: 'VCN 管理',
  Limits: '配额查询',
  OciUsers: 'OCI 用户',
}

const currentTitle = computed(() => {
  // 先匹配精确路径
  if (titleMap[route.path]) return titleMap[route.path]
  // 再匹配路由名称（带参数的子路由）
  const name = route.name as string
  if (name && routeNameMap[name]) return routeNameMap[name]
  return titleMap[route.path] || route.path
})

function isActive(path: string) {
  return route.path === path || route.path.startsWith(path + '/')
}

async function handleLogout() {
  const ok = await confirm('确认退出登录？', '提示')
  if (ok) {
    auth.logout()
    router.push('/login')
  }
}
</script>

<style scoped>
.nav-item {
  @apply flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200;
}
.nav-item-active {
  @apply bg-primary-50 dark:bg-primary-950/50 text-primary-700 dark:text-primary-300;
}
.nav-item-inactive {
  @apply text-surface-600 dark:text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-800 hover:text-surface-900 dark:hover:text-surface-100;
}
</style>
