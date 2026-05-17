<template>
  <div class="space-y-6">
    <h2 class="text-2xl font-bold text-surface-900 dark:text-white">账单监控</h2>

    <!-- Selector -->
    <div class="card p-5">
      <div class="flex items-center gap-4">
        <div>
          <label class="label">选择云账户</label>
          <select v-model="selectedTenant" class="select w-52" @change="loadBill">
            <option :value="null" disabled>请选择</option>
            <option v-for="t in tenants" :key="t.id" :value="t.id">{{ t.name }}</option>
          </select>
        </div>
        <div class="pt-5">
          <button class="btn-primary" :disabled="!selectedTenant || loading" @click="loadBill">
            {{ loading ? '加载中...' : '拉取账单' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Bill data -->
    <template v-if="billData">
      <div class="grid grid-cols-4 gap-4">
        <!-- Total card -->
        <div class="card p-6">
          <div class="flex items-center gap-4">
            <div class="w-12 h-12 rounded-xl bg-amber-100 dark:bg-amber-900/30 flex items-center justify-center">
              <svg class="w-6 h-6 text-amber-600 dark:text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" />
              </svg>
            </div>
            <div>
              <div class="text-2xl font-bold text-amber-600 dark:text-amber-400">¥ {{ billData.total_cny }}</div>
              <div class="text-sm text-surface-500">本月总消费 (CNY)</div>
            </div>
          </div>
        </div>

        <!-- Chart -->
        <div class="col-span-3 card p-5">
          <h3 class="font-semibold text-surface-900 dark:text-white mb-4">每日消费趋势</h3>
          <div class="h-[240px]">
            <Line v-if="chartData" :data="chartData" :options="chartOptions" />
          </div>
        </div>
      </div>

      <!-- Detail table -->
      <div class="card">
        <div class="px-5 py-4 border-b border-surface-200 dark:border-surface-700">
          <h3 class="font-semibold text-surface-900 dark:text-white">账单明细</h3>
        </div>
        <div class="table-container">
          <table class="table">
            <thead>
              <tr>
                <th>开始时间</th>
                <th>结束时间</th>
                <th>原始货币</th>
                <th>消费 (CNY)</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(item, idx) in billData.items" :key="idx">
                <td class="text-xs">{{ item.start_time }}</td>
                <td class="text-xs">{{ item.end_time }}</td>
                <td>{{ item.currency }}</td>
                <td class="font-semibold text-amber-600 dark:text-amber-400">¥ {{ item.amount_cny }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Line } from 'vue-chartjs'
import { Chart as ChartJS, CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend, Filler } from 'chart.js'
import api from '@/api'
import type { Tenant, BillData } from '@/types'
import { useThemeStore } from '@/stores/theme'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend, Filler)

const theme = useThemeStore()
const tenants = ref<Tenant[]>([])
const selectedTenant = ref<number | null>(null)
const billData = ref<BillData | null>(null)
const loading = ref(false)

const chartData = computed(() => {
  if (!billData.value) return null
  const items = billData.value.items
  return {
    labels: items.map(i => i.end_time.split('T')[0].split(' ')[0]),
    datasets: [{
      label: '消费(CNY)',
      data: items.map(i => i.amount_cny),
      borderColor: '#f59e0b',
      backgroundColor: 'rgba(245, 158, 11, 0.1)',
      fill: true,
      tension: 0.4,
      pointRadius: 3,
      pointHoverRadius: 6,
    }],
  }
})

const chartOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { display: false } },
  scales: {
    x: {
      grid: { color: theme.isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)' },
      ticks: { color: theme.isDark ? '#94a3b8' : '#64748b', maxRotation: 45 },
    },
    y: {
      grid: { color: theme.isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)' },
      ticks: { color: theme.isDark ? '#94a3b8' : '#64748b' },
    },
  },
}))

async function loadTenants() {
  const res = await api.get('/tenants')
  tenants.value = res.data
}

async function loadBill() {
  if (!selectedTenant.value) return
  loading.value = true
  try {
    const res = await api.get(`/bills/${selectedTenant.value}/current`)
    billData.value = res.data
  } finally {
    loading.value = false
  }
}

onMounted(loadTenants)
</script>
