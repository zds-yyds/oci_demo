<template>
  <div>
    <div class="page-header">
      <h2>个人设置</h2>
    </div>

    <el-row :gutter="16">
      <!-- 默认私钥 -->
      <el-col :span="12">
        <el-card shadow="never">
          <template #header>
            <div style="display:flex;align-items:center;gap:8px">
              <el-icon color="#409eff"><Key /></el-icon>
              <span>默认 OCI 私钥</span>
              <el-tag v-if="hasKey" type="success" size="small">已设置</el-tag>
              <el-tag v-else type="info" size="small">未设置</el-tag>
            </div>
          </template>

          <el-alert type="info" :closable="false" style="margin-bottom:16px">
            设置后，添加云账户时私钥栏会自动预填，无需每次粘贴。私钥仅存储在数据库中，不会明文返回。
          </el-alert>

          <div v-if="hasKey && !editing" class="key-preview">
            <el-icon><Lock /></el-icon>
            <span>{{ preview }}</span>
            <span style="color:#909399;margin-left:4px">（已加密存储）</span>
          </div>

          <el-form v-if="editing || !hasKey" style="margin-top:8px">
            <el-form-item>
              <el-input
                v-model="privateKey"
                type="textarea"
                :rows="8"
                placeholder="-----BEGIN PRIVATE KEY-----&#10;MIIEvw...&#10;-----END PRIVATE KEY-----"
                style="font-family:monospace;font-size:12px"
              />
            </el-form-item>
          </el-form>

          <div style="display:flex;justify-content:space-between;align-items:center;margin-top:12px">
            <el-upload
              v-if="editing || !hasKey"
              :show-file-list="false"
              :before-upload="handleKeyFileUpload"
              accept=".pem,.key,.txt,*"
            >
              <el-button size="small">
                <el-icon><Upload /></el-icon> 上传私钥文件
              </el-button>
            </el-upload>
            <span v-else></span>
            <div style="display:flex;gap:8px">
              <el-button
                v-if="!editing && hasKey"
                type="primary"
                @click="editing = true"
              >
                <el-icon><Edit /></el-icon> 修改私钥
              </el-button>
              <el-button
                v-if="editing || !hasKey"
                type="primary"
                :loading="saving"
                @click="saveKey"
              >
                <el-icon><Check /></el-icon> 保存
              </el-button>
              <el-button
                v-if="editing"
                @click="cancelEdit"
              >取消</el-button>
              <el-button
                v-if="hasKey"
                type="danger"
                plain
                @click="clearKey"
              >
                <el-icon><Delete /></el-icon> 清除私钥
              </el-button>
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- 默认 SSH 公钥 -->
      <el-col :span="12">
        <el-card shadow="never">
          <template #header>
            <div style="display:flex;align-items:center;gap:8px">
              <el-icon color="#67c23a"><Connection /></el-icon>
              <span>默认 SSH 公钥</span>
              <el-tag v-if="hasSSHKey" type="success" size="small">已设置</el-tag>
              <el-tag v-else type="info" size="small">未设置</el-tag>
            </div>
          </template>

          <el-alert type="info" :closable="false" style="margin-bottom:16px">
            设置后，新建抢机任务时 SSH 公钥会自动使用此默认值，无需每次粘贴。公钥仅存储在数据库中。
          </el-alert>

          <div v-if="hasSSHKey && !sshEditing" class="key-preview">
            <el-icon><Key /></el-icon>
            <span>{{ sshPreview }}</span>
          </div>

          <el-form v-if="sshEditing || !hasSSHKey" style="margin-top:8px">
            <el-form-item>
              <el-input
                v-model="sshPublicKey"
                type="textarea"
                :rows="8"
                placeholder="ssh-rsa AAAAB3NzaC1yc2EAAAA..."
                style="font-family:monospace;font-size:12px"
              />
            </el-form-item>
          </el-form>

          <div style="display:flex;justify-content:space-between;align-items:center;margin-top:12px">
            <el-upload
              v-if="sshEditing || !hasSSHKey"
              :show-file-list="false"
              :before-upload="handleSSHFileUpload"
              accept=".pub,.txt,*"
            >
              <el-button size="small">
                <el-icon><Upload /></el-icon> 上传公钥文件
              </el-button>
            </el-upload>
            <span v-else></span>
            <div style="display:flex;gap:8px">
              <el-button
                v-if="!sshEditing && hasSSHKey"
                type="primary"
                @click="sshEditing = true"
              >
                <el-icon><Edit /></el-icon> 修改公钥
              </el-button>
              <el-button
                v-if="sshEditing || !hasSSHKey"
                type="primary"
                :loading="sshSaving"
                @click="saveSSHKey"
              >
                <el-icon><Check /></el-icon> 保存
              </el-button>
              <el-button
                v-if="sshEditing"
                @click="cancelSSHEdit"
              >取消</el-button>
              <el-button
                v-if="hasSSHKey"
                type="danger"
                plain
                @click="clearSSHKey"
              >
                <el-icon><Delete /></el-icon> 清除公钥
              </el-button>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 修改密码 -->
    <el-row :gutter="16" style="margin-top:16px">
      <el-col :span="12">
        <el-card shadow="never">
          <template #header>
            <div style="display:flex;align-items:center;gap:8px">
              <el-icon color="#e6a23c"><Lock /></el-icon>
              <span>修改密码</span>
            </div>
          </template>
          <el-form :model="pwdForm" :rules="pwdRules" ref="pwdFormRef" label-width="90px">
            <el-form-item label="旧密码" prop="old_password">
              <el-input v-model="pwdForm.old_password" type="password" show-password />
            </el-form-item>
            <el-form-item label="新密码" prop="new_password">
              <el-input v-model="pwdForm.new_password" type="password" show-password />
            </el-form-item>
            <el-form-item label="确认密码" prop="confirm_password">
              <el-input v-model="pwdForm.confirm_password" type="password" show-password />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="pwdSaving" @click="changePassword">
                修改密码
              </el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/api'

