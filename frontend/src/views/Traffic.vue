<template>
  <div>
    <div class="page-header">
      <div>
        <el-button text @click="$router.back()"><el-icon><ArrowLeft /></el-icon> 返回</el-button>
        <h2 style="display:inline;margin-left:8px">流量统计 — {{ tenantName }}</h2>
      </div>
    </div>

    <!-- 查询条件 -->
    <el-card shadow="never" style="margin-bottom:16px">
      <el-form :inline="true">
        <el-form-item label="区域">
          <el-select v-model="selectedRegion" placeholder="选择区域" @change="onRegionChange" style="width:220px">
            <el-option v-for="r in regionOptions" :key="r.value" :label="r.label" :value="r.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="实例">
          <el-select v-model="selectedInstance" placeholder="选择实例" @change="onInstanceChange" style="width:260px" :loading="instanceLoading">
            <el-option v-for="i in instanceOptions" :key="i.value" :label="i.label" :value="i.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="VNIC">
          <el-select v-model="selectedVnic" placeholder="选择 VNIC" style="width:300px" :loading="vnicLoading">
            <el-option v-for="v in vnicOptions" :key="v.value" :label="v.label" :value="v.value" />
          </el-select>
        </el-form-item>
      </el-form>
      <el-form :inline="true">
        <el-form-item label="时间范围">
          <el-date-picker
            v-model="timeRange"
            type="datetimerange"
            range-separator="至"
            start-placeholder="开始时间"
            end-placeholder="结束时间"
            :shortcuts="timeShortcuts"
            style="width:380px"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadTrafficData" :loading="chartLoading">
            <el-icon><DataAnalysis /></el-icon> 查询流量
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 流量汇总卡片 -->
    <el-row :gutter="16" style="margin-bottom:16px" v-if="trafficSummary.instance_count > 0">
      <el-col :span="8">
        <el-card shadow="hover" class="summary-card">
          <div class="summary-label">实例数量</div>
          <div class="summary-value">{{ trafficSummary.instance_count }}</div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover" class="summary-card">
          <div class="summary-label">当月入站流量</div>
          <div class="summary-value inbound">{{ trafficSummary.inbound_traffic }}</div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover" class="summary-card">
          <div class="summary-label">当月出站流量</div>
          <div class="summary-value outbound">{{ trafficSummary.outbound_traffic }}</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 流量图表 -->
    <el-card shadow="never" v-loading="chartLoading">
      <div v-if="!chartData" style="text-align:center;padding:60px 0;color:#909399">
        请选择 VNIC 并点击「查询流量」查看图表
      </div>
      <v-chart v-if="chartData" :option="chartOption" style="height:400px;width:100%" autoresize />
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '@/api'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, DataZoomComponent } from 'echarts/components'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent, DataZoomComponent])

const route = useRoute()
const tenantId = route.params.tenantId
const tenantName = ref('')

const regionOptions = ref([])
const selectedRegion = ref('')
const instanceOptions = ref([])
const selectedInstance = ref('')
const instanceLoading = ref(false)
const vnicOptions = ref([])
const selectedVnic = ref('')
const vnicLoading = ref(false)
const chartLoading = ref(false)
const chartData = ref(null)

const trafficSummary = reactive({
  instance_count: 0,
  inbound_traffic: '0 B',
  outbound_traffic: '0 B',
})

// 时间范围
const now = new Date()
const timeRange = ref([
  new Date(now.getTime() - 24 * 60 * 60 * 1000),  // 24小时前
  now,
])

const timeShortcuts = [
  { text: '最近1小时', value: () => { const e = new Date(); return [new Date(e.getTime() - 3600000), e] } },
  { text: '最近6小时', value: () => { const e = new Date(); return [new Date(e.getTime() - 6 * 3600000), e] } },
  { text: '最近24小时', value: () => { const e = new Date(); return [new Date(e.getTime() - 24 * 3600000), e] } },
  { text: '最近7天', value: () => { const e = new Date(); return [new Date(e.getTime() - 7 * 24 * 3600000), e] } },
  { text: '本月', value: () => { const e = new Date(); return [new Date(e.getFullYear(), e.getMonth(), 1), e] } },
]

