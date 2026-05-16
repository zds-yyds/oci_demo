<template>
  <div>
    <div class="page-header">
      <div>
        <el-button text @click="$router.back()"><el-icon><ArrowLeft /></el-icon> 返回</el-button>
        <h2 style="display:inline;margin-left:8px">实例管理 — {{ tenantName }}</h2>
      </div>
      <el-button @click="load" :loading="loading">
        <el-icon><Refresh /></el-icon> 刷新
      </el-button>
    </div>

    <el-card shadow="never" v-loading="loading">
      <el-empty v-if="!loading && instances.length === 0" description="暂无实例" />
      <el-row :gutter="16">
        <el-col :span="12" v-for="inst in instances" :key="inst.id" style="margin-bottom:16px">
          <el-card class="instance-card" shadow="hover">
            <div class="inst-header">
              <span class="inst-name">{{ inst.display_name }}</span>
              <el-tag :type="stateType(inst.lifecycle_state)" size="small">
                {{ inst.lifecycle_state }}
              </el-tag>
            </div>
            <div class="inst-info">
              <div><el-icon><Cpu /></el-icon> {{ inst.shape }}</div>
              <div v-if="inst.ocpus || inst.memory_in_gbs">
                <el-icon><Odometer /></el-icon>
                <span v-if="inst.ocpus">{{ inst.ocpus }} OCPU</span>
                <span v-if="inst.ocpus && inst.memory_in_gbs"> / </span>
                <span v-if="inst.memory_in_gbs">{{ inst.memory_in_gbs }} GB 内存</span>
              </div>
              <div v-if="inst.boot_volume_size_gb">
                <el-icon><Box /></el-icon> 引导卷: {{ inst.boot_volume_size_gb }} GB
              </div>
              <div><el-icon><Location /></el-icon> {{ inst.region }} / {{ shortAD(inst.availability_domain) }}</div>
              <div v-if="inst.public_ip"><el-icon><Connection /></el-icon> {{ inst.public_ip }}</div>
              <div v-if="inst.time_created">
                <el-icon><Calendar /></el-icon> {{ formatDate(inst.time_created) }}
              </div>
            </div>
            <div class="inst-actions">
              <el-button
                v-if="inst.lifecycle_state === 'STOPPED'"
                type="success" size="small"
                @click="doAction(inst, 'START')"
              >开机</el-button>
              <el-button
                v-if="inst.lifecycle_state === 'RUNNING'"
                type="warning" size="small"
                @click="doAction(inst, 'SOFTSTOP')"
              >关机</el-button>
              <el-button
                v-if="inst.lifecycle_state === 'RUNNING'"
                type="danger" size="small"
                @click="doAction(inst, 'STOP')"
              >强制关机</el-button>
              <el-button
                v-if="inst.lifecycle_state === 'RUNNING'"
                size="small"
                @click="doAction(inst, 'RESET')"
              >重启</el-button>
              <el-button
                type="danger" size="small" plain
                @click="doTerminate(inst)"
              >
                <el-icon><Delete /></el-icon> 删除实例
              </el-button>
              <el-button
                size="small" plain
                @click="openConfigDialog(inst)"
              >
                <el-icon><Setting /></el-icon> 更改配置
              </el-button>
              <el-button
                v-if="inst.public_ip && inst.lifecycle_state === 'RUNNING'"
                type="primary" size="small" plain
                @click="openSSHDialog(inst)"
              >
                <el-icon><Monitor /></el-icon> SSH
              </el-button>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </el-card>

    <!-- SSH 连接弹窗 -->
    <el-dialog v-model="sshDialogVisible" title="SSH 连接" width="520px">
      <el-form :model="sshForm" label-width="100px">
        <el-form-item label="已保存凭据">
          <el-select
            v-model="sshForm.savedCredId"
            placeholder="选择已保存的凭据（可选）"
            clearable
            style="width:100%"
            @change="onSelectSavedCred"
          >
            <el-option v-for="c in savedCreds" :key="c.id" :label="`${c.label} (${c.username}@${c.host})`" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-divider content-position="left">或手动输入</el-divider>
        <el-form-item label="目标主机">
          <el-input :model-value="sshTarget?.public_ip" disabled />
        </el-form-item>
        <el-form-item label="端口">
          <el-input-number v-model="sshForm.port" :min="1" :max="65535" />
        </el-form-item>
        <el-form-item label="用户名">
          <el-input v-model="sshForm.username" placeholder="root" />
        </el-form-item>
        <el-form-item label="认证方式">
          <el-radio-group v-model="sshForm.authType">
            <el-radio-button value="password">密码</el-radio-button>
            <el-radio-button value="key">私钥</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="sshForm.authType === 'password'" label="密码">
          <el-input v-model="sshForm.password" type="password" show-password placeholder="SSH 登录密码" />
        </el-form-item>
        <el-form-item v-if="sshForm.authType === 'key'" label="私钥">
          <el-input
            v-model="sshForm.privateKey"
            type="textarea"
            :rows="6"
            placeholder="粘贴 SSH 私钥内容（PEM 格式）"
          />
        </el-form-item>
        <el-form-item label="保存凭据">
          <el-checkbox v-model="sshForm.saveCredential">保存此凭据以便下次使用</el-checkbox>
        </el-form-item>
        <el-form-item v-if="sshForm.saveCredential" label="凭据标签">
          <el-input v-model="sshForm.credLabel" placeholder="如：我的VPS" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="sshDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="doSSHConnect">连接</el-button>
      </template>
    </el-dialog>

    <!-- 更改实例配置弹窗 -->
    <el-dialog v-model="configDialogVisible" title="更改实例配置" width="520px">
      <el-alert
        v-if="configTarget && configTarget.lifecycle_state === 'RUNNING'"
        type="warning"
        :closable="false"
        style="margin-bottom:16px"
      >
        更改 Shape 需要实例处于 STOPPED 状态。修改 OCPU/内存（Flex 类型）可在运行中调整。
      </el-alert>
      <el-form :model="configForm" label-width="110px">
        <el-form-item label="实例名称">
          <el-input v-model="configForm.display_name" placeholder="留空则不修改" />
        </el-form-item>
        <el-form-item label="Shape">
          <el-select v-model="configForm.shape" placeholder="留空则不修改" clearable style="width:100%">
            <el-option-group label="ARM (Flex)">
              <el-option label="VM.Standard.A1.Flex" value="VM.Standard.A1.Flex" />
              <el-option label="VM.Standard.A2.Flex" value="VM.Standard.A2.Flex" />
            </el-option-group>
            <el-option-group label="AMD (Flex)">
              <el-option label="VM.Standard.E4.Flex" value="VM.Standard.E4.Flex" />
              <el-option label="VM.Standard.E5.Flex" value="VM.Standard.E5.Flex" />
              <el-option label="VM.Standard3.Flex" value="VM.Standard3.Flex" />
            </el-option-group>
            <el-option-group label="AMD (固定)">
              <el-option label="VM.Standard.E2.1.Micro" value="VM.Standard.E2.1.Micro" />
            </el-option-group>
          </el-select>
        </el-form-item>
        <el-form-item label="OCPU 数量">
          <el-input-number v-model="configForm.ocpus" :min="1" :max="80" :step="1" placeholder="留空则不修改" />
          <span style="margin-left:8px;color:#909399;font-size:12px">当前: {{ configTarget?.ocpus || '-' }}</span>
        </el-form-item>
        <el-form-item label="内存 (GB)">
          <el-input-number v-model="configForm.memory_in_gbs" :min="1" :max="512" :step="1" placeholder="留空则不修改" />
          <span style="margin-left:8px;color:#909399;font-size:12px">当前: {{ configTarget?.memory_in_gbs || '-' }}</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="configDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="configLoading" @click="doUpdateConfig">确认修改</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/api'
