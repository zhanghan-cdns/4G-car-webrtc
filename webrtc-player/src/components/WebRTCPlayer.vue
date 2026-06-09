<template>
  <div class="player">
    <div class="camera-bar">
      <div class="camera-bar-left">
        <svg class="camera-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
          <polyline points="14 2 14 8 20 8" />
          <line x1="12" y1="18" x2="12" y2="12" />
          <line x1="9" y1="15" x2="15" y2="15" />
        </svg>
        <span class="camera-name">摄像头 01</span>
        <span class="camera-url" :title="src">{{ src }}</span>
      </div>
      <div class="camera-bar-right">
        <div class="badge" :class="badgeClass">
          <span class="badge-dot"></span>
          <span class="badge-label">{{ badgeText }}</span>
        </div>
      </div>
    </div>

    <div class="video-section">
      <div class="video-wrapper" ref="container">
        <video ref="videoEl" autoplay playsinline muted></video>

        <div v-if="!connected && !error" class="overlay overlay-idle">
          <button class="play-btn" @click="connect" :disabled="connecting">
            <svg v-if="!connecting" viewBox="0 0 24 24" fill="currentColor" stroke="none">
              <path d="M8 5v14l11-7z" />
            </svg>
            <div v-else class="spinner"></div>
          </button>
          <p class="overlay-title">{{ connecting ? '正在建立连接...' : '点击开始播放' }}</p>
          <p v-if="!connecting" class="overlay-hint">WebRTC 视频流</p>
        </div>

        <div v-if="error" class="overlay overlay-error">
          <svg class="err-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
          <p class="err-text">{{ error }}</p>
          <button class="retry-btn" @click="retry">重试</button>
        </div>

        <div v-if="connected" class="video-toolbar">
          <button class="tool-btn" @click="toggleMute" :title="isMuted ? '取消静音' : '静音'">
            <svg v-if="!isMuted" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
              <path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07" />
            </svg>
            <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
              <line x1="23" y1="9" x2="17" y2="15" />
              <line x1="17" y1="9" x2="23" y2="15" />
            </svg>
          </button>
          <button class="tool-btn" @click="onTool('snapshot')" title="截图">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polygon points="23 7 16 12 23 17 23 7" />
              <rect x="1" y="5" width="15" height="14" rx="2" />
            </svg>
          </button>
          <button class="tool-btn" @click="onTool('fullscreen')" title="全屏">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3" />
            </svg>
          </button>
        </div>
      </div>
    </div>

    <div class="control-bar">
      <div class="control-left">
        <button
          v-if="!connected"
          @click="connect"
          :disabled="connecting"
          class="btn btn-primary"
        >
          <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polygon v-if="!connecting" points="5 3 19 12 5 21 5 3" />
          </svg>
          <span>{{ connecting ? '连接中...' : '开始播放' }}</span>
        </button>
        <button
          v-else
          @click="disconnect"
          class="btn btn-secondary"
        >
          <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <rect x="6" y="6" width="12" height="12" rx="2" />
          </svg>
          <span>断开</span>
        </button>
      </div>
      <div class="control-right">
        <span class="ptz-label">云台</span>
      </div>
    </div>

    <div class="ptz-section">
      <div class="dpad" role="group" aria-label="方向控制">
        <button class="dpad-btn up" @click="onWheel('up')" aria-label="上">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 5l7 10H5z"/>
          </svg>
        </button>
        <button class="dpad-btn right" @click="onWheel('right')" aria-label="右">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M19 12L9 5v14z"/>
          </svg>
        </button>
        <button class="dpad-btn down" @click="onWheel('down')" aria-label="下">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 19l-7-10h14z"/>
          </svg>
        </button>
        <button class="dpad-btn left" @click="onWheel('left')" aria-label="左">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M5 12l10-7v14z"/>
          </svg>
        </button>
        <div class="dpad-center" aria-hidden="true"></div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onBeforeUnmount } from 'vue'

const emit = defineEmits(['update:status'])

