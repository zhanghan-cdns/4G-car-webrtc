<template>
  <div class="app">
    <WebRTCPlayer :src="srsUrl" />
  </div>
</template>

<script setup>
import { ref } from 'vue'
import WebRTCPlayer from './components/WebRTCPlayer.vue'

const srsUrl = ref(import.meta.env.VITE_SRS_URL || 'webrtc://your_server_ip:1985/live/cam01')
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
@media (max-width: 600px) {
  .app { padding: 20px 10px; }
}
</style>
