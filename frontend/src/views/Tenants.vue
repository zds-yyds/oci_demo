<template>
  <div>
    <div class="page-header">
      <h2>云账户管理</h2>
      <el-button type="primary" @click="openAdd">
        <el-icon><Plus /></el-icon> 添加账户
      </el-button>
    </div>

    <el-card shadow="never">
      <el-table :data="tenants" v-loading="loading">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="name" label="账户名称" />
        <el-table-column prop="region" label="区域" width="200">
          <template #default="{ row }">
            <el-tag v-for="r in row.region" :key="r" size="small" style="margin:2px">{{ r }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="tenancy_ocid" label="Tenancy OCID" show-overflow-tooltip />
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
              {{ row.is_active ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="170">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{ row }">
            <el-button text size="small" @click="$router.push(`/instances/${row.id}`)">
              <el-icon><Monitor /></el-icon> 实例
            </el-button>
            <el-button text size="small" @click="testConn(row)">
              <el-icon><Connection /></el-icon> 测试
            </el-button>
            <el-button text size="small" @click="openEdit(row)">
              <el-icon><Edit /></el-icon> 编辑
            </el-button>
            <el-button text size="small" type="danger" @click="deleteTenant(row)">
              <el-icon><Delete /></el-icon> 删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Add/Edit Dialog -->
    <el-dialog v-model="dialogVisible" :title="editId ? '编辑账户' : '添加云账户'" width="600px">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="120px">
        <el-form-item label="账户名称" prop="name">
          <el-input v-model="form.name" placeholder="自定义名称，如：我的OCI账户" />
        </el-form-item>
        <el-form-item label="User OCID" prop="user_ocid">
          <el-input v-model="form.user_ocid" placeholder="ocid1.user.oc1.." />
        </el-form-item>
        <el-form-item label="Fingerprint" prop="fingerprint">
          <el-input v-model="form.fingerprint" placeholder="xx:xx:xx:..." />
        </el-form-item>
        <el-form-item label="Tenancy OCID" prop="tenancy_ocid">
          <el-input v-model="form.tenancy_ocid" placeholder="ocid1.tenancy.oc1.." />
        </el-form-item>
        <el-form-item label="Region" prop="region">
          <el-select v-model="form.region" placeholder="选择区域（可多选）" filterable multiple collapse-tags collapse-tags-tooltip style="width:100%">
            <el-option v-for="r in regions" :key="r" :label="r" :value="r" />
          </el-select>
        </el-form-item>
        <el-form-item label="私钥 (PEM)" prop="private_key" :rules="editId ? [] : [{ required: true, message: '请输入私钥' }]">
          <el-input
            v-model="form.private_key"
            type="textarea"
            :rows="6"
            :placeholder="editId ? '留空表示不修改' : '-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----'"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/api'
import dayjs from 'dayjs'

const tenants = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const saving = ref(false)
const editId = ref(null)
const formRef = ref()

const regions = ref([])

const form = reactive({
  name: '', user_ocid: '', fingerprint: '', tenancy_ocid: '', region: [], private_key: '',
})

const rules = {
  name: [{ required: true, message: '请输入账户名称' }],
  user_ocid: [{ required: true, message: '请输入 User OCID' }],
  fingerprint: [{ required: true, message: '请输入 Fingerprint' }],
  tenancy_ocid: [{ required: true, message: '请输入 Tenancy OCID' }],
  region: [{ required: true, type: 'array', min: 1, message: '请至少选择一个区域' }],
}

function formatDate(d) { return dayjs(d).format('YYYY-MM-DD HH:mm') }

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
  dialogVisible.value = true
  // 自动预填默认私钥
  api.get('/users/me/default-key/value').then(res => {
    if (res.data.private_key) {
      form.private_key = res.data.private_key
    }
  }).catch(() => {})
}

function openEdit(row) {
  editId.value = row.id
  Object.assign(form, {
    name: row.name,
    user_ocid: row.user_ocid || '',
    fingerprint: row.fingerprint || '',
    tenancy_ocid: row.tenancy_ocid,
    region: row.region || [],
    private_key: '',
  })
  dialogVisible.value = true
}

async function save() {
  await formRef.value.validate()
  saving.value = true
  try {
    if (editId.value) {
      const payload = { ...form }
      if (!payload.private_key) delete payload.private_key
      await api.put(`/tenants/${editId.value}`, payload)
      ElMessage.success('更新成功')
    } else {
      await api.post('/tenants', form)
      ElMessage.success('添加成功')
    }
    dialogVisible.value = false
    load()
  } finally {
    saving.value = false
  }
}

async function deleteTenant(row) {
  await ElMessageBox.confirm(`确认删除账户「${row.name}」？`, '警告', { type: 'warning' })
  await api.delete(`/tenants/${row.id}`)
  ElMessage.success('删除成功')
  load()
}

async function testConn(row) {
  const loading = ElMessage({ message: '正在测试连接（遍历所有区域）...', type: 'info', duration: 0 })
  try {
    const res = await api.get(`/tenants/${row.id}/test`)
    loading.close()
    if (res.data.status === 'ok') {
      const regionResults = res.data.regions || {}
      const details = Object.entries(regionResults)
        .map(([r, s]) => `${r}: ${s === 'ok' ? '✓' : '✗'}`)
        .join('\n')
      ElMessage.success({ message: `连接成功！租户: ${res.data.tenancy_name}\n${details}`, duration: 5000 })
    } else {
      ElMessage.error(`连接失败: ${res.data.detail}`)
    }
  } catch {
    loading.close()
  }
}

async function loadRegions() {
  try {
    const res = await api.get('/regions')
    regions.value = res.data.map(r => r.identifier)
  } catch {
    // fallback
    regions.value = []
  }
}

onMounted(() => {
  load()
  loadRegions()
})
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.page-header h2 { font-size: 22px; }
</style>
