<template>
  <div class="space-y-6">
    <div class="flex items-center gap-3">
      <button class="btn-ghost btn-sm" @click="$router.back()">← 返回</button>
      <h2 class="text-2xl font-bold text-surface-900 dark:text-white">流量统计 — {{ tenantName }}</h2>
    </div>

    <!-- Query conditions -->
    <div class="card p-5 space-y-4">
      <div class="flex items-center gap-4 flex-wrap">
        <div>
          <label class="label">区域</label>
          <select v-model="selectedRegion" class="select w-52" @change="onRegionChange">
            <option v-for="r in regionOptions" :key="r.value" :value="r.value">{{ r.label }}</option>
          </select>
        </div>
        <div>
          <label class="label">实例</label>
          <div class="relative">
            <select v-model="selectedInstance" class="select w-60" @change="onInstanceChange" :disabled="instanceLoading">
              <option v-if="instanceLoading" value="">加载中...</option>
              <option v-for="i in instanceOptions" :key="i.value" :value="i.value">{{ i.label }}</option>
            </select>
            <div v-if="instanceLoading" class="absolute right-8 top-1/2 -translate-y-1/2">
              <div class="w-4 h-4 border-2 border-primary-200 border-t-primary-600 rounded-full animate-spin"></div>
            </div>
          </div>
        </div>
        <div>
          <label class="label">VNIC</label>
          <div class="relative">
            <select v-model="selectedVnic" class="select w-72" :disabled="vnicLoading">
              <option v-if="vnicLoading" value="">加载中...</option>
              <option v-for="v in vnicOptions" :key="v.value" :value="v.value">{{ v.label }}</option>
            </select>
            <div v-if="vnicLoading" class="absolute right-8 top-1/2 -translate-y-1/2">
              <div class="w-4 h-4 border-2 border-primary-200 border-t-primary-600 rounded-full animate-spin"></div>
            </div>
          </div>
        </div>
      </div>
      <div class="flex items-center gap-4 flex-wrap">
        <div>
          <label class="label">开始时间</label>
          <input v-model="beginTime" type="datetime-local" class="input w-52" />
        </div>
        <div>
          <label class="label">结束时间</label>
          <input v-model="endTime" type="datetime-local" class="input w-52" />
        </div>
        <div class="pt-5 flex items-center gap-2 flex-wrap">
          <button v-for="s in timeShortcuts" :key="s.label" class="btn-ghost btn-sm" @click="applyShortcut(s)">{{ s.label }}</button>
          <button class="btn-primary" :disabled="chartLoading" @click="loadTrafficData">
            {{ chartLoading ? '加载中...' : '查询流量' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Summary cards -->
    <div v-if="trafficSummary.instance_count > 0" class="grid grid-cols-3 gap-4">
      <div class="card p-5 text-center">
        <div class="text-sm text-surface-500 mb-1">实例数量</div>
        <div class="text-2xl font-bold text-surface-900 dark:text-white">{{ trafficSummary.instance_count }}</div>
      </div>
      <div class="card p-5 text-center">
        <div class="text-sm text-surface-500 mb-1">当月入站流量</div>
        <div class="text-2xl font-bold text-primary-600 dark:text-primary-400">{{ trafficSummary.inbound_traffic }}</div>
      </div>
      <div class="card p-5 text-center">
        <div class="text-sm text-surface-500 mb-1">当月出站流量</div>
        <div class="text-2xl font-bold text-emerald-600 dark:text-emerald-400">{{ trafficSummary.outbound_traffic }}</div>
      </div>
    </div>

    <!-- Chart -->
    <div class="card p-5">
      <div v-if="!chartData" class="text-center py-16 text-surface-400">
        请选择 VNIC 并点击「查询流量」查看图表
      </div>
      <div v-if="chartData" class="h-[400px]">
        <Line :data="chartData" :options="chartOptions" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useToast } from '@/composables/useToast'
import { useThemeStore } from '@/stores/theme'
import { Line } from 'vue-chartjs'
import { Chart as ChartJS, CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend, Filler } from 'chart.js'
import api from '@/api'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend, Filler)

const route = useRoute()
const theme = useThemeStore()
const { warning } = useToast()
const tenantId = route.params.tenantId
const tenantName = ref('')

const regionOptions = ref<{label: string, value: string}[]>([])
const selectedRegion = ref('')
const instanceOptions = ref<{label: string, value: string}[]>([])
const selectedInstance = ref('')
const vnicOptions = ref<{label: string, value: string}[]>([])
const selectedVnic = ref('')
const chartLoading = ref(false)
const instanceLoading = ref(false)
const vnicLoading = ref(false)
const chartData = ref<any>(null)

