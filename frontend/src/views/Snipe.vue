<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <h2 class="text-2xl font-bold text-surface-900 dark:text-white">抢机任务</h2>
      <button class="btn-primary" @click="openAdd">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" /></svg>
        新建任务
      </button>
    </div>

    <div class="card">
      <Loading :loading="loading" text="加载中..." />
      <div v-if="!loading" class="table-container">
        <table class="table">
          <thead>
            <tr>
              <th>租户</th>
              <th>区域</th>
              <th>类型</th>
              <th>配置</th>
              <th>状态</th>
              <th>尝试次数</th>
              <th>获得IP</th>
              <th>创建时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="task in tasks" :key="task.id">
              <td class="font-medium">{{ tenantName(task.tenant_id) }}</td>
              <td class="text-xs font-mono">{{ task.region }}</td>
              <td>{{ task.shape_name }}</td>
              <td class="text-xs">{{ task.instance_ocpus }}C / {{ task.instance_memory_in_gbs }}G / {{ task.boot_volume_size_in_gbs }}G</td>
              <td><span :class="statusBadge(task.status)">{{ task.status }}</span></td>
              <td>{{ task.attempt_count }}</td>
              <td class="font-mono text-xs">{{ task.result_ip || '-' }}</td>
              <td class="text-xs text-surface-500">{{ formatDate(task.created_at) }}</td>
              <td>
                <div class="flex items-center gap-1">
                  <button v-if="task.status !== 'running'" class="btn-ghost btn-sm text-primary-600 dark:text-primary-400" @click="startTask(task)">启动</button>
                  <button v-if="task.status === 'running'" class="btn-ghost btn-sm text-amber-600 dark:text-amber-400" @click="stopTask(task)">停止</button>
                  <button class="btn-ghost btn-sm" @click="viewLog(task)">日志</button>
                  <button class="btn-ghost btn-sm text-red-600 dark:text-red-400" @click="deleteTask(task)">删除</button>
                </div>
              </td>
            </tr>
            <tr v-if="tasks.length === 0">
              <td colspan="9" class="text-center text-surface-400 py-12">暂无任务</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Create dialog -->
    <Modal :visible="dialogVisible" title="新建抢机任务" width="560px" @close="dialogVisible = false">
      <form class="space-y-4" @submit.prevent="save">
        <div>
          <label class="label">云账户</label>
          <select v-model="form.tenant_id" class="select" required @change="onTenantChange">
            <option :value="null" disabled>选择云账户</option>
            <option v-for="t in tenants" :key="t.id" :value="t.id">{{ t.name }}</option>
          </select>
        </div>
        <div>
          <label class="label">区域</label>
          <select v-model="form.region" class="select" required>
            <option value="" disabled>选择区域</option>
            <option v-for="r in selectedTenantRegions" :key="r" :value="r">{{ r }}</option>
          </select>
        </div>
        <div>
          <label class="label">实例类型</label>
          <div class="flex gap-2">
            <button type="button" @click="form.shape_name = 'arm'" class="flex-1 py-2 rounded-lg border text-sm font-medium transition-all" :class="form.shape_name === 'arm' ? 'border-primary-500 bg-primary-50 dark:bg-primary-950/50 text-primary-700 dark:text-primary-300' : 'border-surface-300 dark:border-surface-600 text-surface-600 dark:text-surface-400 hover:border-surface-400'">
              ARM (A1.Flex)
            </button>
            <button type="button" @click="form.shape_name = 'amd'" class="flex-1 py-2 rounded-lg border text-sm font-medium transition-all" :class="form.shape_name === 'amd' ? 'border-primary-500 bg-primary-50 dark:bg-primary-950/50 text-primary-700 dark:text-primary-300' : 'border-surface-300 dark:border-surface-600 text-surface-600 dark:text-surface-400 hover:border-surface-400'">
              AMD (E2.1.Micro)
            </button>
          </div>
        </div>
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="label">OCPU 数量</label>
            <input v-model.number="form.instance_ocpus" type="number" min="1" max="80" class="input" />
          </div>
          <div>
            <label class="label">内存 (GB)</label>
            <input v-model.number="form.instance_memory_in_gbs" type="number" min="1" max="512" class="input" />
          </div>
          <div>
            <label class="label">引导卷 (GB)</label>
            <input v-model.number="form.boot_volume_size_in_gbs" type="number" min="50" max="32768" class="input" />
          </div>
          <div>
            <label class="label">抢机频率 (s)</label>
            <input v-model.number="form.frequency" type="number" min="1" max="60" class="input" />
          </div>
        </div>
        <div>
          <label class="label">SSH 公钥</label>
          <textarea v-model="form.ssh_public_key" class="input min-h-[80px] resize-y" placeholder="留空表示使用个人设置中的默认 SSH 公钥"></textarea>
        </div>
      </form>
      <template #footer>
        <button class="btn-secondary" @click="dialogVisible = false">取消</button>
        <button class="btn-primary" :disabled="saving" @click="save">
          {{ saving ? '创建中...' : '创建并启动' }}
        </button>
      </template>
    </Modal>

    <!-- Log dialog -->
    <Modal :visible="logVisible" title="任务日志" width="700px" @close="logVisible = false">
      <div class="bg-surface-900 rounded-xl p-4 max-h-[400px] overflow-y-auto">
        <pre class="text-emerald-400 font-mono text-xs whitespace-pre-wrap break-all">{{ currentLog || '暂无日志' }}</pre>
      </div>
      <template #footer>
        <button class="btn-secondary" @click="refreshLog">刷新</button>
        <button class="btn-secondary" @click="logVisible = false">关闭</button>
      </template>
    </Modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import api from '@/api'
