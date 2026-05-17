<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-3">
        <button class="btn-ghost btn-sm" @click="$router.back()">← 返回</button>
        <h2 class="text-2xl font-bold text-surface-900 dark:text-white">引导卷管理 — {{ tenantName }}</h2>
      </div>
      <button class="btn-secondary" :disabled="loading" @click="load">刷新</button>
    </div>

    <Loading :loading="loading" text="加载引导卷..." />

    <template v-if="!loading">
      <div v-if="volumes.length === 0" class="card p-12 text-center text-surface-400">暂无引导卷</div>

      <div v-for="(group, idx) in regionGroups" :key="group.name" class="space-y-3">
        <div v-if="idx > 0" class="border-t border-surface-200 dark:border-surface-700 my-4"></div>
        <div class="flex items-center gap-2">
          <svg class="w-4 h-4 text-surface-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" /></svg>
          <span class="font-semibold text-surface-900 dark:text-white">{{ group.name }}</span>
          <span class="badge-info">{{ group.volumes.length }} 个引导卷</span>
        </div>

        <div class="card">
          <div class="table-container">
            <table class="table">
              <thead>
                <tr>
                  <th class="w-10"><input type="checkbox" class="accent-primary-600" :checked="isAllSelected(group.name)" @change="toggleSelectAll(group.name, $event)" /></th>
                  <th>名称</th>
                  <th>实例配置</th>
                  <th>可用域</th>
                  <th>大小(GB)</th>
                  <th>VPU/GB</th>
                  <th>状态</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="vol in group.volumes" :key="vol.id">
                  <td><input type="checkbox" class="accent-primary-600" :checked="selectedByRegion[group.name]?.includes(vol)" @change="toggleSelect(group.name, vol, $event)" /></td>
                  <td class="font-medium">{{ vol.display_name }}</td>
                  <td class="text-sm">
                    <span v-if="vol.instance_ocpus || vol.instance_memory_in_gbs">{{ vol.instance_ocpus || '-' }} OCPU / {{ vol.instance_memory_in_gbs || '-' }} GB</span>
                    <span v-else class="text-surface-400">未关联实例</span>
                  </td>
                  <td class="text-xs font-mono">{{ vol.availability_domain }}</td>
                  <td>{{ vol.size_in_gbs }}</td>
                  <td>{{ vol.vpus_per_gb }}</td>
                  <td><span :class="vol.lifecycle_state === 'AVAILABLE' ? 'badge-success' : 'badge-neutral'">{{ vol.lifecycle_state }}</span></td>
                  <td>
                    <div class="flex items-center gap-1">
                      <button class="btn-ghost btn-sm" @click="openUpdate(vol)">配置</button>
                      <button class="btn-ghost btn-sm text-red-600 dark:text-red-400" @click="doTerminate([vol])">终止</button>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-if="(selectedByRegion[group.name] || []).length > 0" class="px-4 py-3 border-t border-surface-200 dark:border-surface-700">
            <button class="btn-danger btn-sm" @click="doTerminate(selectedByRegion[group.name])">
              批量终止 ({{ selectedByRegion[group.name].length }})
            </button>
          </div>
        </div>
      </div>
    </template>

    <!-- Update dialog -->
    <Modal :visible="updateDialogVisible" title="更新引导卷配置" width="440px" @close="updateDialogVisible = false">
      <div class="space-y-4">
        <div>
          <label class="label">当前大小</label>
          <p class="text-sm text-surface-600 dark:text-surface-300">{{ updateTarget?.size_in_gbs }} GB</p>
        </div>
        <div>
          <label class="label">新大小 (GB)</label>
          <input v-model.number="updateForm.size_in_gbs" type="number" min="50" max="32768" step="50" class="input" />
        </div>
        <div>
          <label class="label">VPU/GB</label>
          <input v-model.number="updateForm.vpus_per_gb" type="number" min="10" max="120" step="10" class="input" />
          <p class="text-xs text-surface-400 mt-1">10=基础, 20=均衡, 30-120=高性能</p>
        </div>
      </div>
      <template #footer>
        <button class="btn-secondary" @click="updateDialogVisible = false">取消</button>
        <button class="btn-primary" :disabled="updateLoading" @click="doUpdate">确认</button>
      </template>
    </Modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useToast } from '@/composables/useToast'
