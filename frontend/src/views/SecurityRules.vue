<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-3">
        <button class="btn-ghost btn-sm" @click="$router.back()">← 返回</button>
        <h2 class="text-2xl font-bold text-surface-900 dark:text-white">安全列表管理 — {{ tenantName }}</h2>
      </div>
      <button class="btn-primary btn-sm" @click="doReleaseAll">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 11V7a4 4 0 118 0m-4 8v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2z" /></svg>
        一键放行所有端口
      </button>
    </div>

    <!-- Filters -->
    <div class="card p-4">
      <div class="flex items-center gap-3 flex-wrap">
        <span class="text-sm text-surface-500 shrink-0">区域</span>
        <select v-model="selectedRegion" class="select w-44" @change="onRegionChange">
          <option value="">选择区域</option>
          <option v-for="r in regions" :key="r" :value="r">{{ r }}</option>
        </select>

        <span class="text-sm text-surface-500 shrink-0">VCN</span>
        <select v-model="selectedVcn" class="select w-56" @change="loadRules">
          <option value="">选择 VCN</option>
          <option v-for="v in vcnList" :key="v.vcn_id" :value="v.vcn_id">{{ v.display_name }}</option>
        </select>

        <template v-if="selectedVcn">
          <div class="flex gap-0 shrink-0">
            <button
              class="px-3 py-1.5 text-sm font-medium rounded-l-lg border transition-colors"
              :class="ruleType === 0 ? 'bg-primary-600 text-white border-primary-600' : 'bg-white dark:bg-surface-800 text-surface-600 dark:text-surface-400 border-surface-300 dark:border-surface-600'"
              @click="ruleType = 0; loadRules()"
            >入站规则</button>
            <button
              class="px-3 py-1.5 text-sm font-medium rounded-r-lg border border-l-0 transition-colors"
              :class="ruleType === 1 ? 'bg-primary-600 text-white border-primary-600' : 'bg-white dark:bg-surface-800 text-surface-600 dark:text-surface-400 border-surface-300 dark:border-surface-600'"
              @click="ruleType = 1; loadRules()"
            >出站规则</button>
          </div>

          <button class="btn-ghost btn-sm shrink-0" :disabled="rulesLoading" @click="loadRules">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>
          </button>
          <button class="btn-primary btn-sm shrink-0" @click="openAddDialog">+ 添加规则</button>
        </template>
      </div>
    </div>

    <!-- Rules Table -->
    <div class="card overflow-hidden">
      <Loading :loading="rulesLoading" text="加载规则中..." />
      <div v-if="!rulesLoading && rules.length === 0" class="text-center text-surface-400 py-8">暂无安全规则</div>
      <div v-if="!rulesLoading && rules.length > 0" class="table-container">
        <table class="table">
          <thead>
            <tr>
              <th>无状态</th>
              <th>协议</th>
              <th>{{ ruleType === 0 ? '来源' : '目标' }}</th>
              <th>源端口</th>
              <th>目标端口</th>
              <th>类型和代码</th>
              <th>描述</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(rule, idx) in rules" :key="idx">
              <td>
                <span :class="rule.is_stateless ? 'badge-warning' : 'badge-neutral'">{{ rule.is_stateless ? '是' : '否' }}</span>
              </td>
              <td>{{ rule.protocol }}</td>
              <td class="text-xs font-mono">{{ rule.source_or_destination || '-' }}</td>
              <td class="text-xs">{{ rule.source_port || '' }}</td>
              <td class="text-xs">{{ rule.destination_port || '' }}</td>
              <td class="text-xs">{{ rule.type_and_code || '' }}</td>
              <td class="max-w-[150px] truncate text-xs" :title="rule.description">{{ rule.description || '' }}</td>
              <td>
                <button class="btn-ghost btn-sm text-red-600 dark:text-red-400" @click="doRemoveRule(idx)">
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Add Rule Modal -->
    <Modal :visible="addDialogVisible" title="添加安全规则" width="560px" @close="addDialogVisible = false">
      <div class="space-y-4">
        <div>
          <label class="label">方向</label>
          <div class="flex gap-2">
            <button type="button" @click="addForm.direction = 'INGRESS'" class="flex-1 py-2 rounded-lg border text-sm font-medium transition-all" :class="addForm.direction === 'INGRESS' ? 'border-primary-500 bg-primary-50 dark:bg-primary-950/50 text-primary-700 dark:text-primary-300' : 'border-surface-300 dark:border-surface-600 text-surface-600 dark:text-surface-400'">
              入站 (Ingress)
            </button>
            <button type="button" @click="addForm.direction = 'EGRESS'" class="flex-1 py-2 rounded-lg border text-sm font-medium transition-all" :class="addForm.direction === 'EGRESS' ? 'border-primary-500 bg-primary-50 dark:bg-primary-950/50 text-primary-700 dark:text-primary-300' : 'border-surface-300 dark:border-surface-600 text-surface-600 dark:text-surface-400'">
              出站 (Egress)
            </button>
          </div>
        </div>
        <div class="flex items-center gap-2">
          <input type="checkbox" v-model="addForm.is_stateless" id="stateless" class="accent-primary-600" />
          <label for="stateless" class="text-sm text-surface-700 dark:text-surface-300">无状态</label>
        </div>
        <div>
          <label class="label">{{ addForm.direction === 'INGRESS' ? '来源类型' : '目标类型' }}</label>
          <select v-model="addForm.type" class="select">
            <option value="CIDR_BLOCK">CIDR 块</option>
            <option value="SERVICE_CIDR_BLOCK">服务 CIDR</option>
          </select>
        </div>
        <div>
          <label class="label">{{ addForm.direction === 'INGRESS' ? '来源 CIDR' : '目标 CIDR' }}</label>
          <input v-model="addForm.cidr" class="input" placeholder="0.0.0.0/0" />
        </div>
        <div>
          <label class="label">协议</label>
          <select v-model="addForm.protocol" class="select">
            <option value="all">所有协议</option>
            <option value="6">TCP (6)</option>
            <option value="17">UDP (17)</option>
            <option value="1">ICMP (1)</option>
          </select>
        </div>
        <div v-if="addForm.protocol === '6' || addForm.protocol === '17'">
          <label class="label">源端口</label>
          <input v-model="addForm.source_port" class="input" placeholder="留空表示全部，如 80 或 1024-65535" />
        </div>
        <div v-if="addForm.protocol === '6' || addForm.protocol === '17'">
          <label class="label">目标端口</label>
          <input v-model="addForm.destination_port" class="input" placeholder="留空表示全部，如 443 或 8000-9000" />
        </div>
        <div v-if="addForm.protocol === '1'">
          <label class="label">ICMP 类型</label>
          <input v-model.number="addForm.icmp_type" type="number" class="input" min="0" max="255" placeholder="0-255" />
        </div>
        <div v-if="addForm.protocol === '1'">
          <label class="label">ICMP 代码</label>
          <input v-model.number="addForm.icmp_code" type="number" class="input" min="0" max="255" placeholder="0-255" />
        </div>
        <div>
          <label class="label">描述</label>
          <input v-model="addForm.description" class="input" placeholder="可选" />
        </div>
      </div>
      <template #footer>
        <button class="btn-secondary" @click="addDialogVisible = false">取消</button>
        <button class="btn-primary" :disabled="addLoading" @click="doAddRule">
          {{ addLoading ? '添加中...' : '确认添加' }}
        </button>
      </template>
    </Modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import api from '@/api'
