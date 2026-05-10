<template>
  <div>
    <div class="page-header">
      <div>
        <el-button text @click="$router.back()"><el-icon><ArrowLeft /></el-icon> 返回</el-button>
        <h2 style="display:inline;margin-left:8px">OCI 用户管理 — {{ tenantName }}</h2>
      </div>
      <el-button type="primary" @click="openAdd">
        <el-icon><Plus /></el-icon> 创建用户
      </el-button>
    </div>

    <el-card shadow="never" v-loading="loading">
      <el-empty v-if="!loading && users.length === 0" description="暂无 IAM 用户" />
      <el-table v-else :data="users">
        <el-table-column prop="name" label="用户名/邮箱" show-overflow-tooltip />
        <el-table-column prop="email" label="邮箱" show-overflow-tooltip />
        <el-table-column prop="description" label="描述" width="180" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.lifecycle_state === 'ACTIVE' ? 'success' : 'info'" size="small">
              {{ row.lifecycle_state }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="170">
          <template #default="{ row }">{{ formatDate(row.time_created) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button text size="small" type="danger" @click="deleteUser(row)">
              <el-icon><Delete /></el-icon> 删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Create Dialog -->
    <el-dialog v-model="dialogVisible" title="创建 OCI IAM 用户" width="450px">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="80px">
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="form.email" placeholder="用户邮箱（同时作为登录名）" />
        </el-form-item>
      </el-form>
      <p style="color:#909399;font-size:12px;margin-top:8px">
        创建后用户将自动加入 Administrators 组，拥有管理员权限。
      </p>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/api'
import dayjs from 'dayjs'

const route = useRoute()
const tenantId = route.params.tenantId
const users = ref([])
const loading = ref(false)
const tenantName = ref('')
const dialogVisible = ref(false)
const saving = ref(false)
const formRef = ref()

const form = reactive({ email: '' })
const rules = {
  email: [
    { required: true, message: '请输入邮箱' },
    { type: 'email', message: '请输入有效的邮箱地址' },
  ],
}

function formatDate(d) { return d ? dayjs(d).format('YYYY-MM-DD HH:mm') : '' }

async function load() {
  loading.value = true
  try {
    const [usersRes, tenantRes] = await Promise.all([
      api.get(`/oci-users/${tenantId}`),
      api.get(`/tenants/${tenantId}`),
    ])
    users.value = usersRes.data
    tenantName.value = tenantRes.data.name
  } catch (err) {
    const msg = err.response?.data?.detail || '加载失败'
    ElMessage.error(msg)
  } finally {
    loading.value = false
  }
}

function openAdd() {
  form.email = ''
  dialogVisible.value = true
}

async function save() {
  await formRef.value.validate()
  saving.value = true
  try {
    const res = await api.post(`/oci-users/${tenantId}`, { email: form.email })
    ElMessage.success(res.data.message || '用户创建成功')
    dialogVisible.value = false
    load()
  } catch (err) {
    const msg = err.response?.data?.detail || '创建失败'
    ElMessage.error(msg)
  } finally {
    saving.value = false
  }
}

async function deleteUser(row) {
  await ElMessageBox.confirm(
    `确认删除 OCI 用户「${row.name}」？此操作不可恢复。`,
    '警告', { type: 'warning' }
  )
  try {
    await api.delete(`/oci-users/${tenantId}/${encodeURIComponent(row.id)}`)
    ElMessage.success('用户删除成功')
    load()
  } catch (err) {
    const msg = err.response?.data?.detail || '删除失败'
    ElMessage.error(msg)
  }
}

onMounted(load)
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.page-header h2 { font-size: 22px; }
</style>
