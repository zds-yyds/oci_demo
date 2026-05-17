<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-3">
        <button class="btn-ghost btn-sm" @click="$router.back()">← 返回</button>
        <h2 class="text-2xl font-bold text-surface-900 dark:text-white">实例管理 — {{ tenantName }}</h2>
      </div>
      <button class="btn-secondary" :disabled="loading" @click="load">
        {{ loading ? '刷新中...' : '刷新' }}
      </button>
    </div>

    <!-- Content -->
    <div class="card p-6">
      <Loading :loading="loading" text="加载实例中..." />
      <div v-if="!loading && instances.length === 0" class="text-center text-surface-400 py-12">暂无实例</div>

      <div v-for="(group, idx) in regionGroups" :key="group.name" :class="{ 'mt-8': idx > 0 }">
        <div v-if="idx > 0" class="border-t border-surface-200 dark:border-surface-700 mb-6"></div>
        <div class="flex items-center gap-2 mb-4">
          <span class="font-semibold text-surface-900 dark:text-white">{{ group.name }}</span>
          <span class="badge-info">{{ group.instances.length }} 个实例</span>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div v-for="inst in group.instances" :key="inst.id" class="card p-4">
            <div class="flex items-center justify-between mb-3">
              <span class="font-semibold text-surface-900 dark:text-white">{{ inst.display_name }}</span>
              <span :class="stateClass(inst.lifecycle_state)">{{ inst.lifecycle_state }}</span>
            </div>
            <div class="space-y-1.5 text-sm text-surface-600 dark:text-surface-400 mb-4">
              <div>Shape: {{ inst.shape }}</div>
              <div v-if="inst.ocpus || inst.memory_in_gbs">
                <span v-if="inst.ocpus">{{ inst.ocpus }} OCPU</span>
                <span v-if="inst.ocpus && inst.memory_in_gbs"> / </span>
                <span v-if="inst.memory_in_gbs">{{ inst.memory_in_gbs }} GB</span>
              </div>
              <div v-if="inst.boot_volume_size_gb">引导卷: {{ inst.boot_volume_size_gb }} GB</div>
              <div>AD: {{ shortAD(inst.availability_domain) }}</div>
              <div v-if="inst.public_ip">IP: {{ inst.public_ip }}</div>
              <div>IPv6: {{ inst.ipv6_addresses?.length ? inst.ipv6_addresses.join(', ') : '-' }}</div>
              <div v-if="inst.time_created">创建: {{ formatDate(inst.time_created) }}</div>
            </div>

            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2 flex-wrap">
                <button v-if="inst.lifecycle_state === 'STOPPED'" class="btn-primary btn-sm" @click="doAction(inst, 'START')">开机</button>
                <button v-if="inst.lifecycle_state === 'RUNNING'" class="btn-secondary btn-sm" @click="doAction(inst, 'SOFTSTOP')">关机</button>
                <button v-if="inst.lifecycle_state === 'RUNNING'" class="btn-ghost btn-sm" @click="doAction(inst, 'RESET')">重启</button>
                <button v-if="inst.public_ip && inst.lifecycle_state === 'RUNNING'" class="btn-primary btn-sm" @click="openSSHDialog(inst)">SSH</button>
              </div>
              <div class="relative">
                <button class="btn-ghost btn-sm" :data-dropdown-id="inst.id" @click.stop="toggleInstDropdown(inst.id)">更多 ▾</button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Dropdown menu (teleported to avoid overflow clipping) -->
    <Teleport to="body">
      <div v-if="openInstDropdownId !== null" class="fixed inset-0 z-[8000]" @click="openInstDropdownId = null">
        <div class="fixed w-44 bg-white dark:bg-surface-800 border border-surface-200 dark:border-surface-700 rounded-lg shadow-lg py-1 z-[8001]" :style="dropdownStyle" @click.stop>
          <button class="dropdown-item" @click="handleDropdownAction('config')">更改配置</button>
          <button class="dropdown-item" :disabled="dropdownInst?.lifecycle_state !== 'RUNNING'" @click="handleDropdownAction('vnc')">VNC 控制台</button>
          <button class="dropdown-item" :disabled="dropdownInst?.lifecycle_state !== 'RUNNING'" @click="handleDropdownAction('ipv6')">附加 IPv6</button>
          <button v-if="dropdownInst && isAmdShape(dropdownInst.shape)" class="dropdown-item" :disabled="dropdownInst?.lifecycle_state !== 'RUNNING'" @click="handleDropdownAction('enable500m')">开启 500M</button>
          <button v-if="dropdownInst && isAmdShape(dropdownInst.shape)" class="dropdown-item" :disabled="dropdownInst?.lifecycle_state !== 'RUNNING'" @click="handleDropdownAction('disable500m')">关闭 500M</button>
          <button class="dropdown-item" :disabled="dropdownInst?.lifecycle_state !== 'RUNNING'" @click="handleDropdownAction('forceStop')">强制关机</button>
          <hr class="my-1 border-surface-200 dark:border-surface-700" />
          <button class="dropdown-item text-red-600 dark:text-red-400" @click="handleDropdownAction('terminate')">删除实例</button>
        </div>
      </div>
    </Teleport>

    <!-- SSH Modal -->
    <Modal :visible="sshDialogVisible" title="SSH 连接" width="520px" @close="sshDialogVisible = false">
      <div class="space-y-4">
        <div>
          <label class="label">已保存凭据</label>
          <select v-model="sshForm.savedCredId" class="select" @change="onSelectSavedCred">
            <option value="">选择已保存的凭据（可选）</option>
            <option v-for="c in savedCreds" :key="c.id" :value="c.id">{{ c.label }} ({{ c.username }}@{{ c.host }})</option>
          </select>
        </div>
        <hr class="border-surface-200 dark:border-surface-700" />
        <div>
          <label class="label">目标主机</label>
          <input :value="sshTarget?.public_ip" class="input" disabled />
        </div>
        <div>
          <label class="label">端口</label>
          <input v-model.number="sshForm.port" type="number" class="input" min="1" max="65535" />
        </div>
        <div>
          <label class="label">用户名</label>
          <input v-model="sshForm.username" class="input" placeholder="root" />
        </div>
        <div>
          <label class="label">认证方式</label>
          <div class="flex gap-4">
            <label class="flex items-center gap-2 cursor-pointer">
              <input type="radio" v-model="sshForm.authType" value="password" class="accent-primary-600" /> 密码
            </label>
            <label class="flex items-center gap-2 cursor-pointer">
              <input type="radio" v-model="sshForm.authType" value="key" class="accent-primary-600" /> 私钥
            </label>
          </div>
        </div>
        <div v-if="sshForm.authType === 'password'">
          <label class="label">密码</label>
          <input v-model="sshForm.password" type="password" class="input" placeholder="SSH 登录密码" />
        </div>
        <div v-if="sshForm.authType === 'key'">
          <label class="label">私钥</label>
          <textarea v-model="sshForm.privateKey" class="input" rows="5" placeholder="粘贴 SSH 私钥内容（PEM 格式）"></textarea>
        </div>
        <div class="flex items-center gap-2">
          <input type="checkbox" v-model="sshForm.saveCredential" id="saveCred" class="accent-primary-600" />
          <label for="saveCred" class="text-sm text-surface-700 dark:text-surface-300">保存此凭据以便下次使用</label>
        </div>
        <div v-if="sshForm.saveCredential">
          <label class="label">凭据标签</label>
          <input v-model="sshForm.credLabel" class="input" placeholder="如：我的VPS" />
        </div>
      </div>
      <template #footer>
        <button class="btn-secondary" @click="sshDialogVisible = false">取消</button>
        <button class="btn-primary" @click="doSSHConnect">连接</button>
      </template>
    </Modal>

    <!-- VNC Modal -->
    <Modal :visible="vncDialogVisible" title="VNC 控制台连接" width="680px" @close="vncDialogVisible = false">
      <Loading :loading="vncLoading" text="正在创建 Console Connection，请稍候（约 30-60 秒）..." />
      <template v-if="vncResult">
        <div
          :class="vncResult.vnc_connection_string
            ? 'bg-emerald-50 dark:bg-emerald-900/20 border-emerald-200 dark:border-emerald-800 text-emerald-800 dark:text-emerald-300'
            : 'bg-amber-50 dark:bg-amber-900/20 border-amber-200 dark:border-amber-800 text-amber-800 dark:text-amber-300'"
          class="border rounded-lg p-3 mb-4 text-sm"
        >
          {{ vncResult.message }}
        </div>
        <div v-if="vncResult.vnc_connection_string" class="mb-4">
          <h4 class="text-sm font-semibold mb-2">VNC 连接命令</h4>
          <p class="text-xs text-surface-500 mb-2">将私钥保存为文件（如 console_key.pem），然后执行以下命令建立 VNC 隧道：</p>
          <div class="bg-surface-50 dark:bg-surface-900 border border-surface-200 dark:border-surface-700 rounded-lg p-3 flex items-start justify-between gap-2">
            <code class="text-xs break-all flex-1">{{ vncResult.vnc_connection_string }}</code>
            <button class="btn-ghost btn-sm" @click="copyText(vncResult.vnc_connection_string)">复制</button>
          </div>
        </div>
        <div v-if="vncResult.ssh_connection_string" class="mb-4">
          <h4 class="text-sm font-semibold mb-2">SSH 串行控制台命令</h4>
          <div class="bg-surface-50 dark:bg-surface-900 border border-surface-200 dark:border-surface-700 rounded-lg p-3 flex items-start justify-between gap-2">
            <code class="text-xs break-all flex-1">{{ vncResult.ssh_connection_string }}</code>
            <button class="btn-ghost btn-sm" @click="copyText(vncResult.ssh_connection_string)">复制</button>
          </div>
        </div>
        <div v-if="vncResult.private_key" class="mb-4">
          <h4 class="text-sm font-semibold mb-2">私钥（请妥善保存）</h4>
          <textarea :value="vncResult.private_key" class="input" rows="5" readonly></textarea>
          <button class="btn-ghost btn-sm mt-2" @click="copyText(vncResult.private_key)">复制私钥</button>
        </div>
        <hr class="my-4 border-surface-200 dark:border-surface-700" />
        <div class="text-xs text-surface-500 dark:text-surface-400">
          <p class="font-semibold mb-1">使用方法：</p>
          <ol class="list-decimal pl-4 space-y-1">
            <li>将上方私钥保存为文件，如 <code class="bg-surface-100 dark:bg-surface-700 px-1 rounded">console_key.pem</code>，并设置权限 <code class="bg-surface-100 dark:bg-surface-700 px-1 rounded">chmod 600 console_key.pem</code></li>
            <li>执行 VNC 连接命令（将命令中的密钥路径替换为实际路径）</li>
            <li>使用 VNC 客户端连接 <code class="bg-surface-100 dark:bg-surface-700 px-1 rounded">localhost:5900</code></li>
          </ol>
        </div>
      </template>
      <div v-else-if="!vncLoading" class="text-center text-surface-400 py-10">正在准备...</div>
      <template #footer>
        <button v-if="vncResult?.connection_id" class="btn-danger btn-sm" @click="doDeleteVncConnection">删除连接</button>
        <button class="btn-secondary" @click="vncDialogVisible = false">关闭</button>
      </template>
    </Modal>

    <!-- Config Modal -->
    <Modal :visible="configDialogVisible" title="更改实例配置" width="520px" @close="configDialogVisible = false">
      <div v-if="configTarget?.lifecycle_state === 'RUNNING'" class="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg p-3 mb-4 text-sm text-amber-800 dark:text-amber-300">
        更改 Shape 需要实例处于 STOPPED 状态。修改 OCPU/内存（Flex 类型）可在运行中调整。
      </div>
      <div class="space-y-4">
        <div>
          <label class="label">实例名称</label>
          <input v-model="configForm.display_name" class="input" placeholder="留空则不修改" />
        </div>
        <div>
          <label class="label">Shape</label>
          <select v-model="configForm.shape" class="select">
            <option value="">留空则不修改</option>
            <optgroup label="ARM (Flex)">
              <option value="VM.Standard.A1.Flex">VM.Standard.A1.Flex</option>
              <option value="VM.Standard.A2.Flex">VM.Standard.A2.Flex</option>
            </optgroup>
            <optgroup label="AMD (Flex)">
              <option value="VM.Standard.E4.Flex">VM.Standard.E4.Flex</option>
              <option value="VM.Standard.E5.Flex">VM.Standard.E5.Flex</option>
              <option value="VM.Standard3.Flex">VM.Standard3.Flex</option>
            </optgroup>
            <optgroup label="AMD (固定)">
              <option value="VM.Standard.E2.1.Micro">VM.Standard.E2.1.Micro</option>
            </optgroup>
          </select>
        </div>
        <div>
          <label class="label">OCPU 数量 <span class="text-xs text-surface-400">当前: {{ configTarget?.ocpus || '-' }}</span></label>
          <input v-model.number="configForm.ocpus" type="number" class="input" min="1" max="80" />
        </div>
        <div>
          <label class="label">内存 (GB) <span class="text-xs text-surface-400">当前: {{ configTarget?.memory_in_gbs || '-' }}</span></label>
          <input v-model.number="configForm.memory_in_gbs" type="number" class="input" min="1" max="512" />
        </div>
      </div>
      <template #footer>
        <button class="btn-secondary" @click="configDialogVisible = false">取消</button>
        <button class="btn-primary" :disabled="configLoading" @click="doUpdateConfig">
          {{ configLoading ? '修改中...' : '确认修改' }}
        </button>
      </template>
    </Modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '@/api'
