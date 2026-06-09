<template>
  <div class="page">
    <header class="topbar">
      <div class="topbar-inner">
        <div class="topbar-left">
          <div class="logo">
            <div class="logo-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14 2 14 8 20 8" />
                <line x1="16" y1="13" x2="8" y2="13" />
                <line x1="12" y1="9" x2="12" y2="17" />
              </svg>
            </div>
            <div class="logo-text">
              <span class="logo-title">WebRTC Player</span>
              <span class="logo-badge">v1.0</span>
            </div>
          </div>
        </div>
        <div class="topbar-right"></div>
      </div>
    </header>

    <div class="app">
      <main class="main">
        <WebRTCPlayer
          :src="srsUrl"
        />
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import WebRTCPlayer from './components/WebRTCPlayer.vue'

const srsUrl = ref(import.meta.env.VITE_SRS_URL || 'webrtc://your_server_ip:1985/live/cam01')
</script>

<style>
*,
*::before,
*::after {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

:root {
  --bg-primary: #c0c0c0;
  --bg-secondary: #1a1a1a;
  --bg-card: #1a1a1a;
  --bg-hover: #2a2a2a;
  --accent: #000000;
  --accent-hover: #333333;
  --accent-glow: rgba(0, 0, 0, 0.25);
  --accent-subtle: rgba(0, 0, 0, 0.06);
  --text-primary: #f5f5f5;
  --text-secondary: #a3a3a3;
  --text-muted: #666666;
  --border: #333333;
  --radius: 12px;
  --radius-sm: 8px;
  --radius-full: 9999px;
  --shadow: 0 4px 24px rgba(0, 0, 0, 0.35);
  --shadow-sm: 0 1px 3px rgba(0, 0, 0, 0.08);
  --success: #2e2e2e;
  --success-glow: rgba(0, 0, 0, 0.25);
  --warning: #555555;
  --warning-glow: rgba(0, 0, 0, 0.2);
  --error: #000000;
  --error-glow: rgba(0, 0, 0, 0.3);
  --font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

html {
  font-family: var(--font-family);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

body {
  background: var(--bg-primary);
  color: #1a1a1a;
  min-height: 100vh;
  min-height: 100dvh;
}

.app {
  max-width: 1400px;
  margin: 0 auto;
  padding: 0 20px;
  min-height: 100vh;
  min-height: 100dvh;
  display: flex;
  flex-direction: column;
}

.topbar {
  width: 100%;
  background: #ffffff;
  border-bottom: 1px solid #a0a0a0;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
  flex-shrink: 0;
}

.topbar-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  max-width: 1400px;
  margin: 0 auto;
  padding: 14px 20px;
}

.topbar-left {
  display: flex;
  align-items: center;
}

.logo {
  display: flex;
  align-items: center;
  gap: 12px;
}

.logo-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: #000000;
  color: #fff;
  flex-shrink: 0;
}

.logo-icon svg {
  width: 18px;
  height: 18px;
}

.logo-text {
  display: flex;
  align-items: baseline;
  gap: 10px;
}

.logo-title {
  font-size: 17px;
  font-weight: 700;
  color: #000000;
  letter-spacing: -0.02em;
}

.logo-badge {
  font-size: 11px;
  font-weight: 500;
  color: #999999;
  background: #f0f0f0;
  padding: 1px 8px;
  border-radius: 6px;
  letter-spacing: 0.01em;
}

.topbar-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.status-badge {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 5px 12px;
  border-radius: var(--radius-full);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.01em;
}

.status-badge-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  transition: background 0.3s, box-shadow 0.3s;
}

.status-badge.idle {
  background: rgba(0, 0, 0, 0.05);
  color: var(--text-muted);
}
.status-badge.idle .status-badge-dot {
  background: var(--text-muted);
}

.status-badge.connecting {
  background: rgba(0, 0, 0, 0.08);
  color: var(--warning);
}
.status-badge.connecting .status-badge-dot {
  background: var(--warning);
  box-shadow: 0 0 6px var(--warning-glow);
  animation: pulse-dot 1s ease-in-out infinite;
}

.status-badge.connected {
  background: rgba(0, 0, 0, 0.1);
  color: var(--success);
}
.status-badge.connected .status-badge-dot {
  background: var(--success);
  box-shadow: 0 0 6px var(--success-glow);
}

.status-badge.error {
  background: rgba(0, 0, 0, 0.12);
  color: var(--error);
}
.status-badge.error .status-badge-dot {
  background: var(--error);
  box-shadow: 0 0 6px var(--error-glow);
}

@keyframes pulse-dot {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

.main {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 24px 0 40px;
}

@media (max-width: 768px) {
  .app { padding: 0 12px; }
  .topbar-inner { padding: 12px; }
  .logo-icon { width: 32px; height: 32px; }
  .logo-icon svg { width: 16px; height: 16px; }
  .logo-title { font-size: 15px; }
  .logo-badge { display: none; }
  .main { padding: 16px 0 24px; }
}
</style>