// ── 默认私钥 ──────────────────────────────────────────────────────────────────
const hasKey = ref(false)
const preview = ref('')
const privateKey = ref('')
const editing = ref(false)
const saving = ref(false)

// ── 默认 SSH 公钥 ─────────────────────────────────────────────────────────────
const hasSSHKey = ref(false)
const sshPreview = ref('')
const sshPublicKey = ref('')
const sshEditing = ref(false)
const sshSaving = ref(false)

// ── 修改密码 ──────────────────────────────────────────────────────────────────
const pwdFormRef = ref()
const pwdSaving = ref(false)
const pwdForm = reactive({ old_password: '', new_password: '', confirm_password: '' })
const pwdRules = {
  old_password: [{ required: true, message: '请输入旧密码' }],
  new_password: [{ required: true, message: '请输入新密码', min: 6 }],
  confirm_password: [
    { required: true, message: '请确认新密码' },
    {
      validator: (_, value, cb) => {
        if (value !== pwdForm.new_password) cb(new Error('两次密码不一致'))
        else cb()
      },
    },
  ],
}

// ── 私钥相关方法 ──────────────────────────────────────────────────────────────
async function loadKeyStatus() {
  const res = await api.get('/users/me/default-key')
  hasKey.value = res.data.has_key
  preview.value = res.data.preview || ''
}

async function saveKey() {
  if (!privateKey.value.trim()) {
    ElMessage.warning('请输入私钥内容')
    return
  }
  saving.value = true
  try {
    await api.put('/users/me/default-key', { private_key: privateKey.value })
    ElMessage.success('默认私钥已保存')
    editing.value = false
    privateKey.value = ''
    await loadKeyStatus()
  } finally {
    saving.value = false
  }
}

async function clearKey() {
  await ElMessageBox.confirm('确认清除默认私钥？', '警告', { type: 'warning' })
  await api.put('/users/me/default-key', { private_key: '' })
  ElMessage.success('已清除')
  hasKey.value = false
  preview.value = ''
  privateKey.value = ''
}

function cancelEdit() {
  editing.value = false
  privateKey.value = ''
}

function handleKeyFileUpload(file) {
  const reader = new FileReader()
  reader.onload = (e) => {
    const content = e.target.result.trim()
    if (content) {
      privateKey.value = content
      ElMessage.success('已读取私钥文件内容，请确认后保存')
    } else {
      ElMessage.error('文件内容为空')
    }
  }
  reader.onerror = () => {
    ElMessage.error('文件读取失败')
  }
  reader.readAsText(file)
  return false
}

// ── SSH 公钥相关方法 ──────────────────────────────────────────────────────────
async function loadSSHKeyStatus() {
  const res = await api.get('/users/me/default-ssh-key')
  hasSSHKey.value = res.data.has_key
  sshPreview.value = res.data.preview || ''
}

async function saveSSHKey() {
  if (!sshPublicKey.value.trim()) {
    ElMessage.warning('请输入 SSH 公钥内容')
    return
  }
  sshSaving.value = true
  try {
    await api.put('/users/me/default-ssh-key', { ssh_public_key: sshPublicKey.value })
    ElMessage.success('默认 SSH 公钥已保存')
    sshEditing.value = false
    sshPublicKey.value = ''
    await loadSSHKeyStatus()
  } finally {
    sshSaving.value = false
  }
}

async function clearSSHKey() {
  await ElMessageBox.confirm('确认清除默认 SSH 公钥？', '警告', { type: 'warning' })
  await api.put('/users/me/default-ssh-key', { ssh_public_key: '' })
  ElMessage.success('已清除')
  hasSSHKey.value = false
  sshPreview.value = ''
  sshPublicKey.value = ''
}

function cancelSSHEdit() {
  sshEditing.value = false
  sshPublicKey.value = ''
}

function handleSSHFileUpload(file) {
  const reader = new FileReader()
  reader.onload = (e) => {
    const content = e.target.result.trim()
    if (content) {
      sshPublicKey.value = content
      ElMessage.success('已读取公钥文件内容，请确认后保存')
    } else {
      ElMessage.error('文件内容为空')
    }
  }
  reader.onerror = () => {
    ElMessage.error('文件读取失败')
  }
  reader.readAsText(file)
  return false
}

// ── 修改密码 ──────────────────────────────────────────────────────────────────
async function changePassword() {
  await pwdFormRef.value.validate()
  pwdSaving.value = true
  try {
    await api.post('/auth/change-password', {
      old_password: pwdForm.old_password,
      new_password: pwdForm.new_password,
    })
    ElMessage.success('密码修改成功，请重新登录')
    Object.assign(pwdForm, { old_password: '', new_password: '', confirm_password: '' })
  } finally {
    pwdSaving.value = false
  }
}

onMounted(() => {
  loadKeyStatus()
  loadSSHKeyStatus()
})
</script>

<style scoped>
.page-header { margin-bottom: 20px; }
.page-header h2 { font-size: 22px; }
.key-preview {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px;
  background: #f5f7fa;
  border-radius: 8px;
  font-family: monospace;
  font-size: 13px;
  color: #303133;
  word-break: break-all;
}
</style>