import { useToast } from '@/composables/useToast'
import { useModal } from '@/composables/useModal'
import Modal from '@/components/Modal.vue'
import Loading from '@/components/Loading.vue'
import dayjs from 'dayjs'

const route = useRoute()
const router = useRouter()
const { success, warning, error } = useToast()
const { confirm } = useModal()

const tenantId = route.params.tenantId as string
const instances = ref<any[]>([])
const loading = ref(false)
const tenantName = ref('')

const regionGroups = computed(() => {
  const groups: Record<string, any[]> = {}
  for (const inst of instances.value) {
    const r = inst.region || '未知区域'
    if (!groups[r]) groups[r] = []
    groups[r].push(inst)
  }
  return Object.keys(groups)
    .sort((a, b) => groups[b].length - groups[a].length)
    .map(name => ({ name, instances: groups[name] }))
})

function stateClass(s: string) {
  const map: Record<string, string> = {
    RUNNING: 'badge-success', STOPPED: 'badge-neutral', STOPPING: 'badge-warning',
    STARTING: 'badge-warning', TERMINATED: 'badge-danger',
  }
  return map[s] || 'badge-info'
}

function formatDate(d: string) { return dayjs(d).format('YYYY-MM-DD HH:mm') }

function shortAD(ad: string) {
  if (!ad) return ''
  const parts = ad.split('-')
  return parts.length >= 2 ? parts.slice(-2).join('-') : ad
}

