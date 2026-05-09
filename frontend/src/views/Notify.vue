<template>
  <div>
    <div class="page-header">
      <h2>通知配置</h2>
      <el-button type="primary" @click="openAdd">
        <el-icon><Plus /></el-icon> 添加通知
      </el-button>
    </div>

    <el-row :gutter="16">
      <el-col :span="8" v-for="cfg in configs" :key="cfg.id" style="margin-bottom:16px">
        <el-card shadow="hover" class="notify-card">
          <div class="notify-header">
            <div class="notify-type">
              <el-icon size="20" :color="cfg.notify_type === 'email' ? '#409eff' : '#07c160'">
                <component :is="cfg.notify_type === 'email' ? 'Message' : 'ChatDotRound'" />
              </el-icon>
              <span>{{ cfg.notify_type === 'email' ? '邮件通知' : '企业微信' }}</span>
            </div>
            <el-tag :type="cfg.is_active ? 'success' : 'info'" size="small">
              {{ cfg.is_active ? '启用' : '禁用' }}
            </el-tag>
          </div>
          <div class="notify-info">
            <template v-if="cfg.notify_type === 'email'">
              <div>发件人: {{ cfg.sender_email }}</div>
              <div>收件人: {{ cfg.receiver_email }}</div>
              <div>SMTP: {{ cfg.smtp_server }}:{{ cfg.smtp_port }}</div>
            </template>
            <template v-else>
              <div>Webhook: {{ cfg.wecom_webhook?.substring(0, 40) }}...</div>
            </template>
          </div>
          <div class="notify-actions">
            <el-button size="small" @click="testNotify(cfg)">
              <el-icon><Promotion /></el-icon> 测试
            </el-button>
            <el-button size="small" @click="openEdit(cfg)">
              <el-icon><Edit /></el-icon> 编辑
            </el-button>
            <el-button size="small" type="danger" @click="deleteConfig(cfg)">
              <el-icon><Delete /></el-icon>
            </el-button>
          </div>
        </el-card>
      </el-col>

      <el-col :span="8" v-if="configs.length === 0">
        <el-empty description="暂无通知配置，点击右上角添加" />
      </el-col>
    </el-row>

    <!-- Dialog -->
    <el-dialog v-model="dialogVisible" :title="editId ? '编辑通知' : '添加通知'" width="520px">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="110px">
        <el-form-item label="通知类型" prop="notify_type">
          <el-radio-group v-model="form.notify_type" @change="onTypeChange">
            <el-radio-button value="email">邮件</el-radio-button>
            <el-radio-button value="wecom">企业微信</el-radio-button>
          </el-radio-group>
        </el-form-item>

        <template v-if="form.notify_type === 'email'">
          <el-form-item label="SMTP 服务器" prop="smtp_server">
            <el-input v-model="form.smtp_server" placeholder="smtp.qq.com" />
          </el-form-item>
          <el-form-item label="SMTP 端口" prop="smtp_port">
            <el-input-number v-model="form.smtp_port" :min="1" :max="65535" />
          </el-form-item>
          <el-form-item label="发件人邮箱" prop="sender_email">
            <el-input v-model="form.sender_email" placeholder="xxx@qq.com" />
          </el-form-item>
          <el-form-item label="邮箱授权码" prop="sender_password">
            <el-input v-model="form.sender_password" type="password" show-password placeholder="QQ邮箱授权码" />
          </el-form-item>
          <el-form-item label="收件人邮箱" prop="receiver_email">
            <el-input v-model="form.receiver_email" placeholder="xxx@example.com" />
          </el-form-item>
        </template>

        <template v-if="form.notify_type === 'wecom'">
          <el-form-item label="Webhook URL" prop="wecom_webhook">
            <el-input
              v-model="form.wecom_webhook"
              type="textarea"
              :rows="3"
              placeholder="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=..."
            />
          </el-form-item>
          <el-alert type="info" :closable="false" style="margin-bottom:12px">
            在企业微信群中添加机器人，复制 Webhook 地址粘贴到此处
          </el-alert>
        </template>
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

const configs = ref([])
const dialogVisible = ref(false)
const saving = ref(false)
const editId = ref(null)
const formRef = ref()

const form = reactive({
  notify_type: 'email',
  smtp_server: 'smtp.qq.com',
  smtp_port: 587,
  sender_email: '',
  sender_password: '',
  receiver_email: '',
  wecom_webhook: '',
})

const rules = {
  notify_type: [{ required: true }],
}

function onTypeChange() {
  // Reset fields on type change
}

async function load() {
  const res = await api.get('/notify')
  configs.value = res.data
}

function openAdd() {
  editId.value = null
  Object.assign(form, { notify_type: 'email', smtp_server: 'smtp.qq.com', smtp_port: 587, sender_email: '', sender_password: '', receiver_email: '', wecom_webhook: '' })
  dialogVisible.value = true
}

function openEdit(cfg) {
  editId.value = cfg.id
  Object.assign(form, {
    notify_type: cfg.notify_type,
    smtp_server: cfg.smtp_server || 'smtp.qq.com',
    smtp_port: cfg.smtp_port || 587,
    sender_email: cfg.sender_email || '',
    sender_password: '',
    receiver_email: cfg.receiver_email || '',
    wecom_webhook: cfg.wecom_webhook || '',
  })
  dialogVisible.value = true
}

async function save() {
  await formRef.value.validate()
  saving.value = true
  try {
    if (editId.value) {
      await api.put(`/notify/${editId.value}`, form)
      ElMessage.success('更新成功')
    } else {
      await api.post('/notify', form)
      ElMessage.success('添加成功')
    }
    dialogVisible.value = false
    load()
  } finally {
    saving.value = false
  }
}

async function deleteConfig(cfg) {
  await ElMessageBox.confirm('确认删除该通知配置？', '警告', { type: 'warning' })
  await api.delete(`/notify/${cfg.id}`)
  ElMessage.success('删除成功')
  load()
}

async function testNotify(cfg) {
  const res = await api.post(`/notify/${cfg.id}/test`, { message: '这是来自 OCI Manager 的测试消息 🎉' })
  if (res.data.success) {
    ElMessage.success('测试消息发送成功！')
  } else {
    ElMessage.error('发送失败，请检查配置')
  }
}

onMounted(load)
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.page-header h2 { font-size: 22px; }
.notify-card { border-radius: 12px; }
.notify-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.notify-type { display: flex; align-items: center; gap: 8px; font-weight: 600; font-size: 15px; }
.notify-info { font-size: 13px; color: #606266; margin-bottom: 16px; display: flex; flex-direction: column; gap: 4px; }
.notify-actions { display: flex; gap: 8px; }
</style>
