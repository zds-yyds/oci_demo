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
        <el-col :span="8" v-for="inst in instances" :key="inst.id" style="margin-bottom:16px">
          <el-card class="instance-card" shadow="hover">
            <div class="inst-header">
              <span class="inst-name">{{ inst.display_name }}</span>
              <el-tag :type="stateType(inst.lifecycle_state)" size="small">
                {{ inst.lifecycle_state }}
              </el-tag>
            </div>
            <div class="inst-info">
              <div><el-icon><Cpu /></el-icon> {{ inst.shape }}</div>
              <div><el-icon><Location /></el-icon> {{ inst.availability_domain }}</div>
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
            </div>
          </el-card>
        </el-col>
      </el-row>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/api'
import dayjs from 'dayjs'

const route = useRoute()
const tenantId = route.params.tenantId
const instances = ref([])
const loading = ref(false)
const tenantName = ref('')

function stateType(s) {
  return { RUNNING: 'success', STOPPED: 'info', STOPPING: 'warning', STARTING: 'warning', TERMINATED: 'danger' }[s] || ''
}
function formatDate(d) { return dayjs(d).format('YYYY-MM-DD HH:mm') }

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
    await api.post(`/instances/${tenantId}/${inst.id}/action`, { action })
    ElMessage.success(`${actionMap[action]}指令已发送`)
    setTimeout(load, 3000)
  } catch {}
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
