<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center gap-3">
      <button class="btn-ghost btn-sm" @click="$router.back()">← 返回</button>
      <h2 class="text-2xl font-bold text-surface-900 dark:text-white">配额查询 — {{ tenantName }}</h2>
    </div>

    <!-- Filters -->
    <div class="card p-4">
      <div class="flex items-center gap-3 flex-wrap">
        <span class="text-sm text-surface-500 shrink-0">区域</span>
        <select v-model="selectedRegion" class="select w-48" @change="onRegionChange">
          <option value="">选择区域</option>
          <option v-for="r in regions" :key="r" :value="r">{{ r }}</option>
        </select>
        <span class="text-sm text-surface-500 shrink-0">服务</span>
        <select v-model="selectedService" class="select w-56">
          <option value="">选择服务</option>
          <option v-for="s in services" :key="s" :value="s">{{ s }}</option>
        </select>
        <button class="btn-primary btn-sm" :disabled="queryLoading" @click="doQuery">
          {{ queryLoading ? '查询中...' : '查询' }}
        </button>
      </div>
    </div>

    <!-- Limits Table -->
    <div class="card">
      <Loading :loading="queryLoading" text="查询配额中..." />
      <div v-if="!queryLoading && limits.length === 0" class="text-center text-surface-400 py-12">
        {{ hasQueried ? '暂无配额数据' : '请选择区域和服务后查询' }}
      </div>
      <div v-if="!queryLoading && limits.length > 0" class="table-container">
        <table class="table">
          <thead>
            <tr>
              <th>配额名称</th>
              <th>描述</th>
              <th>范围</th>
              <th>可用域</th>
              <th>限额</th>
              <th>已用</th>
              <th>可用</th>
              <th>使用率</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(item, idx) in limits" :key="idx">
              <td class="font-medium text-xs">{{ item.limit_name }}</td>
              <td class="text-xs max-w-[200px] truncate" :title="item.description">{{ item.description || '-' }}</td>
              <td><span class="badge-neutral">{{ item.scope_type }}</span></td>
              <td class="text-xs">{{ item.availability_domain || '-' }}</td>
              <td>{{ item.service_limit ?? '-' }}</td>
              <td class="text-amber-600 dark:text-amber-400">{{ item.used ?? '-' }}</td>
              <td class="text-emerald-600 dark:text-emerald-400">{{ item.available ?? '-' }}</td>
              <td class="w-32">
                <div v-if="item.service_limit && item.used != null" class="flex items-center gap-2">
                  <div class="flex-1 h-2 bg-surface-200 dark:bg-surface-700 rounded-full overflow-hidden">
                    <div class="h-full rounded-full transition-all" :class="getProgressColor(item)" :style="{ width: Math.min((item.used / item.service_limit) * 100, 100) + '%' }"></div>
                  </div>
                  <span class="text-xs text-surface-500 w-10 text-right">{{ Math.round((item.used / item.service_limit) * 100) }}%</span>
                </div>
                <span v-else class="text-surface-400 text-xs">-</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import api from '@/api'
import { useToast } from '@/composables/useToast'
import Loading from '@/components/Loading.vue'

const route = useRoute()
const { warning } = useToast()

const tenantId = route.params.tenantId as string
const tenantName = ref('')
const regions = ref<string[]>([])
const selectedRegion = ref('')
const services = ref<string[]>([])
const selectedService = ref('')
const limits = ref<any[]>([])
const queryLoading = ref(false)
const hasQueried = ref(false)

async function loadTenant() {
  try {
    const res = await api.get(`/tenants/${tenantId}`)
    tenantName.value = res.data.name
    regions.value = res.data.region || []
    if (regions.value.length > 0) {
      selectedRegion.value = regions.value[0]
      await loadServices()
    }
  } catch { /* handled by interceptor */ }
}

async function onRegionChange() {
  selectedService.value = ''
  limits.value = []
  hasQueried.value = false
  await loadServices()
}

async function loadServices() {
  if (!selectedRegion.value) return
  try {
    const res = await api.get(`/limits/${tenantId}/services`, { params: { region: selectedRegion.value } })
    services.value = res.data
    if (services.value.length > 0) {
      selectedService.value = services.value.includes('compute') ? 'compute' : services.value[0]
    }
  } catch { /* handled by interceptor */ }
}

async function doQuery() {
  if (!selectedRegion.value) { warning('请选择区域'); return }
  if (!selectedService.value) { warning('请选择服务'); return }
  queryLoading.value = true
  hasQueried.value = true
  try {
    const res = await api.get(`/limits/${tenantId}/query`, {
      params: { region: selectedRegion.value, service_name: selectedService.value }
    })
    limits.value = res.data.items || res.data
  } catch { /* handled by interceptor */ } finally { queryLoading.value = false }
}

function getProgressColor(item: any) {
  if (!item.service_limit || item.used == null) return 'bg-surface-400'
  const pct = (item.used / item.service_limit) * 100
  if (pct >= 90) return 'bg-red-500'
  if (pct >= 70) return 'bg-amber-500'
  return 'bg-emerald-500'
}

onMounted(loadTenant)
</script>