const props = defineProps({
  src: { type: String, default: '' }
})

const videoEl = ref(null)
const container = ref(null)

const statusText = ref('准备连接...')
const connected = ref(false)
const connecting = ref(false)
const error = ref(null)
const isMuted = ref(true)

let pc = null

const badgeClass = computed(() => {
  if (error.value) return 'badge-error'
  if (connected.value) return 'badge-online'
  if (connecting.value) return 'badge-connecting'
  return 'badge-offline'
})

const badgeText = computed(() => {
  if (error.value) return '连接失败'
  if (connected.value) return '在线'
  if (connecting.value) return '连接中'
  return '未连接'
})

function emitStatus(status) {
  emit('update:status', status)
}

watch([connected, connecting, error], () => {
  if (error.value) emitStatus('error')
  else if (connected.value) emitStatus('connected')
  else if (connecting.value) emitStatus('connecting')
  else emitStatus('idle')
}, { immediate: true })

function parseUrl(url) {
  const m = url.match(/^(webrtc|rtc|rtmp):\/\/([^:/]+)(?::(\d+))?(\/[^?#]*)?(\?[^#]*)?/)
  if (!m) throw new Error('URL 格式无效，示例: webrtc://host:port/app/stream')
  const path = m[4] || ''
  const parts = path.replace(/^\//, '').split('/')
  let app = 'live', stream = ''
  if (parts.length >= 2) {
    app = parts[0]
    stream = parts.slice(1).join('/')
  } else if (parts.length === 1) {
    stream = parts[0]
  }
  if (!stream) throw new Error('URL 中缺少 stream 名称')
  return {
    schema: m[1],
    host: m[2],
    port: m[3] || '',
    app,
    stream,
    query: m[5] || '',
    originalUrl: url
  }
}

function getIceServers() {
  return {
    iceServers: [
      { urls: 'stun:stun.l.google.com:19302' },
      { urls: 'stun:stun1.l.google.com:19302' }
    ]
  }
}

function createPeerConnection() {
  pc = new RTCPeerConnection(getIceServers())
  pc.addTransceiver('audio', { direction: 'recvonly' })
  pc.addTransceiver('video', { direction: 'recvonly' })

  pc.ontrack = (event) => {
    if (videoEl.value && event.track.kind === 'video') {
      videoEl.value.srcObject = event.streams[0] || new MediaStream([event.track])
      connected.value = true
      statusText.value = '已连接'
    }
  }

  pc.oniceconnectionstatechange = () => {
    const state = pc.iceConnectionState
    if (state === 'disconnected' || state === 'failed' || state === 'closed') {
      handleDisconnect()
    }
  }

  pc.onconnectionstatechange = () => {
    if (pc.connectionState === 'failed' || pc.connectionState === 'disconnected') {
      handleDisconnect()
    }
  }
}

async function connectWithSrs(parsed) {
  const scheme = window.location.protocol === 'https:' ? 'https:' : 'http:'
  const port = parsed.port || '1985'

  let apiUrl = `${scheme}//${parsed.host}:${port}/rtc/v1/play/`
  if (parsed.query) {
    const qs = parsed.query.startsWith('?') ? parsed.query.slice(1) : parsed.query
    apiUrl += '?' + qs
  }

  statusText.value = `正在请求 SDP (${apiUrl})...`

  const offer = await pc.createOffer()
  await pc.setLocalDescription(offer)

  const tid = Number(parseInt(new Date().getTime() * Math.random() * 100)).toString(16).slice(0, 7)

  const body = JSON.stringify({
    api: apiUrl,
    tid,
    streamurl: parsed.originalUrl,
    clientip: null,
    sdp: offer.sdp
  })

  const resp = await fetch(apiUrl, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body
  })

  if (!resp.ok) {
    const text = await resp.text().catch(() => '')
    throw new Error(`SRS API 请求失败 (${resp.status}): ${text.slice(0, 200)}`)
  }

  const data = await resp.json()
  if (data.code) {
    const detail = data.msg || (data.data && (data.data.msg || data.data.error)) || JSON.stringify(data)
    throw new Error(`SRS 错误 code=${data.code}: ${String(detail).slice(0, 300)}`)
  }
  if (!data.sdp) {
    throw new Error('SRS 未返回 SDP')
  }

  await pc.setRemoteDescription(new RTCSessionDescription({ type: 'answer', sdp: data.sdp }))
}

async function connectWithWhep(parsed) {
  const port = parsed.port || '8080'
  const url = `http://${parsed.host}:${port}/whep/${parsed.app}/${parsed.stream}`
  statusText.value = `正在请求 WHEP (${url})...`

  const resp = await fetch(url, { method: 'POST' })
  if (!resp.ok) throw new Error(`WHEP 请求失败: ${resp.status}`)

  const sdpOffer = await resp.text()
  await pc.setRemoteDescription({ type: 'offer', sdp: sdpOffer })

  const answer = await pc.createAnswer()
  await pc.setLocalDescription(answer)

  const location = resp.headers.get('Location')
  if (location) {
    const patchUrl = location.startsWith('http') ? location : `http://${parsed.host}:${port}${location}`
    const patchResp = await fetch(patchUrl, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/sdp' },
      body: answer.sdp
    })
    if (!patchResp.ok) throw new Error(`WHEP PATCH 失败: ${patchResp.status}`)
  }
}

async function connectWithZlmediakit(parsed) {
  const port = parsed.port || '8085'
  const url = `http://${parsed.host}:${port}/index/api/webrtc?app=${parsed.app}&stream=${parsed.stream}&type=play`
  statusText.value = `正在请求 ZLMediaKit (${url})...`

  const resp = await fetch(url, { method: 'POST' })
  if (!resp.ok) throw new Error(`ZLMediaKit 请求失败: ${resp.status}`)

  const data = await resp.json()
  if (data.code !== 0) throw new Error(`ZLMediaKit 错误: ${data.msg || data.code}`)

  const sdpOffer = data.data?.sdp || data.sdp
  if (!sdpOffer) throw new Error('未获取到 SDP')

  await pc.setRemoteDescription({ type: 'offer', sdp: sdpOffer })

  const answer = await pc.createAnswer()
  await pc.setLocalDescription(answer)

  const exchangeResp = await fetch(url + '&answer=' + encodeURIComponent(answer.sdp), {
    method: 'POST'
  })
  if (!exchangeResp.ok) throw new Error('SDP 交换失败')

  const exchangeData = await exchangeResp.json()
  if (exchangeData.code !== 0) throw new Error(`SDP 交换错误: ${exchangeData.msg}`)
}

async function connect() {
  disconnect()

  let parsed
  try {
    parsed = parseUrl(props.src)
  } catch (e) {
    error.value = e.message
    return
  }

  connecting.value = true
  connected.value = false
  error.value = null
  statusText.value = '连接中...'

  try {
    createPeerConnection()

    await connectWithSrs(parsed)

    statusText.value = '等待媒体流...'
  } catch (e) {
    console.error('WebRTC 连接失败:', e)
    error.value = `连接失败: ${e.message}`
    disconnect()
  } finally {
    connecting.value = false
  }
}

function handleDisconnect() {
  if (!connected.value) return
  connected.value = false
  statusText.value = '连接已断开'
  if (videoEl.value) videoEl.value.srcObject = null
}

function disconnect() {
  if (pc) {
    pc.close()
    pc = null
  }
  connected.value = false
  connecting.value = false
  error.value = null
  statusText.value = '已断开'
  if (videoEl.value) videoEl.value.srcObject = null
}

function retry() {
  error.value = null
  connect()
}

function toggleMute() {
  isMuted.value = !isMuted.value
  if (videoEl.value) {
    videoEl.value.muted = isMuted.value
  }
}

function onWheel(dir) {
  console.log('方向盘:', dir)
}

function onTool(action) {
  console.log('工具栏:', action)
}

onBeforeUnmount(() => disconnect())
</script>

<style scoped>
.player {
  max-width: 960px;
  margin: 0 auto;
  width: 100%;
}

/* ===== Camera Bar ===== */
.camera-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius) var(--radius) 0 0;
  gap: 12px;
}

