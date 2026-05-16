<template>
  <el-container class="layout">
    <!-- Sidebar -->
    <el-aside :width="collapsed ? '64px' : '220px'" class="sidebar">
      <div class="sidebar-logo" @click="collapsed = !collapsed">
        <el-icon size="24" color="#409eff"><Cloud /></el-icon>
        <span v-if="!collapsed" class="logo-text">OCI Manager</span>
      </div>
      <el-menu
        :default-active="$route.path"
        router
        :collapse="collapsed"
        background-color="#1a1a2e"
        text-color="rgba(255,255,255,0.7)"
        active-text-color="#409eff"
        class="sidebar-menu"
      >
        <el-menu-item index="/dashboard">
          <el-icon><DataBoard /></el-icon>
          <template #title>控制台</template>
        </el-menu-item>
        <el-menu-item index="/tenants">
          <el-icon><OfficeBuilding /></el-icon>
          <template #title>云账户管理</template>
        </el-menu-item>
        <el-menu-item index="/snipe">
          <el-icon><Aim /></el-icon>
          <template #title>抢机任务</template>
        </el-menu-item>
        <el-menu-item index="/ip-data">
          <el-icon><MapLocation /></el-icon>
          <template #title>IP 数据</template>
        </el-menu-item>
        <el-menu-item index="/cloudflare">
          <el-icon><Cloudy /></el-icon>
          <template #title>Cloudflare DNS</template>
        </el-menu-item>
        <el-menu-item index="/bills">
          <el-icon><CreditCard /></el-icon>
          <template #title>账单监控</template>
        </el-menu-item>
        <el-menu-item index="/notify">
          <el-icon><Bell /></el-icon>
          <template #title>通知配置</template>
        </el-menu-item>
        <el-menu-item v-if="auth.isAdmin" index="/users">
          <el-icon><UserFilled /></el-icon>
          <template #title>用户管理</template>
        </el-menu-item>
        <el-menu-item index="/profile">
          <el-icon><Setting /></el-icon>
          <template #title>个人设置</template>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <!-- Header -->
      <el-header class="header">
        <div class="header-left">
          <el-breadcrumb separator="/">
            <el-breadcrumb-item :to="{ path: '/dashboard' }">首页</el-breadcrumb-item>
            <el-breadcrumb-item>{{ currentTitle }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        <div class="header-right">
          <el-tag type="success" size="small" style="margin-right:12px">
            {{ auth.user?.username }}
            <span v-if="auth.isAdmin"> · 管理员</span>
          </el-tag>
          <el-button text @click="handleLogout">
            <el-icon><SwitchButton /></el-icon> 退出
          </el-button>
        </div>
      </el-header>

      <!-- Main content -->
      <el-main class="main-content">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { ElMessageBox } from 'element-plus'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const collapsed = ref(false)

const titleMap = {
  '/dashboard': '控制台',
  '/tenants': '云账户管理',
  '/snipe': '抢机任务',
  '/ip-data': 'IP 数据',
  '/cloudflare': 'Cloudflare DNS',
  '/bills': '账单监控',
  '/notify': '通知配置',
  '/users': '用户管理',
  '/profile': '个人设置',
}
const currentTitle = computed(() => titleMap[route.path] || route.path)

async function handleLogout() {
  await ElMessageBox.confirm('确认退出登录？', '提示', { type: 'warning' })
  auth.logout()
  router.push('/login')
}
</script>

<style scoped>
.layout { height: 100vh; overflow: hidden; }
.sidebar {
  background: #1a1a2e;
  transition: width 0.3s;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.sidebar-logo {
  height: 60px;
  display: flex;
  align-items: center;
  padding: 0 20px;
  cursor: pointer;
  border-bottom: 1px solid rgba(255,255,255,0.08);
  gap: 10px;
}
.logo-text { color: #fff; font-size: 16px; font-weight: 600; white-space: nowrap; }
.sidebar-menu { border-right: none; flex: 1; }
.header {
  background: #fff;
  border-bottom: 1px solid #ebeef5;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  height: 60px;
  box-shadow: 0 1px 4px rgba(0,21,41,0.08);
}
.main-content {
  background: #f5f7fa;
  overflow-y: auto;
  padding: 24px;
}
</style>
