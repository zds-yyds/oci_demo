<template>
  <div>
    <div class="page-header">
      <h2>Cloudflare DNS 管理</h2>
      <el-button type="primary" @click="openAddCfg">
        <el-icon><Plus /></el-icon> 添加配置
      </el-button>
    </div>

    <!-- CF 配置选择 -->
    <el-card shadow="never" style="margin-bottom:16px">
      <el-form :inline="true">
        <el-form-item label="CF 配置">
          <el-select v-model="selectedCfgId" placeholder="选择 Cloudflare 配置" style="width:280px" @change="onCfgChange">
            <el-option v-for="c in configs" :key="c.id" :label="`${c.name} (${c.domain || c.zone_id})`" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="selectedCfgId">
          <el-button size="small" @click="openEditCfg"><el-icon><Edit /></el-icon> 编辑</el-button>
          <el-button size="small" type="danger" plain @click="doDeleteCfg"><el-icon><Delete /></el-icon> 删除</el-button>
        </el-form-item>
        <el-form-item v-if="selectedCfgId" style="margin-left:auto">
          <el-select v-model="filterType" placeholder="类型筛选" clearable style="width:120px" @change="loadRecords">
            <el-option label="A" value="A" />
            <el-option label="AAAA" value="AAAA" />
            <el-option label="CNAME" value="CNAME" />
            <el-option label="MX" value="MX" />
            <el-option label="TXT" value="TXT" />
            <el-option label="NS" value="NS" />
            <el-option label="SRV" value="SRV" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="selectedCfgId">
          <el-button type="primary" @click="openAddRecord"><el-icon><Plus /></el-icon> 添加记录</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- DNS 记录列表 -->
    <el-card shadow="never" v-if="selectedCfgId" v-loading="recordsLoading">
      <el-empty v-if="!recordsLoading && records.length === 0" description="暂无 DNS 记录" />
      <el-table :data="records" v-if="records.length > 0" stripe>
        <el-table-column prop="type" label="类型" width="80" />
        <el-table-column prop="name" label="名称" min-width="180" show-overflow-tooltip />
        <el-table-column prop="content" label="内容" min-width="200" show-overflow-tooltip />
        <el-table-column label="代理" width="70" align="center">
          <template #default="{ row }">
            <el-tag :type="row.proxied ? 'warning' : 'info'" size="small">
              {{ row.proxied ? '开' : '关' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="TTL" width="80">
          <template #default="{ row }">{{ row.ttl === 1 ? 'Auto' : row.ttl }}</template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button text size="small" @click="openEditRecord(row)">编辑</el-button>
            <el-button text size="small" type="danger" @click="doDeleteRecord(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div v-if="totalRecords > 0" style="margin-top:12px;color:#909399;font-size:13px">
        共 {{ totalRecords }} 条记录
      </div>
    </el-card>

    <!-- 添加/编辑 CF 配置弹窗 -->
    <el-dialog v-model="cfgDialogVisible" :title="editCfgId ? '编辑 CF 配置' : '添加 CF 配置'" width="500px">
      <el-form :model="cfgForm" :rules="cfgRules" ref="cfgFormRef" label-width="110px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="cfgForm.name" placeholder="自定义名称，如：我的域名" />
        </el-form-item>
        <el-form-item label="API Token" prop="api_token">
          <el-input v-model="cfgForm.api_token" placeholder="Cloudflare API Token" show-password />
        </el-form-item>
        <el-form-item label="Zone ID" prop="zone_id">
          <el-input v-model="cfgForm.zone_id" placeholder="在 CF 域名概览页底部可找到" />
        </el-form-item>
        <el-form-item label="域名">
          <el-input v-model="cfgForm.domain" placeholder="可选，如 example.com（会自动获取）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="cfgDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="cfgSaving" @click="saveCfg">保存</el-button>
      </template>
    </el-dialog>

    <!-- 添加/编辑 DNS 记录弹窗 -->
    <el-dialog v-model="recordDialogVisible" :title="editRecordId ? '编辑 DNS 记录' : '添加 DNS 记录'" width="520px">
      <el-form :model="recordForm" :rules="recordRules" ref="recordFormRef" label-width="100px">
        <el-form-item label="类型" prop="type">
          <el-select v-model="recordForm.type" style="width:100%">
            <el-option label="A (IPv4)" value="A" />
            <el-option label="AAAA (IPv6)" value="AAAA" />
            <el-option label="CNAME" value="CNAME" />
            <el-option label="MX" value="MX" />
            <el-option label="TXT" value="TXT" />
            <el-option label="NS" value="NS" />
            <el-option label="SRV" value="SRV" />
          </el-select>
        </el-form-item>
        <el-form-item label="名称" prop="name">
          <el-input v-model="recordForm.name" placeholder="如 www 或 @ 表示根域名" />
        </el-form-item>
        <el-form-item label="内容" prop="content">
          <el-input v-model="recordForm.content" placeholder="如 IP 地址或目标域名" />
        </el-form-item>
        <el-form-item label="TTL">
          <el-select v-model="recordForm.ttl" style="width:100%">
            <el-option label="Auto" :value="1" />
            <el-option label="1 分钟" :value="60" />
            <el-option label="5 分钟" :value="300" />
            <el-option label="30 分钟" :value="1800" />
            <el-option label="1 小时" :value="3600" />
            <el-option label="1 天" :value="86400" />
          </el-select>
        </el-form-item>
        <el-form-item label="代理">
          <el-switch v-model="recordForm.proxied" active-text="开启" inactive-text="关闭" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="recordDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="recordSaving" @click="saveRecord">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/api'

// ── CF 配置 ──────────────────────────────────────────────────────────────────
const configs = ref([])
const selectedCfgId = ref(null)
const cfgDialogVisible = ref(false)
const cfgSaving = ref(false)
const editCfgId = ref(null)
const cfgFormRef = ref()

const cfgForm = reactive({ name: '', api_token: '', zone_id: '', domain: '' })
const cfgRules = {
  name: [{ required: true, message: '请输入名称' }],
  api_token: [{ required: true, message: '请输入 API Token' }],
  zone_id: [{ required: true, message: '请输入 Zone ID' }],
}

async function loadConfigs() {
  try {
    const res = await api.get('/cloudflare/configs')
    configs.value = res.data
  } catch {}
}

function openAddCfg() {
  editCfgId.value = null
  Object.assign(cfgForm, { name: '', api_token: '', zone_id: '', domain: '' })
  cfgDialogVisible.value = true
}

function openEditCfg() {
  const cfg = configs.value.find(c => c.id === selectedCfgId.value)
  if (!cfg) return
  editCfgId.value = cfg.id
  Object.assign(cfgForm, { name: cfg.name, api_token: '', zone_id: cfg.zone_id, domain: cfg.domain || '' })
  cfgDialogVisible.value = true
}

async function saveCfg() {
  await cfgFormRef.value.validate()
  cfgSaving.value = true
  try {
    if (editCfgId.value) {
      const payload = {}
      if (cfgForm.name) payload.name = cfgForm.name
      if (cfgForm.api_token) payload.api_token = cfgForm.api_token
      if (cfgForm.zone_id) payload.zone_id = cfgForm.zone_id
      if (cfgForm.domain) payload.domain = cfgForm.domain
      await api.put(`/cloudflare/configs/${editCfgId.value}`, payload)
      ElMessage.success('更新成功')
    } else {
      await api.post('/cloudflare/configs', cfgForm)
      ElMessage.success('添加成功')
    }
    cfgDialogVisible.value = false
    await loadConfigs()
  } finally {
    cfgSaving.value = false
  }
}

async function doDeleteCfg() {
  await ElMessageBox.confirm('确认删除该 CF 配置？', '警告', { type: 'warning' })
  await api.delete(`/cloudflare/configs/${selectedCfgId.value}`)
  ElMessage.success('删除成功')
  selectedCfgId.value = null
  records.value = []
  await loadConfigs()
}

// ── DNS 记录 ─────────────────────────────────────────────────────────────────
const records = ref([])
const totalRecords = ref(0)
const recordsLoading = ref(false)
const filterType = ref('')
const recordDialogVisible = ref(false)
const recordSaving = ref(false)
const editRecordId = ref(null)
const recordFormRef = ref()

const recordForm = reactive({ type: 'A', name: '', content: '', ttl: 1, proxied: false })
const recordRules = {
  type: [{ required: true, message: '请选择类型' }],
  name: [{ required: true, message: '请输入名称' }],
  content: [{ required: true, message: '请输入内容' }],
}

async function onCfgChange() {
  records.value = []
  filterType.value = ''
  if (selectedCfgId.value) await loadRecords()
}

async function loadRecords() {
  if (!selectedCfgId.value) return
  recordsLoading.value = true
  try {
    const params = { cfg_id: selectedCfgId.value, per_page: 100 }
    if (filterType.value) params.type = filterType.value
    const res = await api.get('/cloudflare/dns-records', { params })
    records.value = res.data.records
    totalRecords.value = res.data.total
  } catch {} finally {
    recordsLoading.value = false
  }
}

function openAddRecord() {
  editRecordId.value = null
  Object.assign(recordForm, { type: 'A', name: '', content: '', ttl: 1, proxied: false })
  recordDialogVisible.value = true
}

function openEditRecord(row) {
  editRecordId.value = row.id
  Object.assign(recordForm, {
    type: row.type,
    name: row.name,
    content: row.content,
    ttl: row.ttl,
    proxied: row.proxied,
  })
  recordDialogVisible.value = true
}

async function saveRecord() {
  await recordFormRef.value.validate()
  recordSaving.value = true
  try {
    if (editRecordId.value) {
      await api.put('/cloudflare/dns-records', {
        cfg_id: selectedCfgId.value,
        record_id: editRecordId.value,
        ...recordForm,
      })
      ElMessage.success('更新成功')
    } else {
      await api.post('/cloudflare/dns-records', {
        cfg_id: selectedCfgId.value,
        ...recordForm,
      })
      ElMessage.success('添加成功')
    }
    recordDialogVisible.value = false
    await loadRecords()
  } finally {
    recordSaving.value = false
  }
}

async function doDeleteRecord(row) {
  await ElMessageBox.confirm(`确认删除记录「${row.name}」？`, '警告', { type: 'warning' })
  await api.post('/cloudflare/dns-records/delete', {
    cfg_id: selectedCfgId.value,
    record_ids: [row.id],
  })
  ElMessage.success('删除成功')
  await loadRecords()
}

onMounted(loadConfigs)
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.page-header h2 { font-size: 22px; margin: 0; }
</style>
