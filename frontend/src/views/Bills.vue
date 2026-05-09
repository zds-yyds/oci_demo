<template>
  <div>
    <div class="page-header">
      <h2>账单监控</h2>
    </div>

    <el-card shadow="never" style="margin-bottom:16px">
      <el-form inline>
        <el-form-item label="选择云账户">
          <el-select v-model="selectedTenant" placeholder="请选择" @change="loadBill" style="width:200px">
            <el-option v-for="t in tenants" :key="t.id" :label="t.name" :value="t.id" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadBill" :loading="loading" :disabled="!selectedTenant">
            <el-icon><Refresh /></el-icon> 拉取账单
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-row :gutter="16" v-if="billData">
      <!-- Total card -->
      <el-col :span="6">
        <el-card shadow="never" class="total-card">
          <div class="total-inner">
            <el-icon size="40" color="#e6a23c"><CreditCard /></el-icon>
            <div>
              <div class="total-value">¥ {{ billData.total_cny }}</div>
              <div class="total-label">本月总消费 (CNY)</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="18">
        <!-- Chart -->
        <el-card shadow="never">
          <template #header>每日消费趋势</template>
          <v-chart :option="chartOption" style="height:260px" autoresize />
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never" style="margin-top:16px" v-if="billData">
      <template #header>账单明细</template>
      <el-table :data="billData.items" size="small" max-height="360">
        <el-table-column prop="start_time" label="开始时间" width="200" />
        <el-table-column prop="end_time" label="结束时间" width="200" />
        <el-table-column prop="currency" label="原始货币" width="100" />
        <el-table-column label="消费 (CNY)" width="120">
          <template #default="{ row }">
            <span style="color:#e6a23c;font-weight:600">¥ {{ row.amount_cny }}</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import api from '@/api'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent])

const tenants = ref([])
const selectedTenant = ref(null)
const billData = ref(null)
const loading = ref(false)

const chartOption = computed(() => {
  if (!billData.value) return {}
  const items = billData.value.items
  return {
    tooltip: { trigger: 'axis' },
    xAxis: {
      type: 'category',
      data: items.map(i => i.end_time.split('T')[0].split(' ')[0]),
      axisLabel: { rotate: 45, fontSize: 11 },
    },
    yAxis: { type: 'value', name: 'CNY' },
    series: [{
      name: '消费(CNY)',
      type: 'line',
      data: items.map(i => i.amount_cny),
      smooth: true,
      areaStyle: { opacity: 0.2 },
      itemStyle: { color: '#e6a23c' },
    }],
    grid: { left: 60, right: 20, bottom: 60, top: 20 },
  }
})

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

<style scoped>
.page-header { margin-bottom: 20px; }
.page-header h2 { font-size: 22px; }
.total-card { border-radius: 12px; height: 100%; }
.total-inner { display: flex; align-items: center; gap: 20px; padding: 16px 0; }
.total-value { font-size: 32px; font-weight: 700; color: #e6a23c; }
.total-label { font-size: 13px; color: #909399; margin-top: 4px; }
</style>