const trafficSummary = reactive({ instance_count: 0, inbound_traffic: '0 B', outbound_traffic: '0 B' })

const now = new Date()
const monthStart = new Date(now.getFullYear(), now.getMonth(), 1)
const beginTime = ref(monthStart.toISOString().slice(0, 16))
const endTime = ref(now.toISOString().slice(0, 16))

const timeShortcuts = [
  { label: '最近1小时', offset: 3600000 },
  { label: '最近6小时', offset: 6 * 3600000 },
  { label: '最近24小时', offset: 24 * 3600000 },
  { label: '最近7天', offset: 7 * 24 * 3600000 },
  { label: '本月', offset: 0 },
]

function applyShortcut(s: { label: string; offset: number }) {
  const e = new Date()
  if (s.offset === 0) {
    // 本月
    beginTime.value = new Date(e.getFullYear(), e.getMonth(), 1).toISOString().slice(0, 16)
  } else {
    beginTime.value = new Date(e.getTime() - s.offset).toISOString().slice(0, 16)
  }
  endTime.value = e.toISOString().slice(0, 16)
}

const chartOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { labels: { color: theme.isDark ? '#94a3b8' : '#64748b' } } },
  scales: {
    x: { grid: { color: theme.isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)' }, ticks: { color: theme.isDark ? '#94a3b8' : '#64748b', maxRotation: 30 } },
    y: { grid: { color: theme.isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)' }, ticks: { color: theme.isDark ? '#94a3b8' : '#64748b' }, title: { display: true, text: 'GB', color: theme.isDark ? '#94a3b8' : '#64748b' } },
  },
}))

async function loadTenant() {
  const res = await api.get(`/tenants/${tenantId}`)
  tenantName.value = res.data.name
}

async function loadConditions() {
  const res = await api.get(`/traffic/${tenantId}/conditions`)
  regionOptions.value = res.data.region_options
  if (regionOptions.value.length > 0) {
    selectedRegion.value = regionOptions.value[0].value
    await loadInstances()
  }
}

async function onRegionChange() {
  selectedInstance.value = ''; selectedVnic.value = ''; vnicOptions.value = []; chartData.value = null
  await loadInstances()
}

async function loadInstances() {
  if (!selectedRegion.value) return
  instanceLoading.value = true
  try {
    const res = await api.get(`/traffic/${tenantId}/instances`, { params: { region: selectedRegion.value } })
    instanceOptions.value = res.data.instances
    trafficSummary.instance_count = res.data.instance_count
    trafficSummary.inbound_traffic = res.data.inbound_traffic
    trafficSummary.outbound_traffic = res.data.outbound_traffic
    if (instanceOptions.value.length > 0) { selectedInstance.value = instanceOptions.value[0].value; await loadVnics() }
  } finally { instanceLoading.value = false }
}

async function onInstanceChange() { selectedVnic.value = ''; chartData.value = null; await loadVnics() }

async function loadVnics() {
  if (!selectedRegion.value || !selectedInstance.value) return
  vnicLoading.value = true
  try {
    const res = await api.get(`/traffic/${tenantId}/vnics`, { params: { region: selectedRegion.value, instance_id: selectedInstance.value } })
    vnicOptions.value = res.data
    if (vnicOptions.value.length > 0) selectedVnic.value = vnicOptions.value[0].value
  } finally { vnicLoading.value = false }
}

async function loadTrafficData() {
  if (!selectedVnic.value) { warning('请先选择 VNIC'); return }
  chartLoading.value = true
  try {
    const res = await api.post(`/traffic/${tenantId}/data`, {
      region: selectedRegion.value,
      vnic_id: selectedVnic.value,
      begin_time: new Date(beginTime.value).toISOString(),
      end_time: new Date(endTime.value).toISOString(),
    })
    const raw = res.data
    if (raw.time.length === 0) { warning('所选时间范围内无流量数据'); chartData.value = null; return }
    chartData.value = {
      labels: raw.time,
      datasets: [
        { label: '入站流量', data: raw.inbound, borderColor: '#6366f1', backgroundColor: 'rgba(99,102,241,0.1)', fill: true, tension: 0.4, pointRadius: 2 },
        { label: '出站流量', data: raw.outbound, borderColor: '#10b981', backgroundColor: 'rgba(16,185,129,0.1)', fill: true, tension: 0.4, pointRadius: 2 },
      ],
    }
  } finally { chartLoading.value = false }
}

onMounted(async () => { await loadTenant(); await loadConditions() })
</script>
