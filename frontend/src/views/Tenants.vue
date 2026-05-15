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
        <el-table-column label="操作" width="340" fixed="right">
          <template #default="{ row }">
            <div style="white-space:nowrap">
              <el-button text size="small" @click="$router.push(`/instances/${row.id}`)">
                <el-icon><Monitor /></el-icon> 实例
              </el-button>
              <el-button text size="small" @click="$router.push(`/oci-users/${row.id}`)">
                <el-icon><User /></el-icon> 用户
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
            </div>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Add/Edit Dialog -->
    <el-dialog v-model="dialogVisible" :title="editId ? '编辑账户' : '添加云账户'" width="600px">
      <!-- 导入区域：仅在添加模式下显示 -->
      <div v-if="!editId" class="import-section">
        <el-divider content-position="left">快速导入 OCI Config</el-divider>
        <div class="import-actions">
          <el-button size="small" @click="showPasteArea = !showPasteArea">
            <el-icon><DocumentCopy /></el-icon> 粘贴配置
          </el-button>
          <el-upload
            :show-file-list="false"
            :before-upload="handleFileUpload"
            accept=".conf,.config,.pem,.txt,*"
          >
            <el-button size="small">
              <el-icon><Upload /></el-icon> 上传配置文件
            </el-button>
          </el-upload>
        </div>
        <div v-if="showPasteArea" class="paste-area">
          <el-input
            v-model="pasteContent"
            type="textarea"
            :rows="6"
            placeholder="粘贴 OCI config 内容，例如：
[DEFAULT]
user=ocid1.user.oc1..xxx
fingerprint=xx:xx:xx:...
tenancy=ocid1.tenancy.oc1..xxx
region=ap-singapore-1
key_file=xxx.pem"
          />
          <el-button type="primary" size="small" style="margin-top:8px" @click="parseAndFill">
            识别并填入表单
          </el-button>
        </div>
      </div>

      <el-form :model="form" :rules="rules" ref="formRef" label-width="120px" style="margin-top:16px">
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
        <el-form-item label="私钥 (PEM)" prop="private_key">
          <el-input
            v-model="form.private_key"
            type="textarea"
            :rows="6"
            placeholder="留空表示使用个人设置中的默认私钥"
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
const showPasteArea = ref(false)
const pasteContent = ref('')

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

/**
 * 解析 OCI config 格式的文本内容
 * 支持格式：
 * [DEFAULT]
 * user=ocid1.user.oc1..xxx
 * fingerprint=xx:xx:xx:...
 * tenancy=ocid1.tenancy.oc1..xxx
 * region=ap-singapore-1
 * key_file=xxx.pem  (忽略)
 */
function parseOciConfig(text) {
  const result = {}
  const lines = text.split(/\r?\n/)
  for (const line of lines) {
    const trimmed = line.trim()
    // 跳过空行、注释、section header
    if (!trimmed || trimmed.startsWith('#') || trimmed.startsWith('[')) continue
    const eqIndex = trimmed.indexOf('=')
    if (eqIndex === -1) continue
    const key = trimmed.substring(0, eqIndex).trim().toLowerCase()
    const value = trimmed.substring(eqIndex + 1).trim()
    if (!value) continue
    // 忽略 key_file
    if (key === 'key_file') continue
    result[key] = value
  }
  return result
}

/**
 * 将解析结果填入表单
 */
function fillFormFromConfig(parsed) {
  let filled = 0
  if (parsed.user) {
    form.user_ocid = parsed.user
    filled++
  }
  if (parsed.fingerprint) {
    form.fingerprint = parsed.fingerprint
    filled++
  }
  if (parsed.tenancy) {
    form.tenancy_ocid = parsed.tenancy
    filled++
  }
  if (parsed.region) {
    // region 可能是单个值，加入到数组中（如果还没有的话）
    const regionVal = parsed.region
    if (!form.region.includes(regionVal)) {
      form.region = [regionVal]
    }
    filled++
  }
  return filled
}

function parseAndFill() {
  if (!pasteContent.value.trim()) {
    ElMessage.warning('请先粘贴配置内容')
    return
  }
  const parsed = parseOciConfig(pasteContent.value)
  const filled = fillFormFromConfig(parsed)
  if (filled === 0) {
    ElMessage.error('未能识别有效的配置项，请检查格式')
  } else {
    ElMessage.success(`已识别并填入 ${filled} 项配置，请检查后保存`)
    showPasteArea.value = false
    pasteContent.value = ''
  }
}

function handleFileUpload(file) {
  const reader = new FileReader()
  reader.onload = (e) => {
    const content = e.target.result
    const parsed = parseOciConfig(content)
    const filled = fillFormFromConfig(parsed)
    if (filled === 0) {
      ElMessage.error('文件中未能识别有效的配置项，请检查文件格式')
    } else {
      ElMessage.success(`已从文件识别并填入 ${filled} 项配置，请检查后保存`)
    }
  }
  reader.onerror = () => {
    ElMessage.error('文件读取失败')
  }
  reader.readAsText(file)
  // 返回 false 阻止 el-upload 默认上传行为
  return false
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
    const payload = { ...form }
    if (!payload.private_key) delete payload.private_key
    if (editId.value) {
      await api.put(`/tenants/${editId.value}`, payload)
      ElMessage.success('更新成功')
    } else {
      await api.post('/tenants', payload)
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
.import-section { margin-bottom: 8px; }
.import-actions { display: flex; gap: 12px; align-items: center; margin-bottom: 12px; }
.paste-area { margin-top: 8px; }
</style>