import { useModal } from '@/composables/useModal'
import api from '@/api'
import Modal from '@/components/Modal.vue'
import Loading from '@/components/Loading.vue'
import type { BootVolume } from '@/types'

const route = useRoute()
const { success } = useToast()
const { confirm } = useModal()
const tenantId = route.params.tenantId
const tenantName = ref('')
const volumes = ref<BootVolume[]>([])
const loading = ref(false)

const regionGroups = computed(() => {
  const groups: Record<string, BootVolume[]> = {}
  for (const vol of volumes.value) {
    const r = vol.region || '未知区域'
    if (!groups[r]) groups[r] = []
    groups[r].push(vol)
  }
  return Object.keys(groups).sort().map(name => ({ name, volumes: groups[name] }))
})

const updateDialogVisible = ref(false)
const updateLoading = ref(false)
const updateTarget = ref<BootVolume | null>(null)
const updateForm = reactive({ size_in_gbs: 50, vpus_per_gb: 10 })

// Batch selection
const selectedByRegion = reactive<Record<string, BootVolume[]>>({})

function toggleSelect(regionName: string, vol: BootVolume, event: Event) {
  const checked = (event.target as HTMLInputElement).checked
  if (!selectedByRegion[regionName]) selectedByRegion[regionName] = []
  if (checked) {
    selectedByRegion[regionName].push(vol)
  } else {
    selectedByRegion[regionName] = selectedByRegion[regionName].filter(v => v.id !== vol.id)
  }
}

function toggleSelectAll(regionName: string, event: Event) {
  const checked = (event.target as HTMLInputElement).checked
  const group = regionGroups.value.find(g => g.name === regionName)
  if (!group) return
  selectedByRegion[regionName] = checked ? [...group.volumes] : []
}

function isAllSelected(regionName: string) {
  const group = regionGroups.value.find(g => g.name === regionName)
  if (!group || group.volumes.length === 0) return false
  return (selectedByRegion[regionName] || []).length === group.volumes.length
}

async function load() {
  loading.value = true
  try {
    const [volRes, tenantRes] = await Promise.all([
      api.get(`/boot-volumes/${tenantId}`),
      api.get(`/tenants/${tenantId}`),
    ])
    volumes.value = volRes.data
    tenantName.value = tenantRes.data.name
  } catch {} finally { loading.value = false }
}

function openUpdate(row: BootVolume) {
  updateTarget.value = row
  updateForm.size_in_gbs = row.size_in_gbs
  updateForm.vpus_per_gb = row.vpus_per_gb
  updateDialogVisible.value = true
}

async function doUpdate() {
  if (!updateTarget.value) return
  updateLoading.value = true
  try {
    await api.put(`/boot-volumes/${tenantId}/update`, {
      region: updateTarget.value.region,
      boot_volume_id: updateTarget.value.id,
      size_in_gbs: updateForm.size_in_gbs,
      vpus_per_gb: updateForm.vpus_per_gb,
    })
    success('引导卷配置更新成功')
    updateDialogVisible.value = false
    await load()
  } finally { updateLoading.value = false }
}

async function doTerminate(rows: BootVolume[]) {
  const ok = await confirm(`确认终止 ${rows.length} 个引导卷？此操作不可逆！`, '危险操作', { type: 'error', confirmText: '确认终止' })
  if (!ok) return
  const byRegion: Record<string, string[]> = {}
  for (const row of rows) {
    const r = row.region || ''
    if (!byRegion[r]) byRegion[r] = []
    byRegion[r].push(row.id)
  }
  await Promise.all(
    Object.entries(byRegion).map(([region, ids]) =>
      api.post(`/boot-volumes/${tenantId}/terminate`, { region, boot_volume_ids: ids })
    )
  )
  success('终止指令已发送')
  setTimeout(load, 3000)
}

onMounted(load)
</script>
