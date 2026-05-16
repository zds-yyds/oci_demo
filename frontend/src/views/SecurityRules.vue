<template>
  <div>
    <div class="page-header">
      <div>
        <el-button text @click="$router.back()"><el-icon><ArrowLeft /></el-icon> 返回</el-button>
        <h2 style="display:inline;margin-left:8px">安全列表管理 — {{ tenantName }}</h2>
      </div>
      <el-button type="danger" @click="doReleaseAll" :loading="releaseLoading">
        <el-icon><Unlock /></el-icon> 一键放行所有端口
      </el-button>
    </div>

    <!-- 区域 + VCN 选择 -->
    <el-card shadow="never" style="margin-bottom:16px">
      <el-form :inline="true">
        <el-form-item label="区域">
          <el-select v-model="selectedRegion" placeholder="选择区域" @change="onRegionChange" style="width:240px">
            <el-option v-for="r in regions" :key="r" :label="r" :value="r" />
          </el-select>
        </el-form-item>
        <el-form-item label="VCN">
          <el-select v-model="selectedVcn" placeholder="选择 VCN" @change="loadRules" style="width:300px" :loading="vcnLoading">
            <el-option v-for="v in vcnList" :key="v.vcn_id" :label="v.display_name" :value="v.vcn_id" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-radio-group v-model="ruleType" @change="loadRules">
            <el-radio-button :value="0">入站规则</el-radio-button>
            <el-radio-button :value="1">出站规则</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item>
          <el-button @click="loadRules" :loading="rulesLoading"><el-icon><Refresh /></el-icon></el-button>
          <el-button type="primary" @click="openAddDialog"><el-icon><Plus /></el-icon> 添加规则</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 规则列表 -->
    <el-card shadow="never" v-loading="rulesLoading">
      <el-empty v-if="!rulesLoading && rules.length === 0" description="暂无安全规则" />
      <el-table :data="rules" v-if="rules.length > 0" stripe border style="width:100%">
        <el-table-column type="selection" width="50" />
        <el-table-column prop="is_stateless" label="无状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.is_stateless ? 'warning' : 'info'" size="small">
              {{ row.is_stateless ? '是' : '否' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="protocol" label="协议" width="120" />
        <el-table-column prop="source_or_destination" :label="ruleType === 0 ? '来源' : '目标'" min-width="160" />
        <el-table-column prop="source_port" label="源端口" width="100" />
        <el-table-column prop="destination_port" label="目标端口" width="100" />
        <el-table-column prop="type_and_code" label="类型和代码" width="120" />
        <el-table-column prop="description" label="描述" min-width="150" show-overflow-tooltip />
        <el-table-column label="操作" width="80" fixed="right">
          <template #default="{ $index }">
            <el-button type="danger" size="small" text @click="doRemoveRule($index)">
              <el-icon><Delete /></el-icon>
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 添加规则弹窗 -->
    <el-dialog v-model="addDialogVisible" :title="ruleType === 0 ? '添加入站规则' : '添加出站规则'" width="560px">
      <el-form :model="addForm" label-width="100px">
        <el-form-item label="无状态">
          <el-switch v-model="addForm.is_stateless" />
        </el-form-item>
        <el-form-item :label="ruleType === 0 ? '来源类型' : '目标类型'">
          <el-select v-model="addForm.type" style="width:100%">
            <el-option label="CIDR 块" value="CIDR_BLOCK" />
            <el-option label="服务 CIDR" value="SERVICE_CIDR_BLOCK" />
          </el-select>
        </el-form-item>
        <el-form-item :label="ruleType === 0 ? '来源 CIDR' : '目标 CIDR'">
          <el-input v-model="addForm.cidr" placeholder="0.0.0.0/0" />
        </el-form-item>
        <el-form-item label="协议">
          <el-select v-model="addForm.protocol" style="width:100%">
            <el-option label="所有协议" value="all" />
            <el-option label="TCP (6)" value="6" />
            <el-option label="UDP (17)" value="17" />
            <el-option label="ICMP (1)" value="1" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="addForm.protocol === '6' || addForm.protocol === '17'" label="源端口">
          <el-input v-model="addForm.source_port" placeholder="留空表示全部，如 80 或 1024-65535" />
        </el-form-item>
        <el-form-item v-if="addForm.protocol === '6' || addForm.protocol === '17'" label="目标端口">
          <el-input v-model="addForm.destination_port" placeholder="留空表示全部，如 443 或 8000-9000" />
        </el-form-item>
        <el-form-item v-if="addForm.protocol === '1'" label="ICMP 类型">
          <el-input-number v-model="addForm.icmp_type" :min="0" :max="255" />
        </el-form-item>
        <el-form-item v-if="addForm.protocol === '1'" label="ICMP 代码">
          <el-input-number v-model="addForm.icmp_code" :min="0" :max="255" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="addForm.description" placeholder="可选" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="addDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="addLoading" @click="doAddRule">确认添加</el-button>
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
const vcnList = ref([])
const selectedVcn = ref('')
const vcnLoading = ref(false)
const ruleType = ref(0)
const rules = ref([])
const rulesLoading = ref(false)
const releaseLoading = ref(false)

// 添加规则
const addDialogVisible = ref(false)
const addLoading = ref(false)
const addForm = reactive({
  is_stateless: false,
  type: 'CIDR_BLOCK',
  cidr: '0.0.0.0/0',
  protocol: 'all',
  source_port: '',
  destination_port: '',
  icmp_type: null,
  icmp_code: null,
  description: '',
})

async function loadTenant() {
  try {
    const res = await api.get(`/tenants/${tenantId}`)
    tenantName.value = res.data.name
    regions.value = res.data.region || []
    if (regions.value.length > 0) {
      selectedRegion.value = regions.value[0]
      await loadVcns()
    }
  } catch {}
}

async function onRegionChange() {
  selectedVcn.value = ''
  rules.value = []
  await loadVcns()
}

async function loadVcns() {
  if (!selectedRegion.value) return
  vcnLoading.value = true
  try {
    const res = await api.get(`/security-rules/${tenantId}/vcns`, {
      params: { region: selectedRegion.value }
    })
    vcnList.value = res.data
    if (vcnList.value.length > 0) {
      selectedVcn.value = vcnList.value[0].vcn_id
      await loadRules()
    }
  } catch {} finally {
    vcnLoading.value = false
  }
}

async function loadRules() {
  if (!selectedRegion.value || !selectedVcn.value) return
  rulesLoading.value = true
  try {
    const res = await api.get(`/security-rules/${tenantId}/rules`, {
      params: {
        region: selectedRegion.value,
        vcn_id: selectedVcn.value,
        rule_type: ruleType.value,
      }
    })
    rules.value = res.data.rules
  } catch {} finally {
    rulesLoading.value = false
  }
}

function openAddDialog() {
  if (!selectedVcn.value) {
    ElMessage.warning('请先选择 VCN')
    return
  }
  addForm.is_stateless = false
  addForm.type = 'CIDR_BLOCK'
  addForm.cidr = '0.0.0.0/0'
  addForm.protocol = 'all'
  addForm.source_port = ''
  addForm.destination_port = ''
  addForm.icmp_type = null
  addForm.icmp_code = null
  addForm.description = ''
  addDialogVisible.value = true
}

async function doAddRule() {
  addLoading.value = true
  try {
    const endpoint = ruleType.value === 0 ? 'ingress' : 'egress'
    const payload = {
      region: selectedRegion.value,
      vcn_id: selectedVcn.value,
      is_stateless: addForm.is_stateless,
      protocol: addForm.protocol,
      description: addForm.description || null,
    }

    if (ruleType.value === 0) {
      payload.source_type = addForm.type
      payload.source = addForm.cidr
    } else {
      payload.destination_type = addForm.type
      payload.destination = addForm.cidr
    }

    if (addForm.protocol === '6' || addForm.protocol === '17') {
      payload.source_port = addForm.source_port || null
      payload.destination_port = addForm.destination_port || null
    }
    if (addForm.protocol === '1') {
      payload.icmp_type = addForm.icmp_type
      payload.icmp_code = addForm.icmp_code
    }

    await api.post(`/security-rules/${tenantId}/${endpoint}`, payload)
    ElMessage.success('规则添加成功')
    addDialogVisible.value = false
    await loadRules()
  } catch {} finally {
    addLoading.value = false
  }
}

async function doRemoveRule(index) {
  await ElMessageBox.confirm('确认删除该安全规则？', '确认', { type: 'warning' })
  try {
    await api.post(`/security-rules/${tenantId}/remove`, {
      region: selectedRegion.value,
      vcn_id: selectedVcn.value,
      rule_type: ruleType.value,
      indices: [index],
    })
    ElMessage.success('规则删除成功')
    await loadRules()
  } catch {}
}

async function doReleaseAll() {
  if (!selectedRegion.value) {
    ElMessage.warning('请先选择区域')
    return
  }
  await ElMessageBox.confirm(
    '将为当前区域所有 VCN 添加 0.0.0.0/0 和 ::/0 的全协议放行规则，确认继续？',
    '一键放行所有端口',
    { type: 'warning' }
  )
  releaseLoading.value = true
  try {
    const res = await api.post(`/security-rules/${tenantId}/release-all`, {
      region: selectedRegion.value,
    })
    ElMessage.success(res.data.message)
    await loadRules()
  } catch {} finally {
    releaseLoading.value = false
  }
}

onMounted(loadTenant)
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
</style>
