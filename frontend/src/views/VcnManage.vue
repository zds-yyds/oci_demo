<template>
  <div>
    <div class="page-header">
      <div>
        <el-button text @click="$router.back()"><el-icon><ArrowLeft /></el-icon> 返回</el-button>
        <h2 style="display:inline;margin-left:8px">VCN 管理 — {{ tenantName }}</h2>
      </div>
    </div>

    <el-card shadow="never" style="margin-bottom:16px">
      <el-form :inline="true">
        <el-form-item label="区域">
          <el-select v-model="selectedRegion" placeholder="选择区域" @change="load" style="width:240px">
            <el-option v-for="r in regions" :key="r" :label="r" :value="r" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button @click="load" :loading="loading"><el-icon><Refresh /></el-icon> 刷新</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never" v-loading="loading">
      <el-empty v-if="!loading && vcnList.length === 0" description="暂无 VCN" />
      <el-table :data="vcnList" v-if="vcnList.length > 0" stripe border>
        <el-table-column prop="display_name" label="名称" min-width="180" />
        <el-table-column prop="cidr_block" label="CIDR" width="150" />
        <el-table-column label="IPv6" width="120">
          <template #default="{ row }">
            <el-tag v-if="row.ipv6_cidr_blocks && row.ipv6_cidr_blocks.length" type="success" size="small">有</el-tag>
            <el-tag v-else type="info" size="small">无</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="lifecycle_state" label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="row.lifecycle_state === 'AVAILABLE' ? 'success' : 'info'" size="small">
              {{ row.lifecycle_state }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button size="small" text type="danger" @click="doDelete(row)">
              <el-icon><Delete /></el-icon> 删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/api'

const route = useRoute()
const tenantId = route.params.tenantId
const tenantName = ref('')
const regions = ref([])
const selectedRegion = ref('')
const vcnList = ref([])
const loading = ref(false)

async function loadTenant() {
  const res = await api.get(`/tenants/${tenantId}`)
  tenantName.value = res.data.name
  regions.value = res.data.region || []
  if (regions.value.length > 0) {
    selectedRegion.value = regions.value[0]
    await load()
  }
}

async function load() {
  if (!selectedRegion.value) return
  loading.value = true
  try {
    const res = await api.get(`/vcn/${tenantId}`, { params: { region: selectedRegion.value } })
    vcnList.value = res.data
  } catch {} finally { loading.value = false }
}

async function doDelete(row) {
  await ElMessageBox.confirm(
    `确认删除 VCN「${row.display_name}」？将同时清理其下属子网、网关等资源。`,
    '危险操作', { type: 'error' }
  )
  try {
    await api.post(`/vcn/${tenantId}/delete`, {
      region: selectedRegion.value,
      vcn_ids: [row.id],
    })
    ElMessage.success('VCN 删除指令已发送')
    setTimeout(load, 3000)
  } catch {}
}

onMounted(loadTenant)
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
</style>
