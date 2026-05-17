<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="confirmState.visible" class="fixed inset-0 z-[9500] flex items-center justify-center p-4">
        <div class="absolute inset-0 bg-black/50 backdrop-blur-sm" @click="handleCancel"></div>
        <div class="relative w-full max-w-md bg-white dark:bg-surface-800 rounded-2xl shadow-2xl border border-surface-200 dark:border-surface-700 p-6">
          <div class="flex items-start gap-4">
            <div class="shrink-0 w-10 h-10 rounded-full flex items-center justify-center" :class="iconBg">
              <svg v-if="confirmState.type === 'warning'" class="w-5 h-5 text-amber-600 dark:text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z" />
              </svg>
              <svg v-else-if="confirmState.type === 'error'" class="w-5 h-5 text-red-600 dark:text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z" />
              </svg>
              <svg v-else class="w-5 h-5 text-blue-600 dark:text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <div class="flex-1">
              <h3 class="text-lg font-semibold text-surface-900 dark:text-surface-100">{{ confirmState.title }}</h3>
              <p class="mt-2 text-sm text-surface-600 dark:text-surface-400 whitespace-pre-line">{{ confirmState.message }}</p>
            </div>
          </div>
          <div class="flex justify-end gap-3 mt-6">
            <button class="btn-secondary" @click="handleCancel">{{ confirmState.cancelText }}</button>
            <button
              :class="confirmState.type === 'error' ? 'btn-danger' : 'btn-primary'"
              @click="handleConfirm"
            >{{ confirmState.confirmText }}</button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useModal } from '@/composables/useModal'

const { confirmState, handleConfirm, handleCancel } = useModal()

const iconBg = computed(() => {
  switch (confirmState.value.type) {
    case 'warning': return 'bg-amber-100 dark:bg-amber-900/30'
    case 'error': return 'bg-red-100 dark:bg-red-900/30'
    default: return 'bg-blue-100 dark:bg-blue-900/30'
  }
})
</script>

<style scoped>
.modal-enter-active { animation: modalIn 0.2s ease; }
.modal-leave-active { animation: modalOut 0.15s ease; }
@keyframes modalIn { from { opacity: 0; transform: scale(0.95); } to { opacity: 1; transform: scale(1); } }
@keyframes modalOut { from { opacity: 1; transform: scale(1); } to { opacity: 0; transform: scale(0.95); } }
</style>
