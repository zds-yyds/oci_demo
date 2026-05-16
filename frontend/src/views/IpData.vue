<template>
  <div>
    <div class="page-header">
      <h2>IP 数据管理</h2>
      <div class="header-actions">
        <el-button type="primary" @click="openAddDialog"><el-icon><Plus /></el-icon> 添加 IP</el-button>
        <el-button type="success" @click="doLoadFromOci" :loading="loadOciLoading">
          <el-icon><Download /></el-icon> 从 OCI 加载
        </el-button>
        <el-button @click="showMap = !showMap">
          <el-icon><MapLocation /></el-icon> {{ showMap ? '隐藏地图' : '显示地图' }}
        </el-button>
      </div>
    </div>

    <!-- 全球服务器地图 (Leaflet) -->
    <el-card v-if="showMap" shadow="never" style="margin-bottom:16px">
      <template #header>
        <span>全球服务器分布</span>
        <el-tag size="small" style="margin-left:8px">{{ mapPoints.length }} 个节点</el-tag>
      </template>
      <div ref="mapContainer" class="leaflet-map"></div>
    </el-card>

    <!-- IP 查询工具 -->
    <el-card shadow="never" style="margin-bottom:16px">
      <el-form :inline="true">
        <el-form-item label="IP 查询">
          <el-input v-model="queryIp" placeholder="输入 IP 地址查询归属地" style="width:220px" @keyup.enter="doQueryIp" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="doQueryIp" :loading="queryLoading">查询</el-button>
        </el-form-item>
      </el-form>
      <el-descriptions v-if="queryResult" :column="4" border size="small" style="margin-top:12px">
        <el-descriptions-item label="IP">{{ queryResult.ip }}</el-descriptions-item>
        <el-descriptions-item label="国家">{{ queryResult.country }}</el-descriptions-item>
        <el-descriptions-item label="地区">{{ queryResult.area }}</el-descriptions-item>
        <el-descriptions-item label="城市">{{ queryResult.city }}</el-descriptions-item>
        <el-descriptions-item label="运营商">{{ queryResult.org }}</el-descriptions-item>
        <el-descriptions-item label="ASN">{{ queryResult.asn }}</el-descriptions-item>
        <el-descriptions-item label="纬度">{{ queryResult.lat }}</el-descriptions-item>
        <el-descriptions-item label="经度">{{ queryResult.lng }}</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <!-- IP 数据列表 -->
    <el-card shadow="never" v-loading="tableLoading">
      <template #header>
        <div style="display:flex;justify-content:space-between;align-items:center">
          <span>IP 数据列表</span>
          <el-input v-model="searchKeyword" placeholder="搜索 IP / 国家 / 城市..." clearable style="width:260px" @input="loadTable" />
        </div>
      </template>
      <el-table :data="tableData" stripe border @selection-change="onSelectionChange">
        <el-table-column type="selection" width="50" />
        <el-table-column prop="tenant_name" label="租户" width="130" show-overflow-tooltip />
        <el-table-column prop="ip" label="IP" width="140" />
        <el-table-column prop="country" label="国家" width="100" />
        <el-table-column prop="area" label="地区" width="120" />
        <el-table-column prop="city" label="城市" width="120" />
        <el-table-column prop="org" label="运营商" min-width="180" show-overflow-tooltip />
        <el-table-column prop="asn" label="ASN" width="160" show-overflow-tooltip />
        <el-table-column prop="ip_type" label="类型" width="80">
          <template #default="{ row }">
            <el-tag v-if="row.ip_type === 'oracle'" type="warning" size="small">OCI</el-tag>
            <el-tag v-else type="info" size="small">手动</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button size="small" text @click="doRefresh(row)"><el-icon><Refresh /></el-icon></el-button>
            <el-button size="small" text type="danger" @click="doRemove([row.id])"><el-icon><Delete /></el-icon></el-button>
          </template>
        </el-table-column>
      </el-table>
      <div style="display:flex;justify-content:space-between;align-items:center;margin-top:12px">
        <div>
          <el-button v-if="selectedIds.length > 0" type="danger" size="small" @click="doRemove(selectedIds)">
            批量删除 ({{ selectedIds.length }})
          </el-button>
        </div>
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[20, 50, 100]"
          layout="total, sizes, prev, pager, next"
          @current-change="loadTable"
          @size-change="loadTable"
        />
      </div>
    </el-card>

    <!-- 添加 IP 弹窗 -->
    <el-dialog v-model="addDialogVisible" title="添加 IP" width="400px">
      <el-form label-width="60px">
        <el-form-item label="IP">
          <el-input v-model="addIp" placeholder="如 8.8.8.8" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="addDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="addLoading" @click="doAdd">添加</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/api'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

// ── Leaflet 地图 ─────────────────────────────────────────────────────────────
const showMap = ref(true)
const mapPoints = ref([])
const mapContainer = ref(null)
let leafletMap = null
let markersLayer = null

function initMap() {
  if (!mapContainer.value || leafletMap) return
  leafletMap = L.map(mapContainer.value, {
    center: [20, 0],
    zoom: 2,
    minZoom: 2,
    maxZoom: 18,
    zoomControl: true,
    attributionControl: false,
  })

  // 图层：街道地图 + 卫星影像
  const streetLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 18,
  })
  const satelliteLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
    maxZoom: 18,
  })

  streetLayer.addTo(leafletMap)

  L.control.layers(
    { '街道地图': streetLayer, '卫星影像': satelliteLayer },
    null,
    { position: 'topright' }
  ).addTo(leafletMap)

  markersLayer = L.layerGroup().addTo(leafletMap)
  updateMarkers()
}

