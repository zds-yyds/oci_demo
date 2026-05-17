<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center gap-3">
      <button class="btn-ghost btn-sm" @click="$router.back()">← 返回</button>
      <h2 class="text-2xl font-bold text-surface-900 dark:text-white">VCN 管理 — {{ tenantName }}</h2>
    </div>

    <!-- Region selector -->
    <div class="card p-4">
      <div class="flex items-center gap-3">
        <span class="text-sm text-surface-500 shrink-0">区域</span>
        <select v-model="selectedRegion" class="select w-52" @change="loadVcns">
          <option value="">选择区域</option>
          <option v-for="r in regions" :key="r" :value="r">{{ r }}</option>
        </select>
      </div>
    </div>

    <!-- VCN Table -->
    <div class="card overflow-hidden">
      <Loading :loading="loading" text="加载 VCN 列表..." />
      <div v-if="!loading && vcnList.length === 0" class="text-center text-surface-400 py-12">
        {{ selectedRegion ? '该区域暂无 VCN 数据' : '请先选择区域' }}
      </div>
      <div v-if="!loading && vcnList.length > 0" class="table-container">
        <table class="table">
          <thead>
            <tr>
              <th>名称</th>
              <th>CIDR 块</th>
              <th>IPv6</th>
              <th>状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="vcn in vcnList" :key="vcn.id">
              <td class="font-medium">{{ vcn.display_name }}</td>
              <td class="font-mono text-xs">{{ vcn.cidr_block || '-' }}</td>
              <td>
                <span v-if="vcn.ipv6_cidr_blocks && vcn.ipv6_cidr_blocks.length" class="badge-success">有</span>
                <span v-else class="badge-neutral">无</span>
              </td>
              <td>
                <span :class="vcn.lifecycle_state === 'AVAILABLE' ? 'badge-success' : 'badge-warning'">
                  {{ vcn.lifecycle_state }}
                </span>
              </td>
              <td>
                <button class="btn-ghost btn-sm text-red-600 dark:text-red-400" @click="doDelete(vcn)">删除</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import api from '@/api'
import { useToast } from '@/composables/useToast'
import { useModal } from '@/composables/useModal'
import Loading from '@/components/Loading.vue'

const route = useRoute()
const { success } = useToast()
const { confirm } = useModal()
const tenantId = route.params.tenantId as string
const tenantName = ref('')
const regions = ref<string[]>([])
const selectedRegion = ref('')
const vcnList = ref<any[]>([])
const loading = ref(false)

async function loadTenant() {
  const res = await api.get(`/tenants/${tenantId}`)
  tenantName.value = res.data.name
  regions.value = res.data.region || []
  if (regions.value.length > 0) {
    selectedRegion.value = regions.value[0]
    await loadVcns()
  }
}

async function loadVcns() {
  if (!selectedRegion.value) return
  loading.value = true
  try {
    const res = await api.get(`/vcn/${tenantId}`, { params: { region: selectedRegion.value } })
    vcnList.value = res.data
  } catch { /* handled by interceptor */ } finally {
    loading.value = false
  }
}

async function doDelete(row: any) {
  const ok = await confirm(
    `确认删除 VCN「${row.display_name}」？将同时清理其下属子网、网关等资源。`,
    '危险操作',
    { type: 'error', confirmText: '确认删除' }
  )
  if (!ok) return
  try {
    await api.post(`/vcn/${tenantId}/delete`, {
      region: selectedRegion.value,
      vcn_ids: [row.id],
    })
    success('VCN 删除指令已发送')
    setTimeout(loadVcns, 3000)
  } catch { /* handled by interceptor */ }
}

onMounted(loadTenant)
</script>
