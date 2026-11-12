import { useKeyboardViewport } from '@/composables/useKeyboardViewport'

/**
 * 登录页的键盘 / 滚动适配。
 *
 * 返回 keyboardInset：键盘遮挡的高度，登录卡片据此增加底部留白，从而整体上移；
 * 挂载期间锁定页面滚动，卸载时恢复，避免 iOS 聚焦输入框时页面被拖动。
 */
export function useLoginViewport() {
  return useKeyboardViewport(() => true).keyboardInset
}