.camera-bar-left {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.camera-icon {
  width: 18px;
  height: 18px;
  color: var(--accent);
  flex-shrink: 0;
}

.camera-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
}

.camera-url {
  font-size: 12px;
  color: var(--text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  display: none;
}

@media (min-width: 640px) {
  .camera-url { display: inline; }
}

.camera-bar-right {
  display: flex;
  align-items: center;
  flex-shrink: 0;
}

.badge {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: var(--radius-full);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.02em;
}

.badge-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  transition: background 0.3s, box-shadow 0.3s;
}

.badge-offline {
  background: rgba(0, 0, 0, 0.05);
  color: var(--text-muted);
}
.badge-offline .badge-dot { background: var(--text-muted); }

.badge-connecting {
  background: rgba(0, 0, 0, 0.08);
  color: var(--warning);
}
.badge-connecting .badge-dot {
  background: var(--warning);
  animation: pulse-dot 1s ease-in-out infinite;
}

.badge-online {
  background: rgba(0, 0, 0, 0.1);
  color: var(--success);
}
.badge-online .badge-dot {
  background: var(--success);
}

.badge-error {
  background: rgba(0, 0, 0, 0.12);
  color: var(--error);
}
.badge-error .badge-dot {
  background: var(--error);
}

@keyframes pulse-dot {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

/* ===== Video Section ===== */
.video-section {
  border-left: 1px solid var(--border);
  border-right: 1px solid var(--border);
}

.video-wrapper {
  position: relative;
  width: 100%;
  aspect-ratio: 16 / 9;
  background: #000;
  overflow: hidden;
}

.video-wrapper video {
  width: 100%;
  height: 100%;
  display: block;
  object-fit: contain;
}

.overlay {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 14px;
  transition: opacity 0.3s ease;
}

.overlay-idle {
  background: linear-gradient(135deg, rgba(0, 0, 0, 0.75) 0%, rgba(0, 0, 0, 0.55) 100%);
}

.overlay-error {
  background: rgba(0, 0, 0, 0.8);
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
}

.play-btn {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  border: 2px solid rgba(255, 255, 255, 0.25);
  background: rgba(255, 255, 255, 0.08);
  color: #fff;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.25s ease;
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
}

.play-btn:hover:not(:disabled) {
  background: var(--accent);
  border-color: var(--accent);
  transform: scale(1.06);
}

.play-btn:active:not(:disabled) {
  transform: scale(0.95);
}

.play-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.play-btn svg {
  width: 28px;
  height: 28px;
  margin-left: 3px;
}

.spinner {
  width: 28px;
  height: 28px;
  border: 2px solid rgba(255, 255, 255, 0.15);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.overlay-title {
  font-size: 15px;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.9);
}

.overlay-hint {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.45);
  font-weight: 400;
}

