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

    <div class="controls">
      <div class="control-row">
        <label>协议：</label>
        <select v-model="mode">
          <option value="srs">SRS</option>
          <option value="whep">WHEP</option>
          <option value="zlmediakit">ZLMediaKit</option>
        </select>
        <label>API 端口：</label>
        <input v-model="apiPort" type="text" class="port-input" placeholder="1985" />
      </div>
      <div class="control-row">
        <label>地址：</label>
        <input v-model="inputUrl" type="text" @keyup.enter="connect" />
        <button @click="connect" :disabled="connecting">连接</button>
        <button v-if="connected" @click="disconnect" class="stop-btn">断开</button>
      </div>
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

const inputUrl = ref(props.src)
const mode = ref('srs')
const apiPort = ref('')
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
  // 只添加 video transceiver（该流没有音频）
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
  const port = apiPort.value || parsed.port || '1985'

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
  const port = apiPort.value || parsed.port || '8080'
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
  const port = apiPort.value || parsed.port || '8085'
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
    parsed = parseUrl(inputUrl.value)
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

    if (mode.value === 'srs') {
      await connectWithSrs(parsed)
    } else if (mode.value === 'whep') {
      await connectWithWhep(parsed)
    } else {
      await connectWithZlmediakit(parsed)
    }

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

onBeforeUnmount(() => disconnect())
</script>

<style scoped>
.player-wrapper {
  background: #16213e;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
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
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.control-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.control-row label {
  font-size: 13px;
  color: #888;
  white-space: nowrap;
}

.control-row select,
.control-row input {
  flex: 1;
  padding: 6px 10px;
  border: 1px solid #333;
  border-radius: 6px;
  background: #1a1a2e;
  color: #eee;
  font-size: 13px;
  outline: none;
}

.control-row select:focus,
.control-row input:focus {
  border-color: #e94560;
}

.control-row .port-input {
  flex: 0 0 70px;
}

.control-row button {
  padding: 6px 16px;
  border: none;
  border-radius: 6px;
  background: #e94560;
  color: #fff;
  cursor: pointer;
  font-size: 13px;
  transition: opacity 0.2s;
}

.control-row button:hover {
  opacity: 0.85;
}

.control-row button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.control-row .stop-btn {
  background: #555;
}

.control-row .stop-btn:hover {
  background: #777;
}
</style>
