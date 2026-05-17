<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <h2 class="text-2xl font-bold text-surface-900 dark:text-white">IP 数据管理</h2>
      <div class="flex items-center gap-2">
        <button class="btn-primary" @click="openAddDialog">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/></svg>
          添加 IP
        </button>
        <button class="btn-secondary" :disabled="loadOciLoading" @click="doLoadFromOci">
          {{ loadOciLoading ? '加载中...' : '从 OCI 加载' }}
        </button>
        <button class="btn-ghost" @click="showMap = !showMap">
          {{ showMap ? '隐藏地图' : '显示地图' }}
        </button>
      </div>
    </div>

    <!-- Map -->
    <div v-if="showMap" class="card p-4">
      <div class="flex items-center gap-2 mb-3">
        <span class="font-semibold text-surface-900 dark:text-white">全球服务器分布</span>
        <span class="badge-info">{{ mapPoints.length }} 个节点</span>
      </div>
      <div ref="mapContainer" class="w-full h-[380px] rounded-lg"></div>
    </div>

    <!-- IP Query -->
    <div class="card p-4">
      <div class="flex items-center gap-3 mb-3">
        <label class="label mb-0">IP 查询</label>
        <input v-model="queryIp" class="input" style="width:220px" placeholder="输入 IP 地址查询归属地" @keyup.enter="doQueryIp" />
        <button class="btn-primary btn-sm" :disabled="queryLoading" @click="doQueryIp">
          {{ queryLoading ? '查询中...' : '查询' }}
        </button>
      </div>
      <div v-if="queryResult" class="grid grid-cols-4 gap-3 mt-3 text-sm">
        <div class="bg-surface-50 dark:bg-surface-900 rounded-lg p-2">
          <span class="text-surface-500">IP</span>
          <div class="font-medium">{{ queryResult.ip }}</div>
        </div>
        <div class="bg-surface-50 dark:bg-surface-900 rounded-lg p-2">
          <span class="text-surface-500">国家</span>
          <div class="font-medium">{{ queryResult.country }}</div>
        </div>
        <div class="bg-surface-50 dark:bg-surface-900 rounded-lg p-2">
          <span class="text-surface-500">地区</span>
          <div class="font-medium">{{ queryResult.area }}</div>
        </div>
        <div class="bg-surface-50 dark:bg-surface-900 rounded-lg p-2">
          <span class="text-surface-500">城市</span>
          <div class="font-medium">{{ queryResult.city }}</div>
        </div>
        <div class="bg-surface-50 dark:bg-surface-900 rounded-lg p-2">
          <span class="text-surface-500">运营商</span>
          <div class="font-medium">{{ queryResult.org }}</div>
        </div>
        <div class="bg-surface-50 dark:bg-surface-900 rounded-lg p-2">
          <span class="text-surface-500">ASN</span>
          <div class="font-medium">{{ queryResult.asn }}</div>
        </div>
        <div class="bg-surface-50 dark:bg-surface-900 rounded-lg p-2">
          <span class="text-surface-500">纬度</span>
          <div class="font-medium">{{ queryResult.lat }}</div>
        </div>
        <div class="bg-surface-50 dark:bg-surface-900 rounded-lg p-2">
          <span class="text-surface-500">经度</span>
          <div class="font-medium">{{ queryResult.lng }}</div>
        </div>
      </div>
    </div>

    <!-- IP Data Table -->
    <div class="card">
      <div class="flex items-center justify-between px-5 py-4 border-b border-surface-200 dark:border-surface-700">
        <span class="font-semibold text-surface-900 dark:text-white">IP 数据列表</span>
        <input v-model="searchKeyword" class="input" style="width:260px" placeholder="搜索 IP / 国家 / 城市..." @input="debouncedLoadTable" />
      </div>
      <Loading :loading="tableLoading" text="加载中..." />
      <div v-if="!tableLoading" class="table-container">
        <table class="table">
          <thead>
            <tr>
              <th><input type="checkbox" @change="toggleSelectAll" :checked="isAllSelected" class="accent-primary-600" /></th>
              <th>租户</th>
              <th>IP</th>
              <th>国家</th>
              <th>地区</th>
              <th>城市</th>
              <th>运营商</th>
              <th>ASN</th>
              <th>类型</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in tableData" :key="row.id">
              <td><input type="checkbox" :checked="selectedIds.includes(row.id)" @change="toggleSelect(row.id)" class="accent-primary-600" /></td>
              <td>{{ row.tenant_name }}</td>
              <td class="font-mono text-xs">{{ row.ip }}</td>
              <td>{{ row.country }}</td>
              <td>{{ row.area }}</td>
              <td>{{ row.city }}</td>
              <td class="max-w-[180px] truncate" :title="row.org">{{ row.org }}</td>
              <td class="text-xs">{{ row.asn }}</td>
              <td>
                <span :class="row.ip_type === 'oracle' ? 'badge-warning' : 'badge-neutral'">
                  {{ row.ip_type === 'oracle' ? 'OCI' : '手动' }}
                </span>
              </td>
              <td>
                <div class="flex items-center gap-1">
                  <button class="btn-ghost btn-sm" @click="doRefresh(row)">刷新</button>
                  <button class="btn-ghost btn-sm text-red-600" @click="doRemove([row.id])">删除</button>
                </div>
              </td>
            </tr>
            <tr v-if="tableData.length === 0 && !tableLoading">
              <td colspan="10" class="text-center text-surface-400 py-8">暂无数据</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Pagination -->
      <div class="flex items-center justify-between px-5 py-3 border-t border-surface-200 dark:border-surface-700">
        <div>
          <button v-if="selectedIds.length > 0" class="btn-danger btn-sm" @click="doRemove(selectedIds)">
            批量删除 ({{ selectedIds.length }})
          </button>
        </div>
        <div class="flex items-center gap-3 text-sm text-surface-600 dark:text-surface-400">
          <span>共 {{ total }} 条</span>
          <select v-model.number="pageSize" class="select" style="width:80px" @change="loadTable">
            <option :value="20">20</option>
            <option :value="50">50</option>
            <option :value="100">100</option>
          </select>
          <div class="flex items-center gap-1">
            <button class="btn-ghost btn-sm" :disabled="currentPage <= 1" @click="currentPage--; loadTable()">上一页</button>
            <span>{{ currentPage }} / {{ totalPages }}</span>
            <button class="btn-ghost btn-sm" :disabled="currentPage >= totalPages" @click="currentPage++; loadTable()">下一页</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Add IP Modal -->
    <Modal :visible="addDialogVisible" title="添加 IP" width="400px" @close="addDialogVisible = false">
      <div>
        <label class="label">IP 地址</label>
        <input v-model="addIp" class="input" placeholder="如 8.8.8.8" @keyup.enter="doAdd" />
      </div>
      <template #footer>
        <button class="btn-secondary" @click="addDialogVisible = false">取消</button>
        <button class="btn-primary" :disabled="addLoading" @click="doAdd">
          {{ addLoading ? '添加中...' : '添加' }}
        </button>
      </template>
    </Modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import api from '@/api'