const chartOption = computed(() => {
  if (!chartData.value) return {}
  return {
    tooltip: {
      trigger: 'axis',
      formatter: (params) => {
        let html = `<b>${params[0].axisValue}</b><br/>`
        params.forEach(p => {
          html += `${p.marker} ${p.seriesName}: ${p.value} GB<br/>`
        })
        return html
      },
    },
    legend: { data: ['入站流量', '出站流量'] },
    grid: { left: '3%', right: '4%', bottom: '12%', containLabel: true },
    dataZoom: [
      { type: 'inside', start: 0, end: 100 },
      { type: 'slider', start: 0, end: 100 },
    ],
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: chartData.value.time,
      axisLabel: { rotate: 30, fontSize: 11 },
    },
    yAxis: {
      type: 'value',
      name: 'GB',
      axisLabel: { formatter: '{value}' },
    },
    series: [
      {
        name: '入站流量',
        type: 'line',
        smooth: true,
        data: chartData.value.inbound,
        itemStyle: { color: '#409EFF' },
        areaStyle: { color: 'rgba(64,158,255,0.1)' },
      },
      {
        name: '出站流量',
        type: 'line',
        smooth: true,
        data: chartData.value.outbound,
        itemStyle: { color: '#67C23A' },
        areaStyle: { color: 'rgba(103,194,58,0.1)' },
      },
    ],
  }
})

async function loadTenant() {
  try {
    const res = await api.get(`/tenants/${tenantId}`)
    tenantName.value = res.data.name
  } catch {}
}

async function loadConditions() {
  try {
    const res = await api.get(`/traffic/${tenantId}/conditions`)
    regionOptions.value = res.data.region_options
    if (regionOptions.value.length > 0) {
      selectedRegion.value = regionOptions.value[0].value
      await loadInstances()
    }
  } catch {}
}

async function onRegionChange() {
  selectedInstance.value = ''
  selectedVnic.value = ''
  vnicOptions.value = []
  chartData.value = null
  await loadInstances()
}

async function loadInstances() {
  if (!selectedRegion.value) return
  instanceLoading.value = true
  try {
    const res = await api.get(`/traffic/${tenantId}/instances`, {
      params: { region: selectedRegion.value }
    })
    instanceOptions.value = res.data.instances
    trafficSummary.instance_count = res.data.instance_count
    trafficSummary.inbound_traffic = res.data.inbound_traffic
    trafficSummary.outbound_traffic = res.data.outbound_traffic
    if (instanceOptions.value.length > 0) {
      selectedInstance.value = instanceOptions.value[0].value
      await loadVnics()
    }
  } catch {} finally {
    instanceLoading.value = false
  }
}

async function onInstanceChange() {
  selectedVnic.value = ''
  chartData.value = null
  await loadVnics()
}

async function loadVnics() {
  if (!selectedRegion.value || !selectedInstance.value) return
  vnicLoading.value = true
  try {
    const res = await api.get(`/traffic/${tenantId}/vnics`, {
      params: { region: selectedRegion.value, instance_id: selectedInstance.value }
    })
    vnicOptions.value = res.data
    if (vnicOptions.value.length > 0) {
      selectedVnic.value = vnicOptions.value[0].value
    }
  } catch {} finally {
    vnicLoading.value = false
  }
}

async function loadTrafficData() {
  if (!selectedVnic.value) {
    ElMessage.warning('请先选择 VNIC')
    return
  }
  if (!timeRange.value || timeRange.value.length < 2) {
    ElMessage.warning('请选择时间范围')
    return
  }
  chartLoading.value = true
  try {
    const res = await api.post(`/traffic/${tenantId}/data`, {
      region: selectedRegion.value,
      vnic_id: selectedVnic.value,
      begin_time: timeRange.value[0].toISOString(),
      end_time: timeRange.value[1].toISOString(),
    })
    chartData.value = res.data
    if (res.data.time.length === 0) {
      ElMessage.info('所选时间范围内无流量数据')
    }
  } catch {} finally {
    chartLoading.value = false
  }
}

onMounted(async () => {
  await loadTenant()
  await loadConditions()
})
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.summary-card { text-align: center; }
.summary-label { font-size: 13px; color: #909399; margin-bottom: 8px; }
.summary-value { font-size: 24px; font-weight: 600; color: #303133; }
.summary-value.inbound { color: #409EFF; }
.summary-value.outbound { color: #67C23A; }
</style>