function isAmdShape(shape: string) {
  return shape.includes('E2') || shape.includes('E4') || shape.includes('E5')
}

// ── Dropdown ─────────────────────────────────────────────────────────────────
const openInstDropdownId = ref<string | null>(null)
const dropdownStyle = ref({ top: '0px', left: '0px' })
const dropdownInst = ref<any>(null)

function toggleInstDropdown(id: string) {
  if (openInstDropdownId.value === id) {
    openInstDropdownId.value = null
    return
  }
  // Find the instance
  dropdownInst.value = instances.value.find(i => i.id === id) || null
  // Position the dropdown near the button
  const btn = document.querySelector(`[data-dropdown-id="${id}"]`) as HTMLElement
  if (btn) {
    const rect = btn.getBoundingClientRect()
    dropdownStyle.value = {
      top: `${rect.bottom + 4}px`,
      left: `${rect.right - 176}px`,
    }
  }
  openInstDropdownId.value = id
}

function handleDropdownAction(action: string) {
  const inst = dropdownInst.value
  if (!inst) return
  openInstDropdownId.value = null
  switch (action) {
    case 'config': openConfigDialog(inst); break
    case 'vnc': doStartVnc(inst); break
    case 'ipv6': doAttachIpv6(inst); break
    case 'enable500m': doEnable500M(inst); break
    case 'disable500m': doDisable500M(inst); break
    case 'forceStop': doAction(inst, 'STOP'); break
    case 'terminate': doTerminate(inst); break
  }
}

