<template>
  <div class="player-wrapper">
    <div class="video-container" ref="container">
      <video ref="videoEl" autoplay playsinline muted controls></video>

      <div v-if="!connected && !error" class="overlay">
        <div class="spinner"></div>
        <p>{{ statusText }}</p>
      </div>

      <div v-if="error" class="overlay error-overlay">
        <p class="error-text">{{ error }}</p>
        <button class="retry-btn" @click="retry">重试</button>
      </div>
    </div>
  </div>

  <div class="controls">
    <button v-if="!connected" @click="connect" :disabled="connecting" class="connect-btn">{{ connecting ? '连接中...' : '连接' }}</button>
    <button v-else @click="disconnect" class="stop-btn">断开</button>
  </div>

  <div class="wheel-wrapper">
    <div class="wheel" role="group" aria-label="方向控制">
      <button class="wheel-btn up" @click="onWheel('up')" aria-label="上">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 6l8 10H4z"/></svg>
      </button>
      <button class="wheel-btn right" @click="onWheel('right')" aria-label="右">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M18 12l-10 8V4z"/></svg>
      </button>
      <button class="wheel-btn down" @click="onWheel('down')" aria-label="下">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 18L4 8h16z"/></svg>
      </button>
      <button class="wheel-btn left" @click="onWheel('left')" aria-label="左">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 12l10-8v16z"/></svg>
      </button>
      <div class="wheel-center" aria-hidden="true"></div>
    </div>
  </div>
</template>

<script setup>
import { ref, onBeforeUnmount } from 'vue'

const props = defineProps({
  src: { type: String, default: '' }
})

const videoEl = ref(null)
const container = ref(null)

const statusText = ref('准备连接...')
const connected = ref(false)
const connecting = ref(false)
const error = ref(null)

let pc = null

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

function onWheel(dir) {
  // TODO: 控制指令发送
  console.log('方向盘:', dir)
}

onBeforeUnmount(() => disconnect())
</script>

<style scoped>
.player-wrapper {
  background: #16213e;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
  max-width: 400px;
  margin: 0 auto;
}

.controls {
  padding: 20px 0 4px;
  max-width: 400px;
  margin: 0 auto;
}

@media (min-width: 768px) {
  .player-wrapper { max-width: 1200px; }
  .controls { max-width: 1200px; }
}

.video-container {
  position: relative;
  width: 100%;
  aspect-ratio: 16 / 9;
  background: #000;
}

.video-container video {
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
  background: rgba(0, 0, 0, 0.6);
  gap: 16px;
}

.error-overlay {
  background: rgba(0, 0, 0, 0.75);
}

.spinner {
  width: 40px;
  height: 40px;
  border: 3px solid rgba(233, 69, 96, 0.3);
  border-top-color: #e94560;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.error-text {
  color: #e94560;
  font-size: 14px;
  text-align: center;
  max-width: 80%;
  word-break: break-all;
}

.retry-btn {
  padding: 8px 24px;
  border: 1px solid #e94560;
  background: transparent;
  color: #e94560;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.2s;
}

.retry-btn:hover {
  background: #e94560;
  color: #fff;
}

.controls {
  padding: 20px 0 4px;
  max-width: 400px;
  margin: 0 auto;
}

.connect-btn, .stop-btn {
  width: 100%;
  padding: 12px;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-size: 16px;
  font-weight: 600;
  transition: opacity 0.2s;
}

.wheel {
  position: relative;
  width: 200px;
  height: 200px;
  margin: 24px auto 16px;
}

.wheel-wrapper {
  margin-top: 20px;
  padding: 24px 16px;
  display: flex;
  justify-content: center;
  background: transparent;
}

.wheel {
  position: relative;
  width: 180px;
  height: 180px;
  border-radius: 50%;
  background:
    radial-gradient(circle at 30% 28%, #2d2d52 0%, #181830 55%, #0d0d1c 100%);
  box-shadow:
    inset 0 2px 6px rgba(255, 255, 255, 0.06),
    inset 0 -3px 10px rgba(0, 0, 0, 0.55),
    0 10px 24px rgba(0, 0, 0, 0.45),
    0 0 0 1px rgba(255, 255, 255, 0.04);
}

.wheel-btn {
  position: absolute;
  width: 58px;
  height: 58px;
  padding: 0;
  border: none;
  background: linear-gradient(150deg, #32325a 0%, #1a1a30 100%);
  color: #c8c8e0;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s ease, color 0.15s ease, box-shadow 0.15s ease;
  user-select: none;
  -webkit-tap-highlight-color: transparent;
  box-shadow:
    0 3px 6px rgba(0, 0, 0, 0.5),
    inset 0 1px 1px rgba(255, 255, 255, 0.12),
    inset 0 -1px 2px rgba(0, 0, 0, 0.4);
}

.wheel-btn svg {
  width: 22px;
  height: 22px;
  fill: currentColor;
  transition: transform 0.15s ease, filter 0.15s ease;
}

.wheel-btn:hover {
  color: #fff;
}

.wheel-btn:hover svg {
  transform: scale(1.08);
  filter: drop-shadow(0 0 6px rgba(233, 69, 96, 0.55));
}

.wheel-btn:active {
  background: linear-gradient(150deg, #e94560 0%, #b8324a 100%);
  color: #fff;
  box-shadow:
    inset 0 3px 6px rgba(0, 0, 0, 0.45),
    0 0 14px rgba(233, 69, 96, 0.5);
}

.wheel-btn:active svg {
  transform: scale(0.9);
  filter: none;
}

.wheel-btn.up {
  top: 6px;
  left: 50%;
  transform: translateX(-50%);
  border-radius: 50% 50% 10px 10px;
}

.wheel-btn.down {
  bottom: 6px;
  left: 50%;
  transform: translateX(-50%);
  border-radius: 10px 10px 50% 50%;
}

.wheel-btn.left {
  left: 6px;
  top: 50%;
  transform: translateY(-50%);
  border-radius: 50% 10px 10px 50%;
}

.wheel-btn.right {
  right: 6px;
  top: 50%;
  transform: translateY(-50%);
  border-radius: 10px 50% 50% 10px;
}

.wheel-center {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 38px;
  height: 38px;
  border-radius: 50%;
  background: radial-gradient(circle at 35% 35%, #20203c 0%, #08081a 100%);
  transform: translate(-50%, -50%);
  box-shadow:
    inset 0 2px 4px rgba(0, 0, 0, 0.8),
    inset 0 -1px 2px rgba(255, 255, 255, 0.05),
    0 0 0 1px rgba(233, 69, 96, 0.18);
  pointer-events: none;
}

.wheel-center::after {
  content: '';
  position: absolute;
  top: 50%;
  left: 50%;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #e94560;
  transform: translate(-50%, -50%);
  box-shadow: 0 0 8px rgba(233, 69, 96, 0.9);
}

.connect-btn, .stop-btn {
  width: 100%;
  padding: 12px;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-size: 16px;
  font-weight: 600;
  transition: opacity 0.2s;
}

.connect-btn {
  background: #e94560;
  color: #fff;
}

.connect-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.stop-btn {
  background: #555;
  color: #fff;
}

@media (max-width: 600px) {
  .controls { padding: 12px; }
  .connect-btn, .stop-btn { padding: 14px; font-size: 17px; }
  .retry-btn { padding: 10px 24px; font-size: 15px; }
  .error-text { font-size: 13px; }
  .wheel { width: 160px; height: 160px; }
  .wheel-btn { width: 52px; height: 52px; }
  .wheel-btn svg { width: 20px; height: 20px; }
  .wheel-center { width: 34px; height: 34px; }
}
</style>
