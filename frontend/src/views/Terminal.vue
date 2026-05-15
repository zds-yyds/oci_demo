<template>
  <div class="terminal-page">
    <div class="terminal-header">
      <el-button text @click="$router.back()"><el-icon><ArrowLeft /></el-icon> 返回</el-button>
      <span class="terminal-title">SSH 终端 — {{ sshInfo.username }}@{{ sshInfo.host }}</span>
      <el-tag :type="connected ? 'success' : 'danger'" size="small">
        {{ connected ? '已连接' : '未连接' }}
      </el-tag>
    </div>
    <div ref="terminalRef" class="terminal-container"></div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Terminal } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import '@xterm/xterm/css/xterm.css'

const router = useRouter()
const terminalRef = ref(null)
const connected = ref(false)

// 从 sessionStorage 读取 SSH 连接信息
const raw = sessionStorage.getItem('ssh_session')
const sshInfo = reactive(raw ? JSON.parse(raw) : { host: '', port: 22, username: 'root', authType: 'password', password: '', privateKey: '', tenantId: 0 })

let terminal = null
let fitAddon = null
let ws = null
let resizeObserver = null

function getWsUrl() {
  const token = localStorage.getItem('token')
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const baseHost = window.location.host
  const params = new URLSearchParams({
    token,
    host: sshInfo.host,
    port: sshInfo.port,
    username: sshInfo.username,
    auth_type: sshInfo.authType,
    tenant_id: sshInfo.tenantId,
  })
  return `${protocol}//${baseHost}/api/terminal/ws?${params.toString()}`
}

function initTerminal() {
  terminal = new Terminal({
    cursorBlink: true,
    fontSize: 14,
    fontFamily: "'JetBrains Mono', 'Fira Code', 'Courier New', monospace",
    theme: {
      background: '#1a1a2e',
      foreground: '#e0e0e0',
      cursor: '#00ff88',
      selectionBackground: '#3a3a5e',
    },
    scrollback: 5000,
  })

  fitAddon = new FitAddon()
  terminal.loadAddon(fitAddon)
  terminal.open(terminalRef.value)

  nextTick(() => {
    fitAddon.fit()
  })

  terminal.onData((data) => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(data)
    }
  })

  resizeObserver = new ResizeObserver(() => {
    if (fitAddon) {
      fitAddon.fit()
      if (ws && ws.readyState === WebSocket.OPEN) {
        const dims = fitAddon.proposeDimensions()
        if (dims) {
          ws.send(`\x1b[RESIZE:${dims.cols},${dims.rows}]`)
        }
      }
    }
  })
  resizeObserver.observe(terminalRef.value)
}

function connectWs() {
  if (!sshInfo.host) {
    ElMessage.error('缺少连接信息，请从实例页面发起连接')
    return
  }

  const url = getWsUrl()
  ws = new WebSocket(url)

  ws.onopen = () => {
    connected.value = true
    // 连接建立后发送认证信息（密码或私钥）
    const authPayload = JSON.stringify({
      type: 'auth',
      auth_type: sshInfo.authType,
      password: sshInfo.password || '',
      private_key: sshInfo.privateKey || '',
    })
    ws.send(authPayload)
  }

  ws.onmessage = (event) => {
    terminal.write(event.data)
  }

  ws.onclose = () => {
    connected.value = false
    terminal.write('\r\n\x1b[33m连接已断开\x1b[0m\r\n')
  }

  ws.onerror = () => {
    connected.value = false
    terminal.write('\r\n\x1b[31mWebSocket 连接错误\x1b[0m\r\n')
  }
}

onMounted(() => {
  if (!sshInfo.host) {
    ElMessage.error('缺少连接信息')
    router.back()
    return
  }
  initTerminal()
  connectWs()
  // 清除 sessionStorage 中的敏感信息
  sessionStorage.removeItem('ssh_session')
})

onUnmounted(() => {
  if (ws) {
    ws.close()
    ws = null
  }
  if (resizeObserver) {
    resizeObserver.disconnect()
  }
  if (terminal) {
    terminal.dispose()
  }
})
</script>

<style scoped>
.terminal-page {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 80px);
}
.terminal-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 0;
  margin-bottom: 8px;
}
.terminal-title {
  font-weight: 600;
  font-size: 15px;
}
.terminal-container {
  flex: 1;
  border-radius: 8px;
  overflow: hidden;
  background: #1a1a2e;
  padding: 8px;
}
</style>
