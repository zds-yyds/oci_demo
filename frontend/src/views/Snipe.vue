<template>
  <div>
    <div class="page-header">
      <h2>抢机任务</h2>
      <el-button type="primary" @click="openAdd">
        <el-icon><Plus /></el-icon> 新建任务
      </el-button>
    </div>

    <el-card shadow="never" v-loading="loading">
      <el-table :data="tasks">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column label="租户" width="120">
          <template #default="{ row }">
            {{ tenantName(row.tenant_id) }}
          </template>
        </el-table-column>
        <el-table-column prop="shape_name" label="类型" width="80" />
        <el-table-column label="配置" width="140">
          <template #default="{ row }">
            {{ row.instance_ocpus }}C / {{ row.instance_memory_in_gbs }}G / {{ row.boot_volume_size_in_gbs }}G
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="attempt_count" label="尝试次数" width="90" />
        <el-table-column prop="result_ip" label="获得IP" width="130" />
        <el-table-column label="创建时间" width="160">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.status !== 'running'"
              type="primary" size="small" text
              @click="startTask(row)"
            >启动</el-button>
            <el-button
              v-if="row.status === 'running'"
              type="warning" size="small" text
              @click="stopTask(row)"
            >停止</el-button>
            <el-button text size="small" @click="viewLog(row)">日志</el-button>
            <el-button text size="small" type="danger" @click="deleteTask(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Create task dialog -->
    <el-dialog v-model="dialogVisible" title="新建抢机任务" width="560px">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="120px">
        <el-form-item label="云账户" prop="tenant_id">
          <el-select v-model="form.tenant_id" placeholder="选择云账户" style="width:100%">
            <el-option v-for="t in tenants" :key="t.id" :label="t.name" :value="t.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="实例类型" prop="shape_name">
          <el-radio-group v-model="form.shape_name">
            <el-radio-button value="arm">ARM (A1.Flex)</el-radio-button>
            <el-radio-button value="amd">AMD (E2.1.Micro)</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="OCPU 数量" prop="instance_ocpus">
          <el-input-number v-model="form.instance_ocpus" :min="1" :max="80" />
        </el-form-item>
        <el-form-item label="内存 (GB)" prop="instance_memory_in_gbs">
          <el-input-number v-model="form.instance_memory_in_gbs" :min="1" :max="512" />
        </el-form-item>
        <el-form-item label="引导卷 (GB)" prop="boot_volume_size_in_gbs">
          <el-input-number v-model="form.boot_volume_size_in_gbs" :min="50" :max="32768" />
        </el-form-item>
        <el-form-item label="抢机频率 (s)" prop="frequency">
          <el-input-number v-model="form.frequency" :min="1" :max="60" />
        </el-form-item>
        <el-form-item label="SSH 公钥">
          <el-input v-model="form.ssh_public_key" type="textarea" :rows="3" placeholder="留空表示使用个人设置中的默认 SSH 公钥" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">创建并启动</el-button>
      </template>
    </el-dialog>

    <!-- Log dialog -->
    <el-dialog v-model="logVisible" title="任务日志" width="700px">
      <div class="log-box">
        <pre>{{ currentLog || '暂无日志' }}</pre>
      </div>
      <template #footer>
        <el-button @click="refreshLog">刷新</el-button>
        <el-button @click="logVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/api'
import dayjs from 'dayjs'

const tasks = ref([])
const tenants = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const logVisible = ref(false)
const saving = ref(false)
const currentLog = ref('')
const currentTaskId = ref(null)
const formRef = ref()
let refreshTimer = null

const form = reactive({
  tenant_id: null,
  shape_name: 'arm',
  instance_ocpus: 4,
  instance_memory_in_gbs: 24,
  boot_volume_size_in_gbs: 100,
  frequency: 10,
  ssh_public_key: '',
})

const rules = {
  tenant_id: [{ required: true, message: '请选择云账户' }],
  shape_name: [{ required: true }],
}

function statusType(s) {
  return { running: 'warning', success: 'success', failed: 'danger', stopped: 'info', pending: '' }[s] || ''
}
function formatDate(d) { return dayjs(d).format('YYYY-MM-DD HH:mm') }
function tenantName(id) { return tenants.value.find(t => t.id === id)?.name || id }

async function load() {
  loading.value = true
  try {
    const [taskRes, tenantRes] = await Promise.all([api.get('/snipe'), api.get('/tenants')])
    tasks.value = taskRes.data
    tenants.value = tenantRes.data
  } finally {
    loading.value = false
  }
}

function openAdd() {
  Object.assign(form, { tenant_id: null, shape_name: 'arm', instance_ocpus: 4, instance_memory_in_gbs: 24, boot_volume_size_in_gbs: 100, frequency: 10, ssh_public_key: '' })
  dialogVisible.value = true
}

async function save() {
  await formRef.value.validate()
  saving.value = true
  try {
    const res = await api.post('/snipe', form)
    const taskId = res.data.id
    await api.post(`/snipe/${taskId}/start`)
    ElMessage.success('任务已创建并启动')
    dialogVisible.value = false
    load()
  } finally {
    saving.value = false
  }
}

async function startTask(row) {
  await api.post(`/snipe/${row.id}/start`)
  ElMessage.success('任务已启动')
  load()
}

async function stopTask(row) {
  await api.post(`/snipe/${row.id}/stop`)
  ElMessage.success('停止信号已发送')
  load()
}

async function deleteTask(row) {
  await ElMessageBox.confirm('确认删除该任务？', '警告', { type: 'warning' })
  await api.delete(`/snipe/${row.id}`)
  ElMessage.success('删除成功')
  load()
}

async function viewLog(row) {
  currentTaskId.value = row.id
  await refreshLog()
  logVisible.value = true
}

async function refreshLog() {
  if (!currentTaskId.value) return
  const res = await api.get(`/snipe/${currentTaskId.value}`)
  currentLog.value = res.data.log
}

onMounted(() => {
  load()
  refreshTimer = setInterval(load, 8000)
})
onUnmounted(() => clearInterval(refreshTimer))
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.page-header h2 { font-size: 22px; }
.log-box {
  background: #1a1a2e;
  border-radius: 8px;
  padding: 16px;
  max-height: 400px;
  overflow-y: auto;
}
.log-box pre {
  color: #a8ff78;
  font-family: 'Courier New', monospace;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