import { useToast } from '@/composables/useToast'
import { useModal } from '@/composables/useModal'
import Modal from '@/components/Modal.vue'
import Loading from '@/components/Loading.vue'

const route = useRoute()
const { success, warning } = useToast()
const { confirm } = useModal()

const tenantId = route.params.tenantId as string
const tenantName = ref('')
const regions = ref<string[]>([])
const selectedRegion = ref('')
const vcnList = ref<any[]>([])
const selectedVcn = ref('')
const rules = ref<any[]>([])
const rulesLoading = ref(false)
const ruleType = ref(0) // 0=入站, 1=出站

// ── Add Rule ─────────────────────────────────────────────────────────────────
const addDialogVisible = ref(false)
const addLoading = ref(false)
const addForm = reactive({
  direction: 'INGRESS' as 'INGRESS' | 'EGRESS',
  is_stateless: false,
  type: 'CIDR_BLOCK',
  cidr: '0.0.0.0/0',
  protocol: 'all',
  source_port: '',
  destination_port: '',
  icmp_type: null as number | null,
  icmp_code: null as number | null,
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
  } catch { /* handled by interceptor */ }
}

async function onRegionChange() {
  selectedVcn.value = ''
  rules.value = []
  await loadVcns()
}

async function loadVcns() {
  if (!selectedRegion.value) return
  try {
    const res = await api.get(`/security-rules/${tenantId}/vcns`, { params: { region: selectedRegion.value } })
    vcnList.value = res.data
    if (vcnList.value.length > 0) {
      selectedVcn.value = vcnList.value[0].vcn_id
      await loadRules()
    }
  } catch { /* handled by interceptor */ }
}