import { useToast } from '@/composables/useToast'
import { useModal } from '@/composables/useModal'
import Modal from '@/components/Modal.vue'
import Loading from '@/components/Loading.vue'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

const { success, warning, error } = useToast()
const { confirm } = useModal()

// ── Map ──────────────────────────────────────────────────────────────────────
const showMap = ref(true)
const mapPoints = ref<any[]>([])
const mapContainer = ref<HTMLElement | null>(null)
let leafletMap: L.Map | null = null
let markersLayer: L.LayerGroup | null = null

function initMap() {
  if (!mapContainer.value || leafletMap) return
  leafletMap = L.map(mapContainer.value, { center: [20, 0], zoom: 2, minZoom: 2, maxZoom: 18, attributionControl: false })
  const streetLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 18 })
  const satelliteLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', { maxZoom: 18 })
  streetLayer.addTo(leafletMap)
  L.control.layers({ '街道地图': streetLayer, '卫星影像': satelliteLayer }, undefined, { position: 'topright' }).addTo(leafletMap)
  markersLayer = L.layerGroup().addTo(leafletMap)
  updateMarkers()
}

function destroyMap() {
  if (leafletMap) { leafletMap.remove(); leafletMap = null; markersLayer = null }
}

function updateMarkers() {
  if (!markersLayer) return
  markersLayer.clearLayers()
  for (const p of mapPoints.value) {
    if (p.lat == null || p.lng == null) continue
    const marker = L.circleMarker([p.lat, p.lng], { radius: 8, fillColor: '#3b82f6', color: '#fff', weight: 2, opacity: 1, fillOpacity: 0.8 })
    marker.bindPopup(`<b>${p.tenant_name || ''}</b>${p.tenant_name ? '<br/>' : ''}<b>${p.ip}</b><br/>${p.city || ''}, ${p.country || ''}<br/>${p.org || ''}`)
    markersLayer.addLayer(marker)
  }
  if (mapPoints.value.length > 0) {
    const valid = mapPoints.value.filter(p => p.lat && p.lng)
    if (valid.length) {
      const bounds = L.latLngBounds(valid.map(p => [p.lat, p.lng] as [number, number]))
      if (bounds.isValid()) leafletMap?.fitBounds(bounds, { padding: [30, 30], maxZoom: 6 })
    }
  }
}

