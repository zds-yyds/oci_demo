<template>
  <div>
    <div class="page-header">
      <div>
        <el-button text @click="$router.back()"><el-icon><ArrowLeft /></el-icon> 返回</el-button>
        <h2 style="display:inline;margin-left:8px">引导卷管理 — {{ tenantName }}</h2>
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
      <el-empty v-if="!loading && volumes.length === 0" description="暂无引导卷" />
      <el-table :data="volumes" v-if="volumes.length > 0" stripe border @selection-change="onSelectionChange">
        <el-table-column type="selection" width="50" />
        <el-table-column prop="display_name" label="名称" min-width="180" show-overflow-tooltip />
        <el-table-column label="实例配置" width="160">
          <template #default="{ row }">
            <span v-if="row.instance_ocpus || row.instance_memory_in_gbs">
              {{ row.instance_ocpus || '-' }} OCPU / {{ row.instance_memory_in_gbs || '-' }} GB
            </span>
            <span v-else style="color:#909399">未关联实例</span>
          </template>
        </el-table-column>
        <el-table-column prop="availability_domain" label="可用域" width="200" show-overflow-tooltip />
        <el-table-column prop="size_in_gbs" label="大小(GB)" width="100" />
        <el-table-column prop="vpus_per_gb" label="VPU/GB" width="90" />
        <el-table-column prop="lifecycle_state" label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="row.lifecycle_state === 'AVAILABLE' ? 'success' : 'info'" size="small">
              {{ row.lifecycle_state }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button size="small" text @click="openUpdate(row)"><el-icon><Edit /></el-icon> 配置</el-button>
            <el-button size="small" text type="danger" @click="doTerminate([row.id])"><el-icon><Delete /></el-icon> 终止</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div v-if="selectedIds.length > 0" style="margin-top:12px">
        <el-button type="danger" size="small" @click="doTerminate(selectedIds)">
          批量终止 ({{ selectedIds.length }})
        </el-button>
      </div>
    </el-card>

    <!-- 更新引导卷弹窗 -->
    <el-dialog v-model="updateDialogVisible" title="更新引导卷配置" width="440px">
      <el-form :model="updateForm" label-width="100px">
        <el-form-item label="当前大小">
          <span>{{ updateTarget?.size_in_gbs }} GB</span>
        </el-form-item>
        <el-form-item label="新大小(GB)">
          <el-input-number v-model="updateForm.size_in_gbs" :min="50" :max="32768" :step="50" />
        </el-form-item>
        <el-form-item label="VPU/GB">
          <el-input-number v-model="updateForm.vpus_per_gb" :min="10" :max="120" :step="10" />
          <div style="font-size:12px;color:#909399;margin-top:4px">10=基础, 20=均衡, 30-120=高性能</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="updateDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="updateLoading" @click="doUpdate">确认</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/api'

const route = useRoute()
const tenantId = route.params.tenantId
const tenantName = ref('')
const regions = ref([])
const selectedRegion = ref('')
const volumes = ref([])
const loading = ref(false)
const selectedIds = ref([])

const updateDialogVisible = ref(false)
const updateLoading = ref(false)
const updateTarget = ref(null)
const updateForm = reactive({ size_in_gbs: 50, vpus_per_gb: 10 })

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
    const res = await api.get(`/boot-volumes/${tenantId}`, { params: { region: selectedRegion.value } })
    volumes.value = res.data
  } catch {} finally { loading.value = false }
}

function onSelectionChange(rows) { selectedIds.value = rows.map(r => r.id) }

function openUpdate(row) {
  updateTarget.value = row
  updateForm.size_in_gbs = row.size_in_gbs
  updateForm.vpus_per_gb = row.vpus_per_gb
  updateDialogVisible.value = true
}

async function doUpdate() {
  updateLoading.value = true
  try {
    await api.put(`/boot-volumes/${tenantId}/update`, {
      region: selectedRegion.value,
      boot_volume_id: updateTarget.value.id,
      size_in_gbs: updateForm.size_in_gbs,
      vpus_per_gb: updateForm.vpus_per_gb,
    })
    ElMessage.success('引导卷配置更新成功')
    updateDialogVisible.value = false
    await load()
  } catch {} finally { updateLoading.value = false }
}

async function doTerminate(ids) {
  await ElMessageBox.confirm(`确认终止 ${ids.length} 个引导卷？此操作不可逆！`, '危险操作', { type: 'error' })
  try {
    await api.post(`/boot-volumes/${tenantId}/terminate`, {
      region: selectedRegion.value,
      boot_volume_ids: ids,
    })
    ElMessage.success('终止指令已发送')
    setTimeout(load, 3000)
  } catch {}
}

onMounted(loadTenant)
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
</style>
