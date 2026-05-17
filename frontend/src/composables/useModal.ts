import { ref } from 'vue'

const confirmState = ref({
  visible: false,
  title: '',
  message: '',
  type: 'warning' as 'warning' | 'error' | 'info',
  confirmText: '确认',
  cancelText: '取消',
  resolve: null as ((value: boolean) => void) | null,
})

export function useModal() {
  function confirm(message: string, title = '提示', options?: {
    type?: 'warning' | 'error' | 'info'
    confirmText?: string
    cancelText?: string
  }): Promise<boolean> {
    return new Promise((resolve) => {
      confirmState.value = {
        visible: true,
        title,
        message,
        type: options?.type || 'warning',
        confirmText: options?.confirmText || '确认',
        cancelText: options?.cancelText || '取消',
        resolve,
      }
    })
  }

  function handleConfirm() {
    confirmState.value.resolve?.(true)
    confirmState.value.visible = false
  }

  function handleCancel() {
    confirmState.value.resolve?.(false)
    confirmState.value.visible = false
  }

  return { confirmState, confirm, handleConfirm, handleCancel }
}
