<template>
  <div class="space-y-6">
    <!-- Page header -->
    <div>
      <h2 class="text-2xl font-bold text-surface-900 dark:text-white">控制台</h2>
      <p class="text-surface-500 dark:text-surface-400 mt-1">欢迎回来，{{ auth.user?.username }}</p>
    </div>

    <!-- Stats cards -->
    <div class="grid grid-cols-4 gap-4">
      <div v-for="stat in stats" :key="stat.label" class="card p-5">
        <div class="flex items-center gap-4">
          <div class="w-12 h-12 rounded-xl flex items-center justify-center" :class="stat.bgClass">
            <component :is="stat.icon" class="w-6 h-6" :class="stat.iconClass" />
          </div>
          <div>
            <div class="text-2xl font-bold text-surface-900 dark:text-white">{{ stat.value }}</div>
            <div class="text-sm text-surface-500 dark:text-surface-400">{{ stat.label }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- Content grid -->
    <div class="grid grid-cols-5 gap-6">
      <!-- Snipe tasks -->
      <div class="col-span-3 card">
        <div class="flex items-center justify-between px-5 py-4 border-b border-surface-200 dark:border-surface-700">
          <h3 class="font-semibold text-surface-900 dark:text-white">抢机任务状态</h3>
          <div class="flex items-center gap-2">
            <button class="btn-ghost btn-sm" @click="loadTasks">刷新</button>
            <button class="btn-ghost btn-sm text-primary-600 dark:text-primary-400" @click="$router.push('/snipe')">
              前往抢机任务 →
            </button>
          </div>
        </div>
        <div class="table-container">
          <table class="table">
            <thead>
              <tr>
                <th>租户</th>
                <th>类型</th>
                <th>状态</th>
                <th>尝试次数</th>
                <th>IP</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="task in recentTasks" :key="task.id">
                <td class="font-medium">{{ tenantName(task.tenant_id) }}</td>
                <td>{{ task.shape_name }}</td>
                <td>
                  <span :class="statusBadge(task.status)">{{ task.status }}</span>
                </td>
                <td>{{ task.attempt_count }}</td>
                <td class="font-mono text-xs">{{ task.result_ip || '-' }}</td>
              </tr>
              <tr v-if="recentTasks.length === 0">
                <td colspan="5" class="text-center text-surface-400 py-8">暂无任务</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Tenants -->
      <div class="col-span-2 card">
        <div class="flex items-center justify-between px-5 py-4 border-b border-surface-200 dark:border-surface-700">
          <h3 class="font-semibold text-surface-900 dark:text-white">云账户列表</h3>
        </div>
        <div class="table-container">
          <table class="table">
            <thead>
              <tr>
                <th>名称</th>
                <th>状态</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="t in tenants" :key="t.id">
                <td class="font-medium">{{ t.name }}</td>
                <td>
                  <span :class="t.is_active ? 'badge-success' : 'badge-neutral'">
                    {{ t.is_active ? '启用' : '禁用' }}
                  </span>
                </td>
                <td>
                  <button class="btn-ghost btn-sm" @click="$router.push(`/instances/${t.id}`)">实例</button>
                </td>
              </tr>
              <tr v-if="tenants.length === 0">
                <td colspan="3" class="text-center text-surface-400 py-8">暂无账户</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, h } from 'vue'
import { useAuthStore } from '@/stores/auth'
import api from '@/api'
import type { SnipeTask, Tenant } from '@/types'

const auth = useAuthStore()
const tasks = ref<SnipeTask[]>([])
const tenants = ref<Tenant[]>([])

const recentTasks = computed(() => tasks.value.slice(0, 10))

// Icon components
const IconBuilding = { render: () => h('svg', { fill: 'none', stroke: 'currentColor', viewBox: '0 0 24 24' }, [h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'stroke-width': '2', d: 'M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4' })]) }
const IconBolt = { render: () => h('svg', { fill: 'none', stroke: 'currentColor', viewBox: '0 0 24 24' }, [h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'stroke-width': '2', d: 'M13 10V3L4 14h7v7l9-11h-7z' })]) }
const IconCheck = { render: () => h('svg', { fill: 'none', stroke: 'currentColor', viewBox: '0 0 24 24' }, [h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'stroke-width': '2', d: 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z' })]) }
const IconX = { render: () => h('svg', { fill: 'none', stroke: 'currentColor', viewBox: '0 0 24 24' }, [h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'stroke-width': '2', d: 'M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z' })]) }

const stats = computed(() => [
  { label: '云账户数', value: tenants.value.length, icon: IconBuilding, bgClass: 'bg-primary-100 dark:bg-primary-900/30', iconClass: 'text-primary-600 dark:text-primary-400' },
  { label: '运行中任务', value: tasks.value.filter(t => t.status === 'running').length, icon: IconBolt, bgClass: 'bg-emerald-100 dark:bg-emerald-900/30', iconClass: 'text-emerald-600 dark:text-emerald-400' },
  { label: '成功抢机', value: tasks.value.filter(t => t.status === 'success').length, icon: IconCheck, bgClass: 'bg-amber-100 dark:bg-amber-900/30', iconClass: 'text-amber-600 dark:text-amber-400' },
  { label: '失败任务', value: tasks.value.filter(t => t.status === 'failed').length, icon: IconX, bgClass: 'bg-red-100 dark:bg-red-900/30', iconClass: 'text-red-600 dark:text-red-400' },
])

function statusBadge(s: string) {
  switch (s) {
    case 'running': return 'badge-warning'
    case 'success': return 'badge-success'
    case 'failed': return 'badge-danger'
    case 'stopped': return 'badge-neutral'
    default: return 'badge-info'
  }
}

function tenantName(id: number) {
  return tenants.value.find(t => t.id === id)?.name || String(id)
}

async function loadTasks() {
  const res = await api.get('/snipe')
  tasks.value = res.data
}

async function loadTenants() {
  const res = await api.get('/tenants')
  tenants.value = res.data
}

onMounted(() => {
  loadTasks()
  loadTenants()
  setInterval(loadTasks, 10000)
})
</script>