import dayjs from 'dayjs'
import { useToast } from '@/composables/useToast'
import { useModal } from '@/composables/useModal'
import Modal from '@/components/Modal.vue'
import Loading from '@/components/Loading.vue'
import type { SnipeTask, Tenant } from '@/types'

const { success } = useToast()
const { confirm } = useModal()

const tasks = ref<SnipeTask[]>([])
const tenants = ref<Tenant[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const logVisible = ref(false)
const saving = ref(false)
const currentLog = ref('')
const currentTaskId = ref<number | null>(null)
let refreshTimer: ReturnType<typeof setInterval> | null = null

const form = reactive({
  tenant_id: null as number | null,
  region: '',
  shape_name: 'arm',
  instance_ocpus: 4,
  instance_memory_in_gbs: 24,
  boot_volume_size_in_gbs: 100,
  frequency: 10,
  ssh_public_key: '',
})

const selectedTenantRegions = ref<string[]>([])

function onTenantChange() {
  const t = tenants.value.find(x => x.id === form.tenant_id)
  selectedTenantRegions.value = t?.region || []
  form.region = selectedTenantRegions.value.length > 0 ? selectedTenantRegions.value[0] : ''
}

function statusBadge(s: string) {
  switch (s) {
    case 'running': return 'badge-warning'
    case 'success': return 'badge-success'
    case 'failed': return 'badge-danger'
    case 'stopped': return 'badge-neutral'
    default: return 'badge-info'
  }
}

function formatDate(d: string) { return dayjs(d).format('YYYY-MM-DD HH:mm') }
function tenantName(id: number) { return tenants.value.find(t => t.id === id)?.name || String(id) }

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
  Object.assign(form, { tenant_id: null, region: '', shape_name: 'arm', instance_ocpus: 4, instance_memory_in_gbs: 24, boot_volume_size_in_gbs: 100, frequency: 10, ssh_public_key: '' })
  selectedTenantRegions.value = []
  dialogVisible.value = true
}

async function save() {
  if (!form.tenant_id || !form.region) return
  saving.value = true
  try {
    const res = await api.post('/snipe', form)
    const taskId = res.data.id
    await api.post(`/snipe/${taskId}/start`)
    success('任务已创建并启动')
    dialogVisible.value = false
    load()
  } finally {
    saving.value = false
  }
}

async function startTask(row: SnipeTask) {
  await api.post(`/snipe/${row.id}/start`)
  success('任务已启动')
  load()
}

async function stopTask(row: SnipeTask) {
  await api.post(`/snipe/${row.id}/stop`)
  success('停止信号已发送')
  load()
}

async function deleteTask(row: SnipeTask) {
  const ok = await confirm('确认删除该任务？', '警告', { type: 'warning' })
  if (!ok) return
  await api.delete(`/snipe/${row.id}`)
  success('删除成功')
  load()
}

async function viewLog(row: SnipeTask) {
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
onUnmounted(() => { if (refreshTimer) clearInterval(refreshTimer) })
</script>
