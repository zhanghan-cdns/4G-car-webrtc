<template>
  <div class="app">
    <h1>WebRTC 视频播放器</h1>
    <WebRTCPlayer src="webrtc://120.26.89.24:1985/live/cam01" />
  </div>
</template>

<script setup>
import WebRTCPlayer from './components/WebRTCPlayer.vue'
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: #1a1a2e;
  color: #eee;
  min-height: 100vh;
}
.app {
  max-width: 800px;
  margin: 0 auto;
  padding: 40px 20px;
}
h1 {
  text-align: center;
  margin-bottom: 30px;
  color: #e94560;
}
</style>
