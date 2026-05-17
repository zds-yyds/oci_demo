<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <h2 class="text-2xl font-bold text-surface-900 dark:text-white">用户管理</h2>
      <button class="btn-primary" @click="openAdd">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" /></svg>
        新建用户
      </button>
    </div>

    <div class="card">
      <Loading :loading="loading" />
      <div v-if="!loading" class="table-container">
        <table class="table">
          <thead>
            <tr>
              <th>用户名</th>
              <th>角色</th>
              <th>创建时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="u in users" :key="u.id">
              <td class="font-medium">{{ u.username }}</td>
              <td><span :class="u.is_admin ? 'badge-danger' : 'badge-neutral'">{{ u.is_admin ? '管理员' : '普通用户' }}</span></td>
              <td class="text-sm text-surface-500">{{ formatDate(u.created_at) }}</td>
              <td>
                <div class="flex items-center gap-1">
                  <button class="btn-ghost btn-sm" @click="openEdit(u)">编辑</button>
                  <button class="btn-ghost btn-sm text-red-600 dark:text-red-400" @click="deleteUser(u)">删除</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Dialog -->
    <Modal :visible="dialogVisible" :title="editId ? '编辑用户' : '新建用户'" width="420px" @close="dialogVisible = false">
      <form class="space-y-4" @submit.prevent="save">
        <div>
          <label class="label">用户名</label>
          <input v-model="form.username" class="input" required />
        </div>
        <div>
          <label class="label">密码</label>
          <input v-model="form.password" type="password" class="input" :placeholder="editId ? '留空表示不修改' : ''" :required="!editId" />
        </div>
        <div class="flex items-center gap-3">
          <label class="label mb-0">管理员</label>
          <button type="button" @click="form.is_admin = !form.is_admin" class="relative w-11 h-6 rounded-full transition-colors" :class="form.is_admin ? 'bg-primary-600' : 'bg-surface-300 dark:bg-surface-600'">
            <span class="absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform" :class="form.is_admin ? 'translate-x-5' : ''"></span>
          </button>
        </div>
      </form>
      <template #footer>
        <button class="btn-secondary" @click="dialogVisible = false">取消</button>
        <button class="btn-primary" :disabled="saving" @click="save">{{ editId ? '保存' : '创建' }}</button>
      </template>
    </Modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'
import { useModal } from '@/composables/useModal'
import api from '@/api'
import dayjs from 'dayjs'
import Modal from '@/components/Modal.vue'
import Loading from '@/components/Loading.vue'
import type { User } from '@/types'

const auth = useAuthStore()
const { success, warning } = useToast()
const { confirm } = useModal()

const users = ref<User[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const saving = ref(false)
const editId = ref<number | null>(null)

const form = reactive({ username: '', password: '', is_admin: false })

function formatDate(d: string) { return dayjs(d).format('YYYY-MM-DD HH:mm') }

async function load() {
  loading.value = true
  try {
    const res = await api.get('/users')
    users.value = res.data
  } finally {
    loading.value = false
  }
}

function openAdd() {
  editId.value = null
  Object.assign(form, { username: '', password: '', is_admin: false })
  dialogVisible.value = true
}

function openEdit(row: User) {
  editId.value = row.id
  Object.assign(form, { username: row.username, password: '', is_admin: row.is_admin })
  dialogVisible.value = true
}

async function save() {
  saving.value = true
  try {
    if (editId.value) {
      const payload: any = { username: form.username, is_admin: form.is_admin }
      if (form.password) payload.password = form.password
      await api.put(`/users/${editId.value}`, payload)
      success('用户更新成功')
    } else {
      await api.post('/users', form)
      success('用户创建成功')
    }
    dialogVisible.value = false
    load()
  } finally {
    saving.value = false
  }
}

async function deleteUser(row: User) {
  if (row.username === auth.user?.username) {
    warning('不能删除自己')
    return
  }
  const ok = await confirm(`确认删除用户「${row.username}」？`, '警告', { type: 'warning' })
  if (!ok) return
  await api.delete(`/users/${row.id}`)
  success('删除成功')
  load()
}

onMounted(load)
</script>
