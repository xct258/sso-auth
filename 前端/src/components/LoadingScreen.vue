<script setup>
import { computed } from 'vue'

const props = defineProps({
  progress: { type: Object, required: true },
  siteName: { type: String, default: '统一登录' },
  failed: { type: Boolean, default: false },
  timedOut: { type: Boolean, default: false },
})

defineEmits(['retry'])

const barKnown = computed(() => props.progress.known)
const percent = computed(() => props.progress.percent)

const phaseText = computed(() => {
  if (props.failed) return '壁纸加载失败，请重新加载'
  if (props.timedOut) return '壁纸加载较慢，仍在继续…'
  if (props.progress.phase === 'decoding') return '正在解码图片…'
  return props.progress.known ? '正在下载壁纸…' : '正在加载壁纸…'
})

const sizeText = computed(() => {
  if (props.failed) return ''
  const { loaded, total, known } = props.progress
  if (known) {
    const remain = Math.max(0, total - loaded)
    return `${formatBytes(loaded)} / ${formatBytes(total)} · 剩余 ${formatBytes(remain)}`
  }
  return loaded > 0 ? `已加载 ${formatBytes(loaded)}` : ''
})

function formatBytes(bytes) {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let value = bytes
  let i = 0
  while (value >= 1024 && i < units.length - 1) {
    value /= 1024
    i += 1
  }
  const digits = value >= 10 || i === 0 ? 0 : 1
  return `${value.toFixed(digits)} ${units[i]}`
}
</script>

<template>
  <div
    class="loading-screen"
    role="status"
    aria-live="polite"
    aria-label="正在加载"
  >
    <div class="glow glow-a" />
    <div class="glow glow-b" />

    <div class="content">
      <div class="ring-wrap">
        <div class="ring-track" />
        <div class="ring-spin" />
        <div class="ring-center">
          <span v-if="barKnown" class="percent">{{ percent }}%</span>
          <span v-else class="core" />
        </div>
      </div>

      <div class="brand">
        <span>{{ siteName }}</span>
        <span class="brand-dot" />
      </div>

      <div class="subline">
        <span>载入登录中心</span>
        <span class="dots" aria-hidden="true"><span>.</span><span>.</span><span>.</span></span>
      </div>

      <div class="bar">
        <div
          v-if="barKnown"
          class="bar-fill"
          :style="{ width: `${percent}%` }"
        />
        <div v-else class="bar-run" />
      </div>

      <p class="phase">{{ phaseText }}</p>
      <p class="size">{{ sizeText }}</p>

      <div class="actions">
        <button
          type="button"
          class="retry"
          :class="{ invisible: !(failed || timedOut) }"
          @click="$emit('retry')"
        >
          重新加载
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.loading-screen {
  position: fixed;
  inset: 0;
  z-index: 50;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  background: rgba(2, 6, 23, 0.72);
}

.glow {
  position: absolute;
  border-radius: 999px;
  filter: blur(64px);
  transition: background 0.5s ease;
  pointer-events: none;
}

.glow-a {
  top: -128px;
  left: -96px;
  width: 320px;
  height: 320px;
  background: rgba(var(--wp-accent-rgb, 99, 102, 241), 0.2);
}

.glow-b {
  right: -96px;
  bottom: -144px;
  width: 384px;
  height: 384px;
  background: rgba(var(--wp-accent-rgb, 99, 102, 241), 0.12);
}

.content {
  position: relative;
  display: flex;
  width: 100%;
  max-width: 320px;
  flex-direction: column;
  align-items: center;
  padding: 0 24px;
  text-align: center;
}

.ring-wrap {
  position: relative;
  width: 64px;
  height: 64px;
  margin-bottom: 28px;
}

.ring-track,
.ring-spin {
  position: absolute;
  inset: 0;
  border-radius: 999px;
}

.ring-track {
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.ring-spin {
  border: 2px solid transparent;
  border-top-color: var(--wp-accent, #6366f1);
  animation: spin 1s linear infinite;
}

.ring-center {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.percent {
  color: var(--wp-accent, #6366f1);
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 10px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.core {
  width: 8px;
  height: 8px;
  border-radius: 2px;
  background: var(--wp-accent, #6366f1);
}

.brand {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: #e2e8f0;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.5em;
}

.brand-dot {
  width: 6px;
  height: 6px;
  border-radius: 2px;
  background: var(--wp-accent, #6366f1);
}

.subline {
  display: flex;
  align-items: baseline;
  gap: 6px;
  margin-top: 8px;
  color: #64748b;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 10px;
  letter-spacing: 0.25em;
}

.dots span {
  animation: blink 1.4s infinite both;
}
.dots span:nth-child(2) { animation-delay: 0.2s; }
.dots span:nth-child(3) { animation-delay: 0.4s; }

.bar {
  position: relative;
  width: 176px;
  height: 3px;
  margin-top: 24px;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.1);
}

.bar-fill {
  position: absolute;
  top: 0;
  bottom: 0;
  left: 0;
  border-radius: 999px;
  background: var(--wp-accent, #6366f1);
  transition: width 0.15s linear;
}

.bar-run {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 33%;
  border-radius: 999px;
  background: var(--wp-accent, #6366f1);
  animation: run 1.2s ease-in-out infinite;
}

.phase {
  margin: 12px 0 0;
  color: #94a3b8;
  font-size: 10px;
  letter-spacing: 0.06em;
}

.size {
  height: 16px;
  margin: 4px 0 0;
  color: #64748b;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 10px;
  font-variant-numeric: tabular-nums;
}

.actions {
  display: flex;
  justify-content: center;
  height: 48px;
  margin-top: 12px;
}

.retry {
  padding: 8px 18px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 9px;
  background: rgba(255, 255, 255, 0.06);
  color: #e2e8f0;
  font-size: 12px;
  cursor: pointer;
  transition: background 0.18s ease, border-color 0.18s ease;
}

.retry.invisible {
  visibility: hidden;
  pointer-events: none;
}

.retry:hover {
  background: rgba(255, 255, 255, 0.12);
  border-color: rgba(255, 255, 255, 0.2);
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

@keyframes run {
  0% { transform: translateX(-120%); }
  100% { transform: translateX(360%); }
}

@keyframes blink {
  0%, 80%, 100% { opacity: 0.25; }
  40% { opacity: 1; }
}
</style>
