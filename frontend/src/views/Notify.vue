<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <h2 class="text-2xl font-bold text-surface-900 dark:text-white">通知配置</h2>
      <button class="btn-primary" @click="openAdd">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" /></svg>
        添加通知
      </button>
    </div>

    <div class="grid grid-cols-3 gap-4">
      <div v-for="cfg in configs" :key="cfg.id" class="card p-5 space-y-4">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2">
            <div class="w-8 h-8 rounded-lg flex items-center justify-center" :class="cfg.notify_type === 'email' ? 'bg-blue-100 dark:bg-blue-900/30' : 'bg-green-100 dark:bg-green-900/30'">
              <svg v-if="cfg.notify_type === 'email'" class="w-4 h-4 text-blue-600 dark:text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
              </svg>
              <svg v-else class="w-4 h-4 text-green-600 dark:text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
              </svg>
            </div>
            <span class="font-semibold text-surface-900 dark:text-white">{{ cfg.notify_type === 'email' ? '邮件通知' : '企业微信' }}</span>
          </div>
          <span :class="cfg.is_active ? 'badge-success' : 'badge-neutral'">{{ cfg.is_active ? '启用' : '禁用' }}</span>
        </div>

        <div class="text-sm text-surface-500 dark:text-surface-400 space-y-1">
          <template v-if="cfg.notify_type === 'email'">
            <div>发件人: {{ cfg.sender_email }}</div>
            <div>收件人: {{ cfg.receiver_email }}</div>
            <div>SMTP: {{ cfg.smtp_server }}:{{ cfg.smtp_port }}</div>
          </template>
          <template v-else>
            <div class="truncate">Webhook: {{ cfg.wecom_webhook?.substring(0, 40) }}...</div>
          </template>
        </div>

        <div class="flex items-center gap-2 pt-2 border-t border-surface-100 dark:border-surface-700">
          <button type="button" @click="toggleActive(cfg)" class="relative w-9 h-5 rounded-full transition-colors shrink-0" :class="cfg.is_active ? 'bg-primary-600' : 'bg-surface-300 dark:bg-surface-600'">
            <span class="absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform" :class="cfg.is_active ? 'translate-x-4' : ''"></span>
          </button>
          <div class="flex-1"></div>
          <button class="btn-ghost btn-sm" @click="testNotify(cfg)">测试</button>
          <button class="btn-ghost btn-sm" @click="openEdit(cfg)">编辑</button>
          <button class="btn-ghost btn-sm text-red-600 dark:text-red-400" @click="deleteConfig(cfg)">删除</button>
        </div>
      </div>

      <div v-if="configs.length === 0" class="col-span-3 card p-12 text-center text-surface-400">
        暂无通知配置，点击右上角添加
      </div>
    </div>

    <!-- Dialog -->
    <Modal :visible="dialogVisible" :title="editId ? '编辑通知' : '添加通知'" width="520px" @close="dialogVisible = false">
      <form class="space-y-4" @submit.prevent="save">
        <div>
          <label class="label">通知类型</label>
          <div class="flex gap-2">
            <button type="button" @click="form.notify_type = 'email'" class="flex-1 py-2 rounded-lg border text-sm font-medium transition-all" :class="form.notify_type === 'email' ? 'border-primary-500 bg-primary-50 dark:bg-primary-950/50 text-primary-700 dark:text-primary-300' : 'border-surface-300 dark:border-surface-600 text-surface-600 dark:text-surface-400'">
              邮件
            </button>
            <button type="button" @click="form.notify_type = 'wecom'" class="flex-1 py-2 rounded-lg border text-sm font-medium transition-all" :class="form.notify_type === 'wecom' ? 'border-primary-500 bg-primary-50 dark:bg-primary-950/50 text-primary-700 dark:text-primary-300' : 'border-surface-300 dark:border-surface-600 text-surface-600 dark:text-surface-400'">
              企业微信
            </button>
          </div>
        </div>

        <template v-if="form.notify_type === 'email'">
          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="label">SMTP 服务器</label>
              <input v-model="form.smtp_server" class="input" placeholder="smtp.qq.com" />
            </div>
            <div>
              <label class="label">SMTP 端口</label>
              <input v-model.number="form.smtp_port" type="number" class="input" />
            </div>
          </div>
          <div>
            <label class="label">发件人邮箱</label>
            <input v-model="form.sender_email" class="input" placeholder="xxx@qq.com" />
          </div>
          <div>
            <label class="label">邮箱授权码</label>
            <input v-model="form.sender_password" type="password" class="input" placeholder="QQ邮箱授权码" />
          </div>
          <div>
            <label class="label">收件人邮箱</label>
            <input v-model="form.receiver_email" class="input" placeholder="xxx@example.com" />
          </div>
        </template>

        <template v-if="form.notify_type === 'wecom'">
          <div>
            <label class="label">Webhook URL</label>
            <textarea v-model="form.wecom_webhook" class="input min-h-[80px]" placeholder="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=..."></textarea>
          </div>
          <div class="text-sm text-surface-500 bg-blue-50 dark:bg-blue-950/30 rounded-lg p-3">
            在企业微信群中添加机器人，复制 Webhook 地址粘贴到此处
          </div>
        </template>
      </form>
      <template #footer>
        <button class="btn-secondary" @click="dialogVisible = false">取消</button>
        <button class="btn-primary" :disabled="saving" @click="save">保存</button>
      </template>
    </Modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useToast } from '@/composables/useToast'
import { useModal } from '@/composables/useModal'
import api from '@/api'
import Modal from '@/components/Modal.vue'
import type { NotifyConfig } from '@/types'

const { success } = useToast()
const { confirm } = useModal()

const configs = ref<NotifyConfig[]>([])
const dialogVisible = ref(false)
const saving = ref(false)
const editId = ref<number | null>(null)

const form = reactive({
  notify_type: 'email' as 'email' | 'wecom',
  smtp_server: 'smtp.qq.com',
  smtp_port: 587,
  sender_email: '',
  sender_password: '',
  receiver_email: '',
  wecom_webhook: '',
})

async function load() {
  const res = await api.get('/notify')
  configs.value = res.data
}

function openAdd() {
  editId.value = null
  Object.assign(form, { notify_type: 'email', smtp_server: 'smtp.qq.com', smtp_port: 587, sender_email: '', sender_password: '', receiver_email: '', wecom_webhook: '' })
  dialogVisible.value = true
}

function openEdit(cfg: NotifyConfig) {
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
  saving.value = true
  try {
    if (editId.value) {
      await api.put(`/notify/${editId.value}`, form)
      success('更新成功')
    } else {
      await api.post('/notify', form)
      success('添加成功')
    }
    dialogVisible.value = false
    load()
  } finally {
    saving.value = false
  }
}

async function deleteConfig(cfg: NotifyConfig) {
  const ok = await confirm('确认删除该通知配置？', '警告', { type: 'warning' })
  if (!ok) return
  await api.delete(`/notify/${cfg.id}`)
  success('删除成功')
  load()
}

async function testNotify(cfg: NotifyConfig) {
  const res = await api.post(`/notify/${cfg.id}/test`, { message: '这是来自 OCI Manager 的测试消息 🎉' })
  if (res.data.success) {
    success('测试消息发送成功！')
  }
}

async function toggleActive(cfg: NotifyConfig) {
  try {
    const res = await api.put(`/notify/${cfg.id}/toggle`)
    cfg.is_active = res.data.is_active
    success(cfg.is_active ? '已启用' : '已禁用')
  } catch {
    cfg.is_active = !cfg.is_active
  }
}

onMounted(load)
</script>