.err-icon {
  width: 36px;
  height: 36px;
  color: var(--error);
  opacity: 0.8;
}

.err-text {
  font-size: 13px;
  color: #fca5a5;
  text-align: center;
  max-width: 80%;
  word-break: break-all;
  line-height: 1.5;
}

.retry-btn {
  padding: 8px 22px;
  border: 1px solid var(--accent);
  background: var(--accent-subtle);
  color: var(--accent);
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  font-family: var(--font-family);
  transition: all 0.2s ease;
}

.retry-btn:hover {
  background: var(--accent);
  color: #fff;
}

.video-toolbar {
  position: absolute;
  bottom: 12px;
  right: 12px;
  display: flex;
  gap: 6px;
}

.tool-btn {
  width: 34px;
  height: 34px;
  border-radius: var(--radius-sm);
  border: none;
  background: rgba(0, 0, 0, 0.55);
  color: rgba(255, 255, 255, 0.7);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
}

.tool-btn:hover {
  background: var(--accent);
  color: #fff;
}

.tool-btn svg {
  width: 16px;
  height: 16px;
}

/* ===== Control Bar ===== */
.control-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-top: none;
  gap: 12px;
}

.control-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 20px;
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: 14px;
  font-weight: 600;
  font-family: var(--font-family);
  transition: all 0.2s ease;
}

