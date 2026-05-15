<template>
  <div>
    <div class="page-header">
      <h2>控制台</h2>
      <p>欢迎回来，{{ auth.user?.username }}</p>
    </div>

    <!-- Stats cards -->
    <el-row :gutter="16" style="margin-bottom:24px">
      <el-col :span="6" v-for="stat in stats" :key="stat.label">
        <el-card class="stat-card" shadow="never">
          <div class="stat-inner">
            <div class="stat-icon" :style="{ background: stat.color }">
              <el-icon size="24" color="#fff"><component :is="stat.icon" /></el-icon>
            </div>
            <div>
              <div class="stat-value">{{ stat.value }}</div>
              <div class="stat-label">{{ stat.label }}</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Running snipe tasks -->
    <el-row :gutter="16">
      <el-col :span="14">
        <el-card shadow="never">
          <template #header>
            <span>抢机任务状态</span>
            <span style="float:right">
              <el-button text @click="loadTasks">刷新</el-button>
              <el-button type="primary" text @click="$router.push('/snipe')">
                <el-icon><Right /></el-icon> 前往抢机任务
              </el-button>
            </span>
          </template>
          <el-table :data="recentTasks" size="small" max-height="320">
            <el-table-column label="租户" width="100">
              <template #default="{ row }">
                {{ tenantName(row.tenant_id) }}
              </template>
            </el-table-column>
            <el-table-column prop="shape_name" label="类型" width="80" />
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="statusType(row.status)" size="small">{{ row.status }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="attempt_count" label="尝试次数" width="90" />
            <el-table-column prop="result_ip" label="IP" />
          </el-table>
        </el-card>
      </el-col>
      <el-col :span="10">
        <el-card shadow="never">
          <template #header><span>云账户列表</span></template>
          <el-table :data="tenants" size="small" max-height="320">
            <el-table-column prop="name" label="名称" />
            <el-table-column prop="region" label="区域" width="120" />
            <el-table-column label="状态" width="80">
              <template #default="{ row }">
                <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
                  {{ row.is_active ? '启用' : '禁用' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="80">
              <template #default="{ row }">
                <el-button text size="small" @click="$router.push(`/instances/${row.id}`)">
                  实例
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useAuthStore } from '@/stores/auth'
import api from '@/api'

const auth = useAuthStore()
const tasks = ref([])
const tenants = ref([])

const recentTasks = computed(() => tasks.value.slice(0, 10))

const stats = computed(() => [
  { label: '云账户数', value: tenants.value.length, icon: 'OfficeBuilding', color: '#409eff' },
  { label: '运行中任务', value: tasks.value.filter(t => t.status === 'running').length, icon: 'Aim', color: '#67c23a' },
  { label: '成功抢机', value: tasks.value.filter(t => t.status === 'success').length, icon: 'CircleCheck', color: '#e6a23c' },
  { label: '失败任务', value: tasks.value.filter(t => t.status === 'failed').length, icon: 'CircleClose', color: '#f56c6c' },
])

function statusType(s) {
  return { running: 'warning', success: 'success', failed: 'danger', stopped: 'info', pending: '' }[s] || ''
}

function tenantName(id) {
  return tenants.value.find(t => t.id === id)?.name || id
}

async function loadTasks() {
  const res = await api.get('/snipe')
  tasks.value = res.data
}

async function loadTenants() {
  const res = await api.get('/tenants')
  tenants.value = res.data
}

onMounted(() => {
  loadTasks()
  loadTenants()
  // Auto-refresh every 10s
  setInterval(loadTasks, 10000)
})
</script>

<style scoped>
.page-header { margin-bottom: 24px; }
.page-header h2 { font-size: 22px; color: #303133; }
.page-header p { color: #909399; margin-top: 4px; }
.stat-card { border-radius: 12px; }
.stat-inner { display: flex; align-items: center; gap: 16px; }
.stat-icon { width: 52px; height: 52px; border-radius: 12px; display: flex; align-items: center; justify-content: center; }
.stat-value { font-size: 28px; font-weight: 700; color: #303133; }
.stat-label { font-size: 13px; color: #909399; margin-top: 2px; }
</style>