function handleClickOutside() {
  openInstDropdownId.value = null
}

onMounted(() => document.addEventListener('click', handleClickOutside, true))
onBeforeUnmount(() => document.removeEventListener('click', handleClickOutside, true))

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

async function doAction(inst: any, action: string) {
  const actionMap: Record<string, string> = { START: '开机', STOP: '强制关机', SOFTSTOP: '关机', RESET: '重启' }
  const ok = await confirm(`确认对实例「${inst.display_name}」执行【${actionMap[action]}】操作？`, '确认操作')
  if (!ok) return
  openInstDropdownId.value = null
  try {
    await api.post(`/instances/${tenantId}/${inst.id}/action`, { action, region: inst.region })
    success(`${actionMap[action]}指令已发送`)
    setTimeout(load, 3000)
  } catch { /* handled by interceptor */ }
}

async function doTerminate(inst: any) {
  openInstDropdownId.value = null
  const ok = await confirm(`⚠️ 确认删除实例「${inst.display_name}」？此操作不可逆！`, '危险操作', { type: 'error', confirmText: '确认删除' })
  if (!ok) return
  const ok2 = await confirm(`再次确认：删除实例「${inst.display_name}」(${inst.public_ip || '无公网IP'})？`, '最终确认', { type: 'error', confirmText: '删除' })
  if (!ok2) return
  try {
    await api.delete(`/instances/${tenantId}/${inst.id}`, { params: { region: inst.region } })
    success('删除指令已发送，实例将在数秒后终止')
    setTimeout(load, 5000)
  } catch { /* handled by interceptor */ }
}

