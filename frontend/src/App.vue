<template>
  <router-view />
  <Toast />
  <ConfirmModal />
</template>

<script setup lang="ts">
import Toast from '@/components/Toast.vue'
import ConfirmModal from '@/components/ConfirmModal.vue'
import { useThemeStore } from '@/stores/theme'

// Initialize theme
useThemeStore()
</script>