async function loadRules() {
  if (!selectedRegion.value || !selectedVcn.value) return
  rulesLoading.value = true
  try {
    const res = await api.get(`/security-rules/${tenantId}/rules`, {
      params: { region: selectedRegion.value, vcn_id: selectedVcn.value, rule_type: ruleType.value }
    })
    rules.value = res.data.rules || res.data
  } catch { /* handled by interceptor */ } finally { rulesLoading.value = false }
}

function openAddDialog() {
  if (!selectedVcn.value) { warning('请先选择 VCN'); return }
  Object.assign(addForm, {
    direction: ruleType.value === 0 ? 'INGRESS' : 'EGRESS',
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
  addDialogVisible.value = true
}

async function doAddRule() {
  addLoading.value = true
  try {
    const endpoint = addForm.direction === 'INGRESS' ? 'ingress' : 'egress'
    const payload: any = {
      region: selectedRegion.value,
      vcn_id: selectedVcn.value,
      is_stateless: addForm.is_stateless,
      protocol: addForm.protocol,
      description: addForm.description || null,
    }
    if (addForm.direction === 'INGRESS') {
      payload.source = addForm.cidr
      payload.source_type = addForm.type
    } else {
      payload.destination = addForm.cidr
      payload.destination_type = addForm.type
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
    success('规则添加成功')
    addDialogVisible.value = false
    await loadRules()
  } catch { /* handled by interceptor */ } finally { addLoading.value = false }
}

async function doRemoveRule(index: number) {
  const ok = await confirm('确认删除该安全规则？', '确认', { type: 'warning' })
  if (!ok) return
  try {
    await api.post(`/security-rules/${tenantId}/remove`, {
      region: selectedRegion.value,
      vcn_id: selectedVcn.value,
      rule_type: ruleType.value,
      indices: [index],
    })
    success('规则删除成功')
    await loadRules()
  } catch { /* handled by interceptor */ }
}

async function doReleaseAll() {
  if (!selectedRegion.value) { warning('请先选择区域'); return }
  const ok = await confirm('将为当前区域所有 VCN 添加 0.0.0.0/0 和 ::/0 的全协议放行规则，确认继续？', '一键放行所有端口', { type: 'warning' })
  if (!ok) return
  try {
    const res = await api.post(`/security-rules/${tenantId}/release-all`, {
      region: selectedRegion.value,
    })
    success(res.data.message || '已放行所有端口')
    await loadRules()
  } catch { /* handled by interceptor */ }
}

onMounted(loadTenant)
</script>