// ── VNC ──────────────────────────────────────────────────────────────────────
const vncDialogVisible = ref(false)
const vncLoading = ref(false)
const vncResult = ref<any>(null)
const vncRegion = ref('')

async function doStartVnc(inst: any) {
  openInstDropdownId.value = null
  vncResult.value = null
  vncRegion.value = inst.region
  vncLoading.value = true
  vncDialogVisible.value = true
  try {
    const res = await api.post(`/console/${tenantId}/start-vnc`, { region: inst.region, instance_id: inst.id })
    vncResult.value = res.data
  } catch (e: any) {
    vncResult.value = { message: e.response?.data?.detail || '创建 VNC 连接失败' }
  } finally {
    vncLoading.value = false
  }
}

async function doDeleteVncConnection() {
  if (!vncResult.value?.connection_id) return
  try {
    await api.post(`/console/${tenantId}/delete-connection`, { region: vncRegion.value, connection_id: vncResult.value.connection_id })
    success('连接已删除')
    vncDialogVisible.value = false
  } catch { /* handled by interceptor */ }
}

function copyText(text: string) {
  navigator.clipboard.writeText(text).then(() => success('已复制到剪贴板')).catch(() => error('复制失败'))
}

// ── IPv6 & 500M ──────────────────────────────────────────────────────────────
async function doAttachIpv6(inst: any) {
  openInstDropdownId.value = null
  const ok = await confirm(`为实例「${inst.display_name}」附加 IPv6 地址？将自动配置 VCN IPv6 CIDR、子网和安全规则。`, '附加 IPv6', { type: 'info' })
  if (!ok) return
  try {
    const res = await api.post(`/network/${tenantId}/attach-ipv6`, { region: inst.region, instance_id: inst.id })
    success(`IPv6 附加成功: ${res.data.ipv6_address}`)
    setTimeout(load, 3000)
  } catch { /* handled by interceptor */ }
}

async function doEnable500M(inst: any) {
  openInstDropdownId.value = null
  const ok = await confirm(`为 AMD 实例「${inst.display_name}」开启下行 500Mbps？将创建 NLB 和 NAT 网关。`, '开启 500Mbps')
  if (!ok) return
  try {
    await api.post(`/network/${tenantId}/enable-500m`, { region: inst.region, instance_id: inst.id, ssh_port: 22 })
    success('任务已提交，请稍后查看')
  } catch { /* handled by interceptor */ }
}

async function doDisable500M(inst: any) {
  openInstDropdownId.value = null
  const ok = await confirm(`关闭实例「${inst.display_name}」的下行 500Mbps？将清理 NLB 和 NAT 网关。`, '关闭 500Mbps')
  if (!ok) return
  try {
    await api.post(`/network/${tenantId}/disable-500m`, { region: inst.region, instance_id: inst.id, retain_nlb: false, retain_nat_gw: false })
    success('关闭任务已提交')
  } catch { /* handled by interceptor */ }
}

