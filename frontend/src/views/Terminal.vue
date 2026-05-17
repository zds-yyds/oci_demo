<template>
  <div class="flex flex-col h-[calc(100vh-7rem)]">
    <!-- Header -->
    <div class="flex items-center gap-3 pb-3">
      <button class="btn-ghost btn-sm" @click="$router.back()">← 返回</button>
      <span class="font-semibold text-surface-900 dark:text-white">SSH 终端 — {{ sshInfo.username }}@{{ sshInfo.host }}</span>
      <span :class="connected ? 'badge-success' : 'badge-danger'">{{ connected ? '已连接' : '未连接' }}</span>
    </div>
    <!-- Terminal container -->
    <div ref="terminalRef" class="flex-1 rounded-xl overflow-hidden bg-surface-900 p-2"></div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useToast } from '@/composables/useToast'
import { Terminal } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import '@xterm/xterm/css/xterm.css'

const router = useRouter()
const { error: showError } = useToast()
const terminalRef = ref<HTMLElement | null>(null)
const connected = ref(false)

const raw = sessionStorage.getItem('ssh_session')
const sshInfo = reactive(raw ? JSON.parse(raw) : { host: '', port: 22, username: 'root', authType: 'password', password: '', privateKey: '', tenantId: 0 })

let terminal: Terminal | null = null
let fitAddon: FitAddon | null = null
let ws: WebSocket | null = null
let resizeObserver: ResizeObserver | null = null

function getWsUrl() {
  const token = localStorage.getItem('token')
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const baseHost = window.location.host
  const params = new URLSearchParams({
    token: token || '',
    host: sshInfo.host,
    port: String(sshInfo.port),
    username: sshInfo.username,
    auth_type: sshInfo.authType,
    tenant_id: String(sshInfo.tenantId),
  })
  return `${protocol}//${baseHost}/api/terminal/ws?${params.toString()}`
}

function initTerminal() {
  terminal = new Terminal({
    cursorBlink: true,
    fontSize: 14,
    fontFamily: "'JetBrains Mono', 'Fira Code', 'Courier New', monospace",
    theme: { background: '#0f172a', foreground: '#e2e8f0', cursor: '#a78bfa', selectionBackground: '#334155' },
    scrollback: 5000,
  })

  fitAddon = new FitAddon()
  terminal.loadAddon(fitAddon)
  terminal.open(terminalRef.value!)
  nextTick(() => fitAddon!.fit())

  terminal.onData((data) => {
    if (ws && ws.readyState === WebSocket.OPEN) ws.send(data)
  })

  resizeObserver = new ResizeObserver(() => {
    if (fitAddon) {
      fitAddon.fit()
      if (ws && ws.readyState === WebSocket.OPEN) {
        const dims = fitAddon.proposeDimensions()
        if (dims) ws.send(`\x1b[RESIZE:${dims.cols},${dims.rows}]`)
      }
    }
  })
  resizeObserver.observe(terminalRef.value!)
}

function connectWs() {
  if (!sshInfo.host) { showError('缺少连接信息'); return }
  ws = new WebSocket(getWsUrl())
  ws.onopen = () => {
    connected.value = true
    ws!.send(JSON.stringify({ type: 'auth', auth_type: sshInfo.authType, password: sshInfo.password || '', private_key: sshInfo.privateKey || '' }))
  }
  ws.onmessage = (event) => terminal?.write(event.data)
  ws.onclose = () => { connected.value = false; terminal?.write('\r\n\x1b[33m连接已断开\x1b[0m\r\n') }
  ws.onerror = () => { connected.value = false; terminal?.write('\r\n\x1b[31mWebSocket 连接错误\x1b[0m\r\n') }
}

onMounted(() => {
  if (!sshInfo.host) { showError('缺少连接信息'); router.back(); return }
  initTerminal()
  connectWs()
  sessionStorage.removeItem('ssh_session')
})

onUnmounted(() => {
  ws?.close(); ws = null
  resizeObserver?.disconnect()
  terminal?.dispose()
})
</script>
