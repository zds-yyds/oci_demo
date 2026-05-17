<template>
  <div class="space-y-6">
    <!-- Page header -->
    <div class="flex items-center justify-between">
      <h2 class="text-2xl font-bold text-surface-900 dark:text-white">云账户管理</h2>
      <div class="flex items-center gap-2">
        <button class="btn-primary" @click="openAdd">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/></svg>
          添加账户
        </button>
        <button class="btn-secondary" @click="openExport">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2M7 10l5 5 5-5M12 15V3"/></svg>
          导出
        </button>
        <button class="btn-secondary" @click="openImport">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2M17 8l-5-5-5 5M12 3v12"/></svg>
          导入
        </button>
      </div>
    </div>

    <!-- Search bar -->
    <div class="flex items-center gap-3 flex-wrap">
      <input v-model="searchQuery" class="input" style="width:300px" placeholder="搜索账户名称、Tenancy OCID..." />
      <select v-model="filterRegion" class="select" style="width:180px">
        <option value="">全部区域</option>
        <option v-for="r in allRegionsInUse" :key="r" :value="r">{{ r }}</option>
      </select>
      <select v-model="filterStatus" class="select" style="width:130px">
        <option value="">全部状态</option>
        <option value="active">启用</option>
        <option value="inactive">禁用</option>
      </select>
      <select v-model="sortBy" class="select" style="width:160px">
        <option value="created_desc">创建时间 ↓</option>
        <option value="created_asc">创建时间 ↑</option>
        <option value="name_asc">名称 A→Z</option>
        <option value="name_desc">名称 Z→A</option>
        <option value="region_desc">区域数量 ↓</option>
        <option value="region_asc">区域数量 ↑</option>
      </select>
    </div>

    <!-- Tenants table -->
    <div class="card">
      <Loading :loading="loading" text="加载中..." />
      <div v-if="!loading" class="table-container">
        <table class="table">
          <thead>
            <tr>
              <th>账户名称</th>
              <th>区域</th>
              <th>Tenancy OCID</th>
              <th>状态</th>
              <th>创建时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in filteredTenants" :key="row.id">
              <td class="font-medium">{{ row.name }}</td>
              <td>
                <div class="flex flex-wrap gap-1">
                  <span v-for="r in row.region" :key="r" class="badge-info">{{ r }}</span>
                </div>
              </td>
              <td class="font-mono text-xs max-w-[200px] truncate" :title="row.tenancy_ocid">{{ row.tenancy_ocid }}</td>
              <td>
                <span :class="row.is_active ? 'badge-success' : 'badge-neutral'">
                  {{ row.is_active ? '启用' : '禁用' }}
                </span>
              </td>
              <td class="whitespace-nowrap">{{ formatDate(row.created_at) }}</td>
              <td>
                <div class="flex items-center gap-1">
                  <button class="btn-ghost btn-sm" @click="$router.push(`/instances/${row.id}`)">实例</button>
                  <button class="btn-ghost btn-sm" @click="testConn(row)">测试</button>
                  <button class="btn-ghost btn-sm" @click="openEdit(row)">编辑</button>
                  <div class="relative">
                    <button class="btn-ghost btn-sm" @click="toggleDropdown($event, row.id)">更多 ▾</button>
                  </div>
                </div>
              </td>
            </tr>
            <tr v-if="filteredTenants.length === 0 && !loading">
              <td colspan="6" class="text-center text-surface-400 py-8">暂无账户数据</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Dropdown menu (teleported to avoid overflow clipping) -->
    <Teleport to="body">
      <div v-if="openDropdownId !== null" class="fixed inset-0 z-[8000]" @click="openDropdownId = null">
        <div class="fixed w-44 bg-white dark:bg-surface-800 border border-surface-200 dark:border-surface-700 rounded-lg shadow-lg py-1" :style="dropdownStyle" @click.stop>
          <button class="dropdown-item" @click="navigateTo(`/security-rules/${openDropdownId}`)">安全列表</button>
          <button class="dropdown-item" @click="navigateTo(`/traffic/${openDropdownId}`)">流量统计</button>
          <button class="dropdown-item" @click="navigateTo(`/boot-volumes/${openDropdownId}`)">引导卷</button>
          <button class="dropdown-item" @click="navigateTo(`/vcn/${openDropdownId}`)">VCN 管理</button>
          <button class="dropdown-item" @click="navigateTo(`/limits/${openDropdownId}`)">配额查询</button>
          <button class="dropdown-item" @click="navigateTo(`/oci-users/${openDropdownId}`)">OCI 用户</button>
          <hr class="my-1 border-surface-200 dark:border-surface-700" />
          <button class="dropdown-item text-red-600 dark:text-red-400" @click="deleteTenantById(openDropdownId!)">删除账户</button>
        </div>
      </div>
    </Teleport>

    <!-- Add/Edit Modal -->
    <Modal :visible="dialogVisible" :title="editId ? '编辑账户' : '添加云账户'" width="600px" @close="dialogVisible = false">
      <!-- OCI Config import (only in add mode) -->
      <div v-if="!editId" class="mb-4">
        <p class="text-sm font-medium text-surface-600 dark:text-surface-400 mb-2">快速导入 OCI Config</p>
        <div class="flex items-center gap-3 mb-2">
          <button class="btn-secondary btn-sm" @click="showPasteArea = !showPasteArea">粘贴配置</button>
          <label class="btn-secondary btn-sm cursor-pointer">
            上传配置文件
            <input type="file" class="hidden" accept=".conf,.config,.pem,.txt,*" @change="handleFileUpload" />
          </label>
        </div>
        <div v-if="showPasteArea" class="space-y-2">
          <textarea v-model="pasteContent" class="input" rows="5" placeholder="粘贴 OCI config 内容，例如：