function destroyMap() {
  if (leafletMap) {
    leafletMap.remove()
    leafletMap = null
    markersLayer = null
  }
}

function updateMarkers() {
  if (!markersLayer) return
  markersLayer.clearLayers()
  for (const p of mapPoints.value) {
    if (p.lat == null || p.lng == null) continue
    const marker = L.circleMarker([p.lat, p.lng], {
      radius: 8,
      fillColor: '#409EFF',
      color: '#fff',
      weight: 2,
      opacity: 1,
      fillOpacity: 0.8,
    })
    marker.bindPopup(`<b>${p.tenant_name || ''}</b>${p.tenant_name ? '<br/>' : ''}<b>${p.ip}</b><br/>${p.city || ''}, ${p.country || ''}<br/>${p.org || ''}<br/><a href="https://www.itdog.cn/ping/${p.ip}" target="_blank" style="display:inline-block;margin-top:6px;padding:2px 10px;background:#409EFF;color:#fff;border-radius:4px;text-decoration:none;font-size:12px;">测 Ping</a>`)
    markersLayer.addLayer(marker)
  }
  // 自适应缩放到所有标记
  if (mapPoints.value.length > 0) {
    const bounds = L.latLngBounds(mapPoints.value.filter(p => p.lat && p.lng).map(p => [p.lat, p.lng]))
    if (bounds.isValid()) {
      leafletMap.fitBounds(bounds, { padding: [30, 30], maxZoom: 6 })
    }
  }
}

watch(showMap, async (val) => {
  if (val) {
    await nextTick()
    initMap()
  } else {
    destroyMap()
  }
})

watch(mapPoints, () => {
  updateMarkers()
})

onBeforeUnmount(() => {
  destroyMap()
})

// ── IP 查询 ──────────────────────────────────────────────────────────────────
const queryIp = ref('')
const queryLoading = ref(false)
const queryResult = ref(null)

async function doQueryIp() {
  if (!queryIp.value.trim()) return
  queryLoading.value = true
  queryResult.value = null
  try {
    const res = await api.get('/ip-data/query', { params: { ip: queryIp.value.trim() } })
    queryResult.value = res.data
  } catch {} finally { queryLoading.value = false }
}

// ── 表格 ─────────────────────────────────────────────────────────────────────
const tableData = ref([])
const tableLoading = ref(false)
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)
const searchKeyword = ref('')
const selectedIds = ref([])

async function loadTable() {
  tableLoading.value = true
  try {
    const params = { page: currentPage.value, page_size: pageSize.value }
    if (searchKeyword.value) params.keyword = searchKeyword.value
    const res = await api.get('/ip-data/list', { params })
    tableData.value = res.data.items
    total.value = res.data.total
  } catch {} finally { tableLoading.value = false }
}

async function loadMapData() {
  try {
    const res = await api.get('/ip-data/map')
    mapPoints.value = res.data
  } catch {}
}

function onSelectionChange(rows) { selectedIds.value = rows.map(r => r.id) }

// ── 添加 ─────────────────────────────────────────────────────────────────────
const addDialogVisible = ref(false)
const addIp = ref('')
const addLoading = ref(false)

function openAddDialog() { addIp.value = ''; addDialogVisible.value = true }

async function doAdd() {
  if (!addIp.value.trim()) { ElMessage.warning('请输入 IP'); return }
  addLoading.value = true
  try {
    await api.post('/ip-data/add', { ip: addIp.value.trim() })
    ElMessage.success('添加成功')
    addDialogVisible.value = false
    await loadTable()
    await loadMapData()
  } catch {} finally { addLoading.value = false }
}

// ── 刷新 ─────────────────────────────────────────────────────────────────────
async function doRefresh(row) {
  try {
    await api.post(`/ip-data/refresh/${row.id}`)
    ElMessage.success('刷新成功')
    await loadTable()
    await loadMapData()
  } catch {}
}

// ── 删除 ─────────────────────────────────────────────────────────────────────
async function doRemove(ids) {
  await ElMessageBox.confirm(`确认删除 ${ids.length} 条 IP 记录？`, '确认', { type: 'warning' })
  try {
    await api.post('/ip-data/remove', { ids })
    ElMessage.success('删除成功')
    await loadTable()
    await loadMapData()
  } catch {}
}

// ── 从 OCI 加载 ──────────────────────────────────────────────────────────────
const loadOciLoading = ref(false)

async function doLoadFromOci() {
  await ElMessageBox.confirm('将从所有 OCI 租户加载实例公网 IP 并查询归属地，确认继续？', '从 OCI 加载', { type: 'info' })
  loadOciLoading.value = true
  try {
    const res = await api.post('/ip-data/load-from-oci')
    ElMessage.success(res.data.message)
    setTimeout(async () => {
      await loadTable()
      await loadMapData()
    }, 5000)
  } catch {} finally { loadOciLoading.value = false }
}

// ── 初始化 ───────────────────────────────────────────────────────────────────
onMounted(async () => {
  await loadTable()
  await loadMapData()
  await nextTick()
  initMap()
})
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.page-header h2 { margin: 0; }
.header-actions { display: flex; gap: 8px; }
.leaflet-map { width: 100%; height: 380px; border-radius: 8px; z-index: 0; }
</style>
