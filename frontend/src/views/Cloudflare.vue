<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <h2 class="text-2xl font-bold text-surface-900 dark:text-white">Cloudflare DNS 管理</h2>
      <button class="btn-primary" @click="openAddCfg">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" /></svg>
        添加配置
      </button>
    </div>

    <!-- Config selector -->
    <div class="card p-5">
      <div class="flex items-center gap-4 flex-wrap">
        <div>
          <label class="label">CF 配置</label>
          <select v-model="selectedCfgId" class="select w-72" @change="onCfgChange">
            <option :value="null" disabled>选择 Cloudflare 配置</option>
            <option v-for="c in configs" :key="c.id" :value="c.id">{{ c.name }} ({{ c.domain || c.zone_id }})</option>
          </select>
        </div>
        <div v-if="selectedCfgId" class="flex items-center gap-2 pt-5">
          <button class="btn-ghost btn-sm" @click="openEditCfg">编辑</button>
          <button class="btn-ghost btn-sm text-red-600 dark:text-red-400" @click="doDeleteCfg">删除</button>
        </div>
        <div class="flex-1"></div>
        <div v-if="selectedCfgId" class="flex items-center gap-3 pt-5">
          <select v-model="filterType" class="select w-32" @change="loadRecords">
            <option value="">全部类型</option>
            <option value="A">A</option>
            <option value="AAAA">AAAA</option>
            <option value="CNAME">CNAME</option>
            <option value="MX">MX</option>
            <option value="TXT">TXT</option>
            <option value="NS">NS</option>
            <option value="SRV">SRV</option>
          </select>
          <button class="btn-primary btn-sm" @click="openAddRecord">添加记录</button>
        </div>
      </div>
    </div>

    <!-- DNS Records -->
    <div v-if="selectedCfgId" class="card">
      <Loading :loading="recordsLoading" />
      <div v-if="!recordsLoading && records.length === 0" class="p-12 text-center text-surface-400">暂无 DNS 记录</div>
      <div v-if="records.length > 0" class="table-container">
        <table class="table">
          <thead>
            <tr>
              <th>类型</th>
              <th>名称</th>
              <th>内容</th>
              <th>代理</th>
              <th>TTL</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in records" :key="r.id">
              <td><span class="badge-info">{{ r.type }}</span></td>
              <td class="font-mono text-xs">{{ r.name }}</td>
              <td class="font-mono text-xs max-w-[200px] truncate">{{ r.content }}</td>
              <td><span :class="r.proxied ? 'badge-warning' : 'badge-neutral'">{{ r.proxied ? '开' : '关' }}</span></td>
              <td>{{ r.ttl === 1 ? 'Auto' : r.ttl }}</td>
              <td>
                <div class="flex items-center gap-1">
                  <button class="btn-ghost btn-sm" @click="openEditRecord(r)">编辑</button>
                  <button class="btn-ghost btn-sm text-red-600 dark:text-red-400" @click="doDeleteRecord(r)">删除</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="totalRecords > 0" class="px-5 py-3 text-sm text-surface-400 border-t border-surface-100 dark:border-surface-700">
        共 {{ totalRecords }} 条记录
      </div>
    </div>

    <!-- CF Config Dialog -->
    <Modal :visible="cfgDialogVisible" :title="editCfgId ? '编辑 CF 配置' : '添加 CF 配置'" width="500px" @close="cfgDialogVisible = false">
      <form class="space-y-4" @submit.prevent="saveCfg">
        <div>
          <label class="label">名称</label>
          <input v-model="cfgForm.name" class="input" placeholder="自定义名称" required />
        </div>
        <div>
          <label class="label">API Token</label>
          <input v-model="cfgForm.api_token" type="password" class="input" placeholder="Cloudflare API Token" :required="!editCfgId" />
        </div>
        <div>
          <label class="label">Zone ID</label>
          <input v-model="cfgForm.zone_id" class="input" placeholder="在 CF 域名概览页底部可找到" required />
        </div>
        <div>
          <label class="label">域名（可选）</label>
          <input v-model="cfgForm.domain" class="input" placeholder="如 example.com（会自动获取）" />
        </div>
      </form>
      <template #footer>
        <button class="btn-secondary" @click="cfgDialogVisible = false">取消</button>
        <button class="btn-primary" :disabled="cfgSaving" @click="saveCfg">保存</button>
      </template>
    </Modal>

    <!-- DNS Record Dialog -->
    <Modal :visible="recordDialogVisible" :title="editRecordId ? '编辑 DNS 记录' : '添加 DNS 记录'" width="520px" @close="recordDialogVisible = false">
      <form class="space-y-4" @submit.prevent="saveRecord">
        <div>
          <label class="label">类型</label>
          <select v-model="recordForm.type" class="select">
            <option value="A">A (IPv4)</option>
            <option value="AAAA">AAAA (IPv6)</option>
            <option value="CNAME">CNAME</option>
            <option value="MX">MX</option>
            <option value="TXT">TXT</option>
            <option value="NS">NS</option>
            <option value="SRV">SRV</option>
          </select>
        </div>
        <div>
          <label class="label">名称</label>
          <input v-model="recordForm.name" class="input" placeholder="如 www 或 @ 表示根域名" required />
        </div>
        <div>
          <label class="label">内容</label>
          <input v-model="recordForm.content" class="input" placeholder="如 IP 地址或目标域名" required />
        </div>
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="label">TTL</label>
            <select v-model.number="recordForm.ttl" class="select">
              <option :value="1">Auto</option>
              <option :value="60">1 分钟</option>
              <option :value="300">5 分钟</option>
              <option :value="1800">30 分钟</option>
              <option :value="3600">1 小时</option>
              <option :value="86400">1 天</option>
            </select>
          </div>
          <div>
            <label class="label">代理</label>
            <button type="button" @click="recordForm.proxied = !recordForm.proxied" class="mt-1 relative w-11 h-6 rounded-full transition-colors" :class="recordForm.proxied ? 'bg-primary-600' : 'bg-surface-300 dark:bg-surface-600'">
              <span class="absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform" :class="recordForm.proxied ? 'translate-x-5' : ''"></span>
            </button>
          </div>
        </div>
      </form>
      <template #footer>
        <button class="btn-secondary" @click="recordDialogVisible = false">取消</button>
        <button class="btn-primary" :disabled="recordSaving" @click="saveRecord">保存</button>
      </template>
    </Modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useToast } from '@/composables/useToast'