[DEFAULT]
user=ocid1.user.oc1..xxx
fingerprint=xx:xx:xx:...
tenancy=ocid1.tenancy.oc1..xxx
region=ap-singapore-1
key_file=xxx.pem"></textarea>
          <button class="btn-primary btn-sm" @click="parseAndFill">识别并填入表单</button>
        </div>
      </div>

      <div class="space-y-4">
        <div>
          <label class="label">账户名称 <span class="text-red-500">*</span></label>
          <input v-model="form.name" class="input" placeholder="自定义名称，如：我的OCI账户" />
        </div>
        <div>
          <label class="label">User OCID <span class="text-red-500">*</span></label>
          <input v-model="form.user_ocid" class="input" placeholder="ocid1.user.oc1.." />
        </div>
        <div>
          <label class="label">Fingerprint <span class="text-red-500">*</span></label>
          <input v-model="form.fingerprint" class="input" placeholder="xx:xx:xx:..." />
        </div>
        <div>
          <label class="label">Tenancy OCID <span class="text-red-500">*</span></label>
          <input v-model="form.tenancy_ocid" class="input" placeholder="ocid1.tenancy.oc1.." />
        </div>
        <div>
          <label class="label">Region <span class="text-red-500">*</span></label>
          <div class="flex flex-wrap gap-2 p-2 border border-surface-300 dark:border-surface-600 rounded-lg min-h-[40px]">
            <span v-for="r in form.region" :key="r" class="badge-info flex items-center gap-1">
              {{ r }}
              <button @click="removeRegion(r)" class="hover:text-red-500">&times;</button>
            </span>
          </div>
          <select class="select mt-2" @change="addRegion($event)">
            <option value="">选择区域添加...</option>
            <option v-for="r in availableRegions" :key="r" :value="r">{{ r }}</option>
          </select>
        </div>
        <div>
          <label class="label">私钥 (PEM)</label>
          <textarea v-model="form.private_key" class="input" rows="5" placeholder="留空表示使用个人设置中的默认私钥"></textarea>
        </div>
      </div>

      <template #footer>
        <button class="btn-secondary" @click="dialogVisible = false">取消</button>
        <button class="btn-primary" :disabled="saving" @click="save">
          {{ saving ? '保存中...' : '保存' }}
        </button>
      </template>
    </Modal>

    <!-- Export Modal -->
    <Modal :visible="exportDialogVisible" title="加密导出" width="440px" @close="exportDialogVisible = false">
      <div class="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg p-3 mb-4 text-sm text-amber-800 dark:text-amber-300">
        导出文件包含私钥等敏感信息，将使用 AES-256-GCM 加密保护。请牢记密码，丢失后无法恢复。
      </div>
      <div class="space-y-4">
        <div>
          <label class="label">加密密码</label>
          <input v-model="exportForm.password" type="password" class="input" placeholder="至少 6 个字符" />
        </div>
        <div>
          <label class="label">确认密码</label>
          <input v-model="exportForm.confirmPassword" type="password" class="input" placeholder="再次输入密码" />
        </div>
      </div>
      <template #footer>
        <button class="btn-secondary" @click="exportDialogVisible = false">取消</button>
        <button class="btn-primary" :disabled="exporting" @click="doExport">
          {{ exporting ? '导出中...' : '确认导出' }}
        </button>
      </template>
    </Modal>

    <!-- Import Modal -->
    <Modal :visible="importDialogVisible" title="导入备份" width="440px" @close="importDialogVisible = false">
      <div class="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-3 mb-4 text-sm text-blue-800 dark:text-blue-300">
        选择 .enc 备份文件并输入导出时设置的密码。已存在的账户（相同 Tenancy OCID）将被跳过。
      </div>
      <div class="space-y-4">
        <div>
          <label class="label">备份文件</label>
          <input type="file" accept=".enc" class="input" @change="handleImportFile" />
        </div>
        <div>
          <label class="label">解密密码</label>
          <input v-model="importForm.password" type="password" class="input" placeholder="输入导出时设置的密码" />
        </div>
      </div>
      <template #footer>
        <button class="btn-secondary" @click="importDialogVisible = false">取消</button>
        <button class="btn-primary" :disabled="importing" @click="doImport">
          {{ importing ? '导入中...' : '确认导入' }}
        </button>
      </template>
    </Modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/api'
