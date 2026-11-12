import { onUnmounted, ref, watch } from 'vue'

/**
 * 移动端键盘 / 视口适配。
 *
 * keyboardInset 是键盘实际遮挡的高度：
 *   inset = layoutHeight - visualViewport.height - visualViewport.offsetTop
 *
 * 登录页把这个值加到容器底部留白上，让卡片在可视区域内保持居中。
 * 页面本身的滚动由 CSS 锁定，这里只负责测量，避免切换 overflow 干扰 iOS 键盘。
 */
const keyboardInset = ref(0)
let lockCount = 0
let viewport = null
let frame = 0

function measure() {
  if (!viewport) {
    keyboardInset.value = 0
    return
  }
  const layoutHeight = document.documentElement.clientHeight
  const raw = layoutHeight - viewport.height - viewport.offsetTop
  // 缩放时可视区域变小不是键盘造成的；小于 100px 视为地址栏/工具栏变化。
  const next = viewport.scale > 1.01 ? 0 : raw > 100 ? Math.round(raw) : 0
  if (next === keyboardInset.value) return
  keyboardInset.value = next
}

function scheduleMeasure() {
  cancelAnimationFrame(frame)
  frame = requestAnimationFrame(() => {
    frame = 0
    measure()
  })
}

function acquire() {
  if (lockCount === 0) {
    viewport = window.visualViewport
    if (viewport) {
      viewport.addEventListener('resize', scheduleMeasure)
      viewport.addEventListener('scroll', scheduleMeasure)
    }
    window.addEventListener('resize', scheduleMeasure)
    measure()
  }
  lockCount += 1
}

function release() {
  lockCount = Math.max(0, lockCount - 1)
  if (lockCount > 0) return

  cancelAnimationFrame(frame)
  frame = 0
  if (viewport) {
    viewport.removeEventListener('resize', scheduleMeasure)
    viewport.removeEventListener('scroll', scheduleMeasure)
  }
  window.removeEventListener('resize', scheduleMeasure)
  viewport = null
  keyboardInset.value = 0
}

/**
 * @param {() => boolean} active 是否启用键盘适配
 */
export function useKeyboardViewport(active = () => true) {
  let held = false

  watch(
    active,
    (value) => {
      if (value && !held) {
        held = true
        acquire()
      } else if (!value && held) {
        held = false
        release()
      }
    },
    { immediate: true },
  )

  onUnmounted(() => {
    if (held) {
      held = false
      release()
    }
  })

  return { keyboardInset }
}
