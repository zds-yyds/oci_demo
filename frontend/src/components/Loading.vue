<template>
  <div v-if="loading" class="flex items-center justify-center py-12">
    <div class="flex flex-col items-center gap-3">
      <div class="w-8 h-8 border-3 border-primary-200 dark:border-primary-800 border-t-primary-600 dark:border-t-primary-400 rounded-full animate-spin"></div>
      <span v-if="text" class="text-sm text-surface-500">{{ text }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  loading: boolean
  text?: string
}>()
</script>