import { useToast } from '@/composables/useToast'
import { useModal } from '@/composables/useModal'
import Modal from '@/components/Modal.vue'
import Loading from '@/components/Loading.vue'
import type { Tenant } from '@/types'
import dayjs from 'dayjs'

const router = useRouter()
const { success, warning, error } = useToast()
const { confirm } = useModal()

const tenants = ref<Tenant[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const saving = ref(false)
const editId = ref<number | null>(null)

const regions = ref<string[]>([])
const showPasteArea = ref(false)
const pasteContent = ref('')

// ── Search & Filter ──────────────────────────────────────────────────────────
const searchQuery = ref('')
const filterRegion = ref('')
const filterStatus = ref('')
const sortBy = ref(localStorage.getItem('tenants_sort') || 'created_desc')

// Persist sort preference
watch(sortBy, (val) => localStorage.setItem('tenants_sort', val))

const allRegionsInUse = computed(() => {
  const regionSet = new Set<string>()
  for (const t of tenants.value) {
    for (const r of (t.region || [])) {
      regionSet.add(r)
    }
  }
  return [...regionSet].sort()
})

const filteredTenants = computed(() => {
  let list = tenants.value

  if (searchQuery.value.trim()) {
    const q = searchQuery.value.toLowerCase()
    list = list.filter(t =>
      t.name.toLowerCase().includes(q) ||
      t.tenancy_ocid.toLowerCase().includes(q) ||
      (t.user_ocid && t.user_ocid.toLowerCase().includes(q)) ||
      (t.fingerprint && t.fingerprint.toLowerCase().includes(q))
    )
  }

  if (filterRegion.value) {
    list = list.filter(t => (t.region || []).includes(filterRegion.value))
  }

  if (filterStatus.value) {
    list = list.filter(t => filterStatus.value === 'active' ? t.is_active : !t.is_active)
  }

  list = [...list]
  switch (sortBy.value) {
    case 'created_desc':
      list.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
      break
    case 'created_asc':
      list.sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime())
      break
    case 'name_asc':
      list.sort((a, b) => a.name.localeCompare(b.name))
      break
    case 'name_desc':
      list.sort((a, b) => b.name.localeCompare(a.name))
      break
    case 'region_desc':
      list.sort((a, b) => (b.region?.length || 0) - (a.region?.length || 0))
      break
    case 'region_asc':
      list.sort((a, b) => (a.region?.length || 0) - (b.region?.length || 0))
      break
  }

  return list
})

// ── Dropdown ─────────────────────────────────────────────────────────────────
const openDropdownId = ref<number | null>(null)
const dropdownStyle = ref({ top: '0px', left: '0px' })