import dayjs from 'dayjs'

const route = useRoute()
const router = useRouter()
const tenantId = route.params.tenantId
const instances = ref([])
const loading = ref(false)
const tenantName = ref('')

function stateType(s) {
  return { RUNNING: 'success', STOPPED: 'info', STOPPING: 'warning', STARTING: 'warning', TERMINATED: 'danger' }[s] || ''
}
function formatDate(d) { return dayjs(d).format('YYYY-MM-DD HH:mm') }
function shortAD(ad) {
  // "AQud:EU-FRANKFURT-1-AD-1" → "AD-1"
  if (!ad) return ''
  const parts = ad.split('-')
  return parts.length >= 2 ? parts.slice(-2).join('-') : ad
}

async function load() {
  loading.value = true
  try {
    const [instRes, tenantRes] = await Promise.all([
      api.get(`/instances/${tenantId}`),
      api.get(`/tenants/${tenantId}`),
    ])
    instances.value = instRes.data
    tenantName.value = tenantRes.data.name
  } finally {
    loading.value = false
  }
}

async function doAction(inst, action) {
  const actionMap = { START: '开机', STOP: '强制关机', SOFTSTOP: '关机', RESET: '重启' }
  await ElMessageBox.confirm(
    `确认对实例「${inst.display_name}」执行【${actionMap[action]}】操作？`,
    '确认操作', { type: 'warning' }
  )
  try {
    await api.post(`/instances/${tenantId}/${inst.id}/action`, { action, region: inst.region })
    ElMessage.success(`${actionMap[action]}指令已发送`)
    setTimeout(load, 3000)
  } catch {}
}

async function doTerminate(inst) {
  await ElMessageBox.confirm(
    `⚠️ 确认删除实例「${inst.display_name}」？\n\n此操作不可逆，实例及其引导卷将被永久删除！`,
    '危险操作',
    { type: 'error', confirmButtonText: '确认删除', cancelButtonText: '取消' }
  )
  // 二次确认
  await ElMessageBox.confirm(
    `再次确认：删除实例「${inst.display_name}」(${inst.public_ip || '无公网IP'})？`,
    '最终确认',
    { type: 'error', confirmButtonText: '删除', cancelButtonText: '取消' }
  )
  try {
    await api.delete(`/instances/${tenantId}/${inst.id}`, { params: { region: inst.region } })
    ElMessage.success('删除指令已发送，实例将在数秒后终止')
    setTimeout(load, 5000)
  } catch {}
}

