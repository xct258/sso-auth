<script setup>
import { onMounted, onUnmounted } from 'vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  title: { type: String, default: '确认操作' },
  message: { type: String, default: '' },
  confirmText: { type: String, default: '确定' },
  cancelText: { type: String, default: '取消' },
  danger: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue', 'confirm'])

function close() {
  emit('update:modelValue', false)
}

function confirm() {
  emit('confirm')
  close()
}

function onKeydown(event) {
  if (event.key === 'Escape' && props.modelValue) close()
}

onMounted(() => window.addEventListener('keydown', onKeydown))
onUnmounted(() => window.removeEventListener('keydown', onKeydown))
</script>

<template>
  <Teleport to="body">
    <div v-if="modelValue" class="admin-modal-backdrop" @click.self="close">
      <div class="admin-modal confirm-modal" role="dialog" aria-modal="true">
        <h2>{{ title }}</h2>
        <p class="admin-muted">{{ message }}</p>
        <div class="confirm-actions">
          <button class="admin-btn ghost" type="button" @click="close">
            {{ cancelText }}
          </button>
          <button
            :class="['admin-btn', danger ? 'danger' : 'primary']"
            type="button"
            @click="confirm"
          >
            {{ confirmText }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>
