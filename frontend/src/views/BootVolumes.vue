<template>
  <div>
    <div class="page-header">
      <div>
        <el-button text @click="$router.back()"><el-icon><ArrowLeft /></el-icon> 返回</el-button>
        <h2 style="display:inline;margin-left:8px">引导卷管理 — {{ tenantName }}</h2>
      </div>
      <el-button @click="load" :loading="loading">
        <el-icon><Refresh /></el-icon> 刷新
      </el-button>
    </div>

    <el-card shadow="never" v-loading="loading">
      <el-empty v-if="!loading && volumes.length === 0" description="暂无引导卷" />

      <div v-for="(group, idx) in regionGroups" :key="group.name" style="margin-bottom:24px">
        <el-divider v-if="idx > 0" />
        <div class="region-header">
          <el-icon><Location /></el-icon>
          <span>{{ group.name }}</span>
          <el-tag size="small" type="info" style="margin-left:8px">{{ group.volumes.length }} 个引导卷</el-tag>
        </div>

        <el-table :data="group.volumes" stripe border @selection-change="(rows) => onSelectionChange(rows, group.name)">
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
              <el-button size="small" text type="danger" @click="doTerminate([row])"><el-icon><Delete /></el-icon> 终止</el-button>
            </template>
          </el-table-column>
        </el-table>

        <div v-if="(selectedByRegion[group.name] || []).length > 0" style="margin-top:12px">
          <el-button type="danger" size="small" @click="doTerminate(selectedByRegion[group.name])">
            批量终止 ({{ selectedByRegion[group.name].length }})
          </el-button>
        </div>
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
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/api'

const route = useRoute()
const tenantId = route.params.tenantId
const tenantName = ref('')
const volumes = ref([])
const loading = ref(false)

// 按区域分组的选中行，key 为 region name
const selectedByRegion = reactive({})

const regionGroups = computed(() => {
  const groups = {}
  for (const vol of volumes.value) {
    const r = vol.region || '未知区域'
    if (!groups[r]) groups[r] = []
    groups[r].push(vol)
  }
  return Object.keys(groups)
    .sort()
    .map(name => ({ name, volumes: groups[name] }))
})

const updateDialogVisible = ref(false)
const updateLoading = ref(false)
const updateTarget = ref(null)
const updateForm = reactive({ size_in_gbs: 50, vpus_per_gb: 10 })

async function load() {
  loading.value = true
  try {
    const [volRes, tenantRes] = await Promise.all([
      api.get(`/boot-volumes/${tenantId}`),
      api.get(`/tenants/${tenantId}`),
    ])
    volumes.value = volRes.data
    tenantName.value = tenantRes.data.name
  } catch {} finally {
    loading.value = false
  }
}

function onSelectionChange(rows, regionName) {
  selectedByRegion[regionName] = rows
}

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
      region: updateTarget.value.region,
      boot_volume_id: updateTarget.value.id,
      size_in_gbs: updateForm.size_in_gbs,
      vpus_per_gb: updateForm.vpus_per_gb,
    })
    ElMessage.success('引导卷配置更新成功')
    updateDialogVisible.value = false
    await load()
  } catch {} finally {
    updateLoading.value = false
  }
}

async function doTerminate(rows) {
  await ElMessageBox.confirm(
    `确认终止 ${rows.length} 个引导卷？此操作不可逆！`,
    '危险操作',
    { type: 'error' }
  )
  // 按区域分组批量终止
  const byRegion = {}
  for (const row of rows) {
    const r = row.region || ''
    if (!byRegion[r]) byRegion[r] = []
    byRegion[r].push(row.id)
  }
  try {
    await Promise.all(
      Object.entries(byRegion).map(([region, ids]) =>
        api.post(`/boot-volumes/${tenantId}/terminate`, { region, boot_volume_ids: ids })
      )
    )
    ElMessage.success('终止指令已发送')
    setTimeout(load, 3000)
  } catch {}
}

onMounted(load)
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.region-header { display: flex; align-items: center; gap: 6px; font-size: 15px; font-weight: 600; margin-bottom: 12px; color: #303133; }
</style>