// ── SSH 连接弹窗 ────────────────────────────────────────────────────────────
const sshDialogVisible = ref(false)
const sshTarget = ref(null)
const savedCreds = ref([])
const sshForm = reactive({
  username: 'root',
  authType: 'password',
  password: '',
  privateKey: '',
  port: 22,
  savedCredId: null,
  saveCredential: false,
  credLabel: '',
})

async function loadSavedCreds() {
  try {
    const res = await api.get('/ssh-credentials')
    savedCreds.value = res.data
  } catch {}
}

function openSSHDialog(inst) {
  sshTarget.value = inst
  sshForm.username = 'root'
  sshForm.authType = 'password'
  sshForm.password = ''
  sshForm.privateKey = ''
  sshForm.port = 22
  sshForm.savedCredId = null
  sshForm.saveCredential = false
  sshForm.credLabel = ''
  loadSavedCreds()
  sshDialogVisible.value = true
}

async function onSelectSavedCred(credId) {
  if (!credId) return
  try {
    const res = await api.get(`/ssh-credentials/${credId}/secret`)
    const cred = res.data
    sshForm.username = cred.username
    sshForm.port = cred.port
    sshForm.authType = cred.auth_type
    sshForm.password = cred.password
    sshForm.privateKey = cred.private_key
  } catch {}
}

async function doSSHConnect() {
  if (!sshForm.username) {
    ElMessage.warning('请输入用户名')
    return
  }
  if (sshForm.authType === 'password' && !sshForm.password) {
    ElMessage.warning('请输入密码')
    return
  }
  if (sshForm.authType === 'key' && !sshForm.privateKey) {
    ElMessage.warning('请输入私钥')
    return
  }

  // 保存凭据
  if (sshForm.saveCredential) {
    try {
      await api.post('/ssh-credentials', {
        label: sshForm.credLabel || `${sshForm.username}@${sshTarget.value.public_ip}`,
        host: sshTarget.value.public_ip,
        port: sshForm.port,
        username: sshForm.username,
        auth_type: sshForm.authType,
        password: sshForm.authType === 'password' ? sshForm.password : null,
        private_key: sshForm.authType === 'key' ? sshForm.privateKey : null,
      })
    } catch {}
  }

  // 将认证信息通过 sessionStorage 传递
  const sshSession = {
    host: sshTarget.value.public_ip,
    port: sshForm.port,
    username: sshForm.username,
    authType: sshForm.authType,
    password: sshForm.authType === 'password' ? sshForm.password : '',
    privateKey: sshForm.authType === 'key' ? sshForm.privateKey : '',
    tenantId: tenantId,
  }
  sessionStorage.setItem('ssh_session', JSON.stringify(sshSession))

  sshDialogVisible.value = false
  router.push({ path: '/terminal' })
}

// ── 更改实例配置弹窗 ─────────────────────────────────────────────────────────
const configDialogVisible = ref(false)
const configTarget = ref(null)
const configLoading = ref(false)
const configForm = reactive({
  display_name: '',
  shape: '',
  ocpus: null,
  memory_in_gbs: null,
})

function openConfigDialog(inst) {
  configTarget.value = inst
  configForm.display_name = inst.display_name || ''
  configForm.shape = ''
  configForm.ocpus = inst.ocpus || null
  configForm.memory_in_gbs = inst.memory_in_gbs || null
  configDialogVisible.value = true
}

async function doUpdateConfig() {
  const payload = { region: configTarget.value.region }
  let hasChange = false

  if (configForm.display_name && configForm.display_name !== configTarget.value.display_name) {
    payload.display_name = configForm.display_name
    hasChange = true
  }
  if (configForm.shape) {
    payload.shape = configForm.shape
    hasChange = true
  }
  if (configForm.ocpus != null && configForm.ocpus !== configTarget.value.ocpus) {
    payload.ocpus = configForm.ocpus
    hasChange = true
  }
  if (configForm.memory_in_gbs != null && configForm.memory_in_gbs !== configTarget.value.memory_in_gbs) {
    payload.memory_in_gbs = configForm.memory_in_gbs
    hasChange = true
  }

  if (!hasChange) {
    ElMessage.info('未检测到配置变更')
    return
  }

  configLoading.value = true
  try {
    await api.put(`/instances/${tenantId}/${configTarget.value.id}/config`, payload)
    ElMessage.success('实例配置更新成功')
    configDialogVisible.value = false
    setTimeout(load, 3000)
  } catch (e) {
    const detail = e.response?.data?.detail || '更新失败'
    ElMessage.error(detail)
  } finally {
    configLoading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.instance-card { border-radius: 12px; }
.inst-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.inst-name { font-weight: 600; font-size: 15px; }
.inst-info { font-size: 13px; color: #606266; display: flex; flex-direction: column; gap: 6px; margin-bottom: 16px; }
.inst-info div { display: flex; align-items: center; gap: 6px; }
.inst-actions { display: flex; gap: 8px; flex-wrap: wrap; }
</style>
