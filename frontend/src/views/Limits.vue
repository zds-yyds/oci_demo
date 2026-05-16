<template>
  <div>
    <div class="page-header">
      <div>
        <el-button text @click="$router.back()"><el-icon><ArrowLeft /></el-icon> 返回</el-button>
        <h2 style="display:inline;margin-left:8px">配额查询 — {{ tenantName }}</h2>
      </div>
    </div>

    <el-card shadow="never" style="margin-bottom:16px">
      <el-form :inline="true">
        <el-form-item label="区域">
          <el-select v-model="selectedRegion" placeholder="选择区域" @change="onRegionChange" style="width:220px">
            <el-option v-for="r in regions" :key="r" :label="r" :value="r" />
          </el-select>
        </el-form-item>
        <el-form-item label="服务">
          <el-select v-model="selectedService" placeholder="选择服务" filterable style="width:200px" :loading="servicesLoading">
            <el-option v-for="s in services" :key="s" :label="s" :value="s" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="queryLimits" :loading="queryLoading">
            <el-icon><Search /></el-icon> 查询
          </el-button>
        </el-form-item>
      </el-form>
      <div v-if="servicesLoading" style="color:#909399;font-size:13px;margin-top:8px">
        正在加载服务列表，请稍候（首次加载可能较慢）...
      </div>
    </el-card>

    <el-card shadow="never" v-loading="queryLoading">
      <el-empty v-if="!queryLoading && items.length === 0" description="请选择服务并点击查询" />
      <el-table :data="items" v-if="items.length > 0" stripe border max-height="600">
        <el-table-column prop="limit_name" label="配额名称" min-width="220" show-overflow-tooltip />
        <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
        <el-table-column prop="scope_type" label="范围" width="90" />
        <el-table-column prop="availability_domain" label="可用域" width="180" show-overflow-tooltip />
        <el-table-column prop="service_limit" label="限额" width="80" align="center" />
        <el-table-column prop="used" label="已用" width="80" align="center" />
        <el-table-column prop="available" label="可用" width="80" align="center" />
        <el-table-column label="使用率" width="120">
          <template #default="{ row }">
            <el-progress
              v-if="row.service_limit && row.used != null"
              :percentage="Math.min(100, Math.round((row.used / row.service_limit) * 100))"
              :stroke-width="10"
              :color="getProgressColor(row)"
            />
            <span v-else style="color:#909399">-</span>
          </template>
        </el-table-column>
      </el-table>
      <div v-if="items.length > 0" style="margin-top:12px;color:#909399;font-size:13px">
        共 {{ items.length }} 条配额记录
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '@/api'

const route = useRoute()
const tenantId = route.params.tenantId
const tenantName = ref('')
const regions = ref([])
const selectedRegion = ref('')
const services = ref([])
const selectedService = ref('')
const servicesLoading = ref(false)
const queryLoading = ref(false)
const items = ref([])

function getProgressColor(row) {
  if (!row.service_limit || row.used == null) return '#909399'
  const pct = (row.used / row.service_limit) * 100
  if (pct >= 90) return '#F56C6C'
  if (pct >= 70) return '#E6A23C'
  return '#67C23A'
}

async function loadTenant() {
  try {
    const res = await api.get(`/tenants/${tenantId}`)
    tenantName.value = res.data.name
    regions.value = res.data.region || []
    if (regions.value.length > 0) {
      selectedRegion.value = regions.value[0]
      await loadServices()
    }
  } catch (e) {
    ElMessage.error('加载租户信息失败')
  }
}

async function onRegionChange() {
  selectedService.value = ''
  items.value = []
  await loadServices()
}

async function loadServices() {
  if (!selectedRegion.value) return
  servicesLoading.value = true
  try {
    const res = await api.get(`/limits/${tenantId}/services`, { params: { region: selectedRegion.value } })
    services.value = res.data
    if (services.value.length > 0) {
      selectedService.value = services.value.includes('compute') ? 'compute' : services.value[0]
    }
  } catch {} finally { servicesLoading.value = false }
}

async function queryLimits() {
  if (!selectedService.value) {
    ElMessage.warning('请选择服务')
    return
  }
  queryLoading.value = true
  try {
    const res = await api.get(`/limits/${tenantId}/query`, {
      params: { region: selectedRegion.value, service_name: selectedService.value }
    })
    items.value = res.data.items
    if (items.value.length === 0) {
      ElMessage.info('该服务暂无配额数据')
    }
  } catch {} finally { queryLoading.value = false }
}

onMounted(loadTenant)
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
</style>
