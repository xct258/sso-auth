import { ref } from 'vue'

export const toasts = ref([])
let seed = 0

export function notify(message, type = 'success', duration = 2600) {
  const id = (seed += 1)
  toasts.value.push({ id, message, type })
  window.setTimeout(() => dismissToast(id), duration)
  return id
}

export function dismissToast(id) {
  toasts.value = toasts.value.filter((item) => item.id !== id)
}