function toggleDropdown(event: MouseEvent, id: number) {
  if (openDropdownId.value === id) {
    openDropdownId.value = null
    return
  }
  const btn = event.currentTarget as HTMLElement
  const rect = btn.getBoundingClientRect()
  dropdownStyle.value = {
    top: `${rect.bottom + 4}px`,
    left: `${rect.right - 176}px`, // 176 = w-44 = 11rem
  }
  openDropdownId.value = id
}

function navigateTo(path: string) {
  openDropdownId.value = null
  router.push(path)
}

onMounted(() => {
  load()
  loadRegions()
})

// ── Export ───────────────────────────────────────────────────────────────────
const exportDialogVisible = ref(false)
const exporting = ref(false)
const exportForm = reactive({ password: '', confirmPassword: '' })

function openExport() {
  exportForm.password = ''
  exportForm.confirmPassword = ''
  exportDialogVisible.value = true
}

async function doExport() {
  if (exportForm.password.length < 6) { warning('密码至少 6 个字符'); return }
  if (exportForm.password !== exportForm.confirmPassword) { warning('两次密码不一致'); return }
  exporting.value = true
  try {
    const res = await api.post('/tenants/export', { password: exportForm.password }, { responseType: 'blob' })
    const blob = new Blob([res.data], { type: 'application/octet-stream' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'oci_tenants_backup.enc'
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    success('导出成功，请妥善保管备份文件和密码')
    exportDialogVisible.value = false
  } finally {
    exporting.value = false
  }
}

// ── Import ───────────────────────────────────────────────────────────────────
const importDialogVisible = ref(false)
const importing = ref(false)
const importForm = reactive({ password: '', file: null as File | null })

function openImport() {
  importForm.password = ''
  importForm.file = null
  importDialogVisible.value = true
}

function handleImportFile(e: Event) {
  const target = e.target as HTMLInputElement
  importForm.file = target.files?.[0] || null
}

async function doImport() {
  if (!importForm.file) { warning('请选择备份文件'); return }
  if (!importForm.password) { warning('请输入解密密码'); return }
  importing.value = true
  try {
    const fileContent = await readFileAsBase64(importForm.file)
    const res = await api.post('/tenants/import', {
      password: importForm.password,
      file_content: fileContent,
    })
    const { created, skipped, skipped_names } = res.data
    let msg = `导入完成：成功 ${created} 个`
    if (skipped > 0) {
      msg += `，跳过 ${skipped} 个（${skipped_names.join('、')}）`
    }
    success(msg)
    importDialogVisible.value = false
    load()
  } finally {
    importing.value = false
  }
}

function readFileAsBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      const base64 = (reader.result as string).split(',')[1]
      resolve(base64)
    }
    reader.onerror = reject
    reader.readAsDataURL(file)
  })
}

// ── Form ─────────────────────────────────────────────────────────────────────
const form = reactive({
  name: '', user_ocid: '', fingerprint: '', tenancy_ocid: '', region: [] as string[], private_key: '',
})

const availableRegions = computed(() => regions.value.filter(r => !form.region.includes(r)))

function addRegion(e: Event) {
  const val = (e.target as HTMLSelectElement).value
  if (val && !form.region.includes(val)) {
    form.region.push(val)
  }
  ;(e.target as HTMLSelectElement).value = ''
}

function removeRegion(r: string) {
  form.region = form.region.filter(x => x !== r)
}

function formatDate(d: string) { return dayjs(d).format('YYYY-MM-DD HH:mm') }

function parseOciConfig(text: string) {
  const result: Record<string, string> = {}
  const lines = text.split(/\r?\n/)
  for (const line of lines) {
    const trimmed = line.trim()
    if (!trimmed || trimmed.startsWith('#') || trimmed.startsWith('[')) continue
    const eqIndex = trimmed.indexOf('=')
    if (eqIndex === -1) continue
    const key = trimmed.substring(0, eqIndex).trim().toLowerCase()
    const value = trimmed.substring(eqIndex + 1).trim()
    if (!value || key === 'key_file') continue
    result[key] = value
  }
  return result
}

function fillFormFromConfig(parsed: Record<string, string>) {
  let filled = 0
  if (parsed.user) { form.user_ocid = parsed.user; filled++ }
  if (parsed.fingerprint) { form.fingerprint = parsed.fingerprint; filled++ }
  if (parsed.tenancy) { form.tenancy_ocid = parsed.tenancy; filled++ }
  if (parsed.region) {
    if (!form.region.includes(parsed.region)) form.region = [parsed.region]
    filled++
  }
  return filled
}