.btn:active {
  transform: scale(0.97);
}

.btn-icon {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
}

.btn-primary {
  background: var(--accent);
  color: #fff;
}

.btn-primary:hover:not(:disabled) {
  background: var(--accent-hover);
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-secondary {
  background: transparent;
  color: var(--text-secondary);
  border: 1px solid var(--border);
}

.btn-secondary:hover {
  background: rgba(248, 81, 73, 0.08);
  color: var(--error);
  border-color: rgba(248, 81, 73, 0.3);
}

.control-right {
  display: flex;
  align-items: center;
  flex-shrink: 0;
}

.ptz-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-muted);
  letter-spacing: 0.05em;
}

/* ===== PTZ Section ===== */
.ptz-section {
  display: flex;
  justify-content: center;
  padding: 20px 16px 16px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-top: none;
  border-radius: 0 0 var(--radius) var(--radius);
}

.dpad {
  display: grid;
  grid-template-columns: 52px 52px 52px;
  grid-template-rows: 52px 52px 52px;
  gap: 4px;
  align-items: center;
  justify-items: center;
}

.dpad-btn {
  width: 48px;
  height: 48px;
  padding: 0;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--bg-secondary);
  color: var(--text-muted);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  user-select: none;
  -webkit-tap-highlight-color: transparent;
  transition: all 0.2s ease;
}

.dpad-btn svg {
  width: 18px;
  height: 18px;
  stroke: currentColor;
  transition: transform 0.2s ease;
}

.dpad-btn:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
  border-color: rgba(255, 255, 255, 0.08);
  transform: translateY(-1px);
}

.dpad-btn:hover svg {
  transform: scale(1.1);
}

.dpad-btn:active {
  background: var(--accent);
  color: #fff;
  border-color: var(--accent);
  transform: translateY(0);
}

.dpad-btn:active svg {
  transform: scale(0.9);
}

.dpad-btn.up {
  grid-column: 2;
  grid-row: 1;
}

.dpad-btn.right {
  grid-column: 3;
  grid-row: 2;
}

.dpad-btn.down {
  grid-column: 2;
  grid-row: 3;
}

.dpad-btn.left {
  grid-column: 1;
  grid-row: 2;
}

.dpad-center {
  grid-column: 2;
  grid-row: 2;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: 1px solid var(--border);
  background: transparent;
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: none;
}

.dpad-center::after {
  content: '';
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--accent);
}

@media (max-width: 600px) {
  .camera-bar { padding: 10px 12px; }
  .camera-name { font-size: 13px; }
  .camera-icon { width: 16px; height: 16px; }
  .badge { font-size: 10px; padding: 3px 8px; }
  .badge-dot { width: 5px; height: 5px; }

  .play-btn { width: 54px; height: 54px; }
  .play-btn svg { width: 24px; height: 24px; }
  .spinner { width: 24px; height: 24px; }
  .overlay-title { font-size: 14px; }
  .overlay-hint { font-size: 12px; }

  .control-bar { padding: 10px 12px; }
  .btn { padding: 8px 16px; font-size: 13px; }
  .btn-icon { width: 14px; height: 14px; }
  .ptz-label { font-size: 11px; }

  .ptz-section { padding: 16px 12px 12px; }
  .dpad { grid-template-columns: 46px 46px 46px; grid-template-rows: 46px 46px 46px; gap: 3px; }
  .dpad-btn { width: 42px; height: 42px; border-radius: 8px; }
  .dpad-btn svg { width: 16px; height: 16px; }
  .dpad-center { width: 30px; height: 30px; }
  .dpad-center::after { width: 4px; height: 4px; }
}
</style>