import { useModal } from '@/composables/useModal'
import api from '@/api'
import Modal from '@/components/Modal.vue'
import Loading from '@/components/Loading.vue'
import type { CfConfig, DnsRecord } from '@/types'

const { success } = useToast()
const { confirm } = useModal()

const configs = ref<CfConfig[]>([])
const selectedCfgId = ref<number | null>(null)
const cfgDialogVisible = ref(false)
const cfgSaving = ref(false)
const editCfgId = ref<number | null>(null)
const cfgForm = reactive({ name: '', api_token: '', zone_id: '', domain: '' })

const records = ref<DnsRecord[]>([])
const totalRecords = ref(0)
const recordsLoading = ref(false)
const filterType = ref('')
const recordDialogVisible = ref(false)
const recordSaving = ref(false)
const editRecordId = ref<string | null>(null)
const recordForm = reactive({ type: 'A', name: '', content: '', ttl: 1, proxied: false })

async function loadConfigs() {
  const res = await api.get('/cloudflare/configs')
  configs.value = res.data
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
  cfgSaving.value = true
  try {
    if (editCfgId.value) {
      const payload: any = {}
      if (cfgForm.name) payload.name = cfgForm.name
      if (cfgForm.api_token) payload.api_token = cfgForm.api_token
      if (cfgForm.zone_id) payload.zone_id = cfgForm.zone_id
      if (cfgForm.domain) payload.domain = cfgForm.domain
      await api.put(`/cloudflare/configs/${editCfgId.value}`, payload)
      success('更新成功')
    } else {
      await api.post('/cloudflare/configs', cfgForm)
      success('添加成功')
    }
    cfgDialogVisible.value = false
    await loadConfigs()
  } finally { cfgSaving.value = false }
}

async function doDeleteCfg() {
  const ok = await confirm('确认删除该 CF 配置？', '警告', { type: 'warning' })
  if (!ok) return
  await api.delete(`/cloudflare/configs/${selectedCfgId.value}`)
  success('删除成功')
  selectedCfgId.value = null
  records.value = []
  await loadConfigs()
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
    const params: any = { cfg_id: selectedCfgId.value, per_page: 100 }
    if (filterType.value) params.type = filterType.value
    const res = await api.get('/cloudflare/dns-records', { params })
    records.value = res.data.records
    totalRecords.value = res.data.total
  } finally { recordsLoading.value = false }
}

function openAddRecord() {
  editRecordId.value = null
  Object.assign(recordForm, { type: 'A', name: '', content: '', ttl: 1, proxied: false })
  recordDialogVisible.value = true
}

function openEditRecord(row: DnsRecord) {
  editRecordId.value = row.id
  Object.assign(recordForm, { type: row.type, name: row.name, content: row.content, ttl: row.ttl, proxied: row.proxied })
  recordDialogVisible.value = true
}

async function saveRecord() {
  recordSaving.value = true
  try {
    if (editRecordId.value) {
      await api.put('/cloudflare/dns-records', { cfg_id: selectedCfgId.value, record_id: editRecordId.value, ...recordForm })
      success('更新成功')
    } else {
      await api.post('/cloudflare/dns-records', { cfg_id: selectedCfgId.value, ...recordForm })
      success('添加成功')
    }
    recordDialogVisible.value = false
    await loadRecords()
  } finally { recordSaving.value = false }
}

async function doDeleteRecord(row: DnsRecord) {
  const ok = await confirm(`确认删除记录「${row.name}」？`, '警告', { type: 'warning' })
  if (!ok) return
  await api.post('/cloudflare/dns-records/delete', { cfg_id: selectedCfgId.value, record_ids: [row.id] })
  success('删除成功')
  await loadRecords()
}

onMounted(loadConfigs)
</script>
