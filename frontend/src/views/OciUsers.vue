<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-3">
        <button class="btn-ghost btn-sm" @click="$router.back()">← 返回</button>
        <h2 class="text-2xl font-bold text-surface-900 dark:text-white">OCI 用户管理 — {{ tenantName }}</h2>
      </div>
      <button class="btn-primary" @click="openAdd">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" /></svg>
        创建用户
      </button>
    </div>

    <!-- Users Table -->
    <div class="card overflow-hidden">
      <Loading :loading="loading" text="加载用户列表..." />
      <div v-if="!loading && users.length === 0" class="text-center text-surface-400 py-12">暂无 IAM 用户</div>
      <div v-if="!loading && users.length > 0" class="table-container">
        <table class="table">
          <thead>
            <tr>
              <th>用户名/邮箱</th>
              <th>邮箱</th>
              <th>描述</th>
              <th>状态</th>
              <th>创建时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="user in users" :key="user.id">
              <td class="font-medium">{{ user.name }}</td>
              <td>{{ user.email || '-' }}</td>
              <td class="text-xs max-w-[180px] truncate" :title="user.description">{{ user.description || '-' }}</td>
              <td>
                <span :class="stateClass(user.lifecycle_state)">{{ user.lifecycle_state }}</span>
              </td>
              <td class="whitespace-nowrap text-sm">{{ formatDate(user.time_created) }}</td>
              <td>
                <div class="flex items-center gap-1">
                  <button
                    class="btn-ghost btn-sm text-amber-600 dark:text-amber-400"
                    :disabled="resettingMfaId === user.id"
                    @click="resetMfa(user)"
                  >
                    <svg v-if="resettingMfaId !== user.id" class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>
                    <svg v-else class="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path></svg>
                    重置因素
                  </button>
                  <button class="btn-ghost btn-sm text-red-600 dark:text-red-400" @click="deleteUser(user)">删除</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Create Dialog -->
    <Modal :visible="dialogVisible" title="创建 OCI IAM 用户" width="450px" @close="dialogVisible = false">
      <div class="space-y-4">
        <div>
          <label class="label">邮箱</label>
          <input v-model="form.email" type="email" class="input" placeholder="用户邮箱（同时作为登录名）" />
        </div>
        <p class="text-xs text-surface-500">创建后用户将自动加入 Administrators 组，拥有管理员权限。</p>
      </div>
      <template #footer>
        <button class="btn-secondary" @click="dialogVisible = false">取消</button>
        <button class="btn-primary" :disabled="saving || !form.email" @click="save">
          {{ saving ? '创建中...' : '创建' }}
        </button>
      </template>
    </Modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import api from '@/api'
import { useToast } from '@/composables/useToast'
import { useModal } from '@/composables/useModal'
import Modal from '@/components/Modal.vue'
import Loading from '@/components/Loading.vue'
import dayjs from 'dayjs'

const route = useRoute()
const { success } = useToast()
const { confirm } = useModal()

const tenantId = route.params.tenantId as string
const tenantName = ref('')
const users = ref<any[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const saving = ref(false)
const resettingMfaId = ref<string | null>(null)

const form = reactive({ email: '' })

function formatDate(d: string) {
  return d ? dayjs(d).format('YYYY-MM-DD HH:mm') : '-'
}

function stateClass(state: string) {
  switch (state) {
    case 'ACTIVE': return 'badge-success'
    case 'INACTIVE': return 'badge-neutral'
    case 'DELETED': return 'badge-danger'
    default: return 'badge-info'
  }
}

async function load() {
  loading.value = true
  try {
    const [usersRes, tenantRes] = await Promise.all([
      api.get(`/oci-users/${tenantId}`),
      api.get(`/tenants/${tenantId}`),
    ])
    users.value = usersRes.data
    tenantName.value = tenantRes.data.name
  } catch { /* handled by interceptor */ } finally {
    loading.value = false
  }
}

function openAdd() {
  form.email = ''
  dialogVisible.value = true
}

async function save() {
  if (!form.email) return
  saving.value = true
  try {
    const res = await api.post(`/oci-users/${tenantId}`, { email: form.email })
    success(res.data.message || '用户创建成功')
    dialogVisible.value = false
    load()
  } finally {
    saving.value = false
  }
}

async function resetMfa(row: any) {
  const ok = await confirm(
    `确认重置用户「${row.name}」的所有 MFA 认证因素？重置后用户需要重新注册 MFA 设备。`,
    '重置认证因素',
    { type: 'warning' }
  )
  if (!ok) return
  resettingMfaId.value = row.id
  try {
    const res = await api.post(`/oci-users/${tenantId}/${encodeURIComponent(row.id)}/reset-mfa`)
    success(res.data.message || '认证因素重置成功')
  } finally {
    resettingMfaId.value = null
  }
}

async function deleteUser(row: any) {
  const ok = await confirm(
    `确认删除 OCI 用户「${row.name}」？此操作不可恢复。`,
    '警告',
    { type: 'warning' }
  )
  if (!ok) return
  try {
    await api.delete(`/oci-users/${tenantId}/${encodeURIComponent(row.id)}`)
    success('用户删除成功')
    load()
  } catch { /* handled by interceptor */ }
}

onMounted(load)
</script>