// ── SSH ──────────────────────────────────────────────────────────────────────
const sshDialogVisible = ref(false)
const sshTarget = ref<any>(null)
const savedCreds = ref<any[]>([])
const sshForm = reactive({
  username: 'root',
  authType: 'password',
  password: '',
  privateKey: '',
  port: 22,
  savedCredId: '',
  saveCredential: false,
  credLabel: '',
})

async function loadSavedCreds() {
  try {
    const res = await api.get('/ssh-credentials')
    savedCreds.value = res.data
  } catch { /* ignore */ }
}

function openSSHDialog(inst: any) {
  sshTarget.value = inst
  Object.assign(sshForm, { username: 'root', authType: 'password', password: '', privateKey: '', port: 22, savedCredId: '', saveCredential: false, credLabel: '' })
  loadSavedCreds()
  sshDialogVisible.value = true
}

async function onSelectSavedCred() {
  if (!sshForm.savedCredId) return
  try {
    const res = await api.get(`/ssh-credentials/${sshForm.savedCredId}/secret`)
    const cred = res.data
    sshForm.username = cred.username
    sshForm.port = cred.port
    sshForm.authType = cred.auth_type
    sshForm.password = cred.password || ''
    sshForm.privateKey = cred.private_key || ''
  } catch { /* ignore */ }
}

async function doSSHConnect() {
  if (!sshForm.username) { warning('请输入用户名'); return }
  if (sshForm.authType === 'password' && !sshForm.password) { warning('请输入密码'); return }
  if (sshForm.authType === 'key' && !sshForm.privateKey) { warning('请输入私钥'); return }

  if (sshForm.saveCredential) {
    try {
      await api.post('/ssh-credentials', {
        label: sshForm.credLabel || `${sshForm.username}@${sshTarget.value.public_ip}`,
        host: sshTarget.value.public_ip, port: sshForm.port, username: sshForm.username,
        auth_type: sshForm.authType,
        password: sshForm.authType === 'password' ? sshForm.password : null,
        private_key: sshForm.authType === 'key' ? sshForm.privateKey : null,
      })
    } catch { /* ignore */ }
  }

  sessionStorage.setItem('ssh_session', JSON.stringify({
    host: sshTarget.value.public_ip, port: sshForm.port, username: sshForm.username,
    authType: sshForm.authType,
    password: sshForm.authType === 'password' ? sshForm.password : '',
    privateKey: sshForm.authType === 'key' ? sshForm.privateKey : '',
    tenantId,
  }))
  sshDialogVisible.value = false
  router.push({ path: '/terminal' })
}

// ── Config ───────────────────────────────────────────────────────────────────
const configDialogVisible = ref(false)
const configTarget = ref<any>(null)
const configLoading = ref(false)
const configForm = reactive({ display_name: '', shape: '', ocpus: null as number | null, memory_in_gbs: null as number | null })

function openConfigDialog(inst: any) {
  openInstDropdownId.value = null
  configTarget.value = inst
  configForm.display_name = inst.display_name || ''
  configForm.shape = ''
  configForm.ocpus = inst.ocpus || null
  configForm.memory_in_gbs = inst.memory_in_gbs || null
  configDialogVisible.value = true
}

async function doUpdateConfig() {
  const payload: any = { region: configTarget.value.region }
  let hasChange = false
  if (configForm.display_name && configForm.display_name !== configTarget.value.display_name) { payload.display_name = configForm.display_name; hasChange = true }
  if (configForm.shape) { payload.shape = configForm.shape; hasChange = true }
  if (configForm.ocpus != null && configForm.ocpus !== configTarget.value.ocpus) { payload.ocpus = configForm.ocpus; hasChange = true }
  if (configForm.memory_in_gbs != null && configForm.memory_in_gbs !== configTarget.value.memory_in_gbs) { payload.memory_in_gbs = configForm.memory_in_gbs; hasChange = true }
  if (!hasChange) { warning('未检测到配置变更'); return }

  configLoading.value = true
  try {
    await api.put(`/instances/${tenantId}/${configTarget.value.id}/config`, payload)
    success('实例配置更新成功')
    configDialogVisible.value = false
    setTimeout(load, 3000)
  } catch { /* handled by interceptor */ } finally {
    configLoading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.dropdown-item {
  @apply w-full text-left px-3 py-2 text-sm text-surface-700 dark:text-surface-300 hover:bg-surface-100 dark:hover:bg-surface-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed;
}
</style>