watch(showMap, async (val) => {
  if (val) { await nextTick(); initMap() } else { destroyMap() }
})
watch(mapPoints, () => updateMarkers())
onBeforeUnmount(() => destroyMap())

// ── IP Query ─────────────────────────────────────────────────────────────────
const queryIp = ref('')
const queryLoading = ref(false)
const queryResult = ref<any>(null)

async function doQueryIp() {
  if (!queryIp.value.trim()) return
  queryLoading.value = true
  queryResult.value = null
  try {
    const res = await api.get('/ip-data/query', { params: { ip: queryIp.value.trim() } })
    queryResult.value = res.data
  } catch { /* handled by interceptor */ } finally { queryLoading.value = false }
}

// ── Table ────────────────────────────────────────────────────────────────────
const tableData = ref<any[]>([])
const tableLoading = ref(false)
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)
const searchKeyword = ref('')
const selectedIds = ref<number[]>([])

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))
const isAllSelected = computed(() => tableData.value.length > 0 && tableData.value.every(r => selectedIds.value.includes(r.id)))

let debounceTimer: ReturnType<typeof setTimeout> | null = null
function debouncedLoadTable() {
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => { currentPage.value = 1; loadTable() }, 300)
}

function toggleSelectAll(e: Event) {
  const checked = (e.target as HTMLInputElement).checked
  selectedIds.value = checked ? tableData.value.map(r => r.id) : []
}

function toggleSelect(id: number) {
  const idx = selectedIds.value.indexOf(id)
  if (idx === -1) selectedIds.value.push(id)
  else selectedIds.value.splice(idx, 1)
}

async function loadTable() {
  tableLoading.value = true
  try {
    const params: any = { page: currentPage.value, page_size: pageSize.value }
    if (searchKeyword.value) params.keyword = searchKeyword.value
    const res = await api.get('/ip-data/list', { params })
    tableData.value = res.data.items
    total.value = res.data.total
  } catch { /* handled by interceptor */ } finally { tableLoading.value = false }
}

async function loadMapData() {
  try { const res = await api.get('/ip-data/map'); mapPoints.value = res.data } catch { /* ignore */ }
}

// ── Add ──────────────────────────────────────────────────────────────────────
const addDialogVisible = ref(false)
const addIp = ref('')
const addLoading = ref(false)

function openAddDialog() { addIp.value = ''; addDialogVisible.value = true }

async function doAdd() {
  if (!addIp.value.trim()) { warning('请输入 IP'); return }
  addLoading.value = true
  try {
    await api.post('/ip-data/add', { ip: addIp.value.trim() })
    success('添加成功')
    addDialogVisible.value = false
    await loadTable()
    await loadMapData()
  } catch { /* handled by interceptor */ } finally { addLoading.value = false }
}

// ── Refresh ──────────────────────────────────────────────────────────────────
async function doRefresh(row: any) {
  try {
    await api.post(`/ip-data/refresh/${row.id}`)
    success('刷新成功')
    await loadTable()
    await loadMapData()
  } catch { /* handled by interceptor */ }
}

// ── Remove ───────────────────────────────────────────────────────────────────
async function doRemove(ids: number[]) {
  const ok = await confirm(`确认删除 ${ids.length} 条 IP 记录？`, '确认', { type: 'warning' })
  if (!ok) return
  try {
    await api.post('/ip-data/remove', { ids })
    success('删除成功')
    selectedIds.value = []
    await loadTable()
    await loadMapData()
  } catch { /* handled by interceptor */ }
}

// ── Load from OCI ────────────────────────────────────────────────────────────
const loadOciLoading = ref(false)

async function doLoadFromOci() {
  const ok = await confirm('将从所有 OCI 租户加载实例公网 IP 并查询归属地，确认继续？', '从 OCI 加载', { type: 'info' })
  if (!ok) return
  loadOciLoading.value = true
  try {
    const res = await api.post('/ip-data/load-from-oci')
    success(res.data.message)
    setTimeout(async () => { await loadTable(); await loadMapData() }, 5000)
  } catch { /* handled by interceptor */ } finally { loadOciLoading.value = false }
}

// ── Init ─────────────────────────────────────────────────────────────────────
onMounted(async () => {
  await loadTable()
  await loadMapData()
  await nextTick()
  initMap()
})
</script>