function parseAndFill() {
  if (!pasteContent.value.trim()) { warning('请先粘贴配置内容'); return }
  const parsed = parseOciConfig(pasteContent.value)
  const filled = fillFormFromConfig(parsed)
  if (filled === 0) {
    error('未能识别有效的配置项，请检查格式')
  } else {
    success(`已识别并填入 ${filled} 项配置，请检查后保存`)
    showPasteArea.value = false
    pasteContent.value = ''
  }
}

function handleFileUpload(e: Event) {
  const target = e.target as HTMLInputElement
  const file = target.files?.[0]
  if (!file) return
  const reader = new FileReader()
  reader.onload = (ev) => {
    const content = ev.target?.result as string
    const parsed = parseOciConfig(content)
    const filled = fillFormFromConfig(parsed)
    if (filled === 0) {
      error('文件中未能识别有效的配置项，请检查文件格式')
    } else {
      success(`已从文件识别并填入 ${filled} 项配置，请检查后保存`)
    }
  }
  reader.onerror = () => { error('文件读取失败') }
  reader.readAsText(file)
}

async function load() {
  loading.value = true
  try {
    const res = await api.get('/tenants')
    tenants.value = res.data
  } finally {
    loading.value = false
  }
}

function openAdd() {
  editId.value = null
  Object.assign(form, { name: '', user_ocid: '', fingerprint: '', tenancy_ocid: '', region: [], private_key: '' })
  showPasteArea.value = false
  pasteContent.value = ''
  dialogVisible.value = true
}

function openEdit(row: Tenant) {
  editId.value = row.id
  Object.assign(form, {
    name: row.name,
    user_ocid: row.user_ocid || '',
    fingerprint: row.fingerprint || '',
    tenancy_ocid: row.tenancy_ocid,
    region: [...(row.region || [])],
    private_key: '',
  })
  dialogVisible.value = true
}

async function save() {
  if (!form.name) { warning('请输入账户名称'); return }
  if (!form.user_ocid) { warning('请输入 User OCID'); return }
  if (!form.fingerprint) { warning('请输入 Fingerprint'); return }
  if (!form.tenancy_ocid) { warning('请输入 Tenancy OCID'); return }
  if (form.region.length === 0) { warning('请至少选择一个区域'); return }

  saving.value = true
  try {
    const payload: any = { ...form }
    if (!payload.private_key) delete payload.private_key
    if (editId.value) {
      await api.put(`/tenants/${editId.value}`, payload)
      success('更新成功')
    } else {
      await api.post('/tenants', payload)
      success('添加成功')
    }
    dialogVisible.value = false
    load()
  } finally {
    saving.value = false
  }
}

async function deleteTenant(row: Tenant) {
  openDropdownId.value = null
  const ok = await confirm(`确认删除账户「${row.name}」？`, '警告', { type: 'warning' })
  if (!ok) return
  await api.delete(`/tenants/${row.id}`)
  success('删除成功')
  load()
}

async function deleteTenantById(id: number) {
  const row = tenants.value.find(t => t.id === id)
  if (row) await deleteTenant(row)
}

async function testConn(row: Tenant) {
  const { info } = useToast()
  info('正在测试连接（遍历所有区域）...')
  try {
    const res = await api.get(`/tenants/${row.id}/test`)
    if (res.data.status === 'ok') {
      const regionResults = res.data.regions || {}
      const details = Object.entries(regionResults)
        .map(([r, s]) => `${r}: ${s === 'ok' ? '✓' : '✗'}`)
        .join(', ')
      success(`连接成功！租户: ${res.data.tenancy_name} | ${details}`)
    } else {
      error(`连接失败: ${res.data.detail}`)
    }
  } catch { /* handled by interceptor */ }
}

async function loadRegions() {
  try {
    const res = await api.get('/regions')
    regions.value = res.data.map((r: any) => r.identifier)
  } catch {
    regions.value = []
  }
}
</script>

<style scoped>
.dropdown-item {
  @apply w-full text-left px-3 py-2 text-sm text-surface-700 dark:text-surface-300 hover:bg-surface-100 dark:hover:bg-surface-700 transition-colors;
}
</style>
