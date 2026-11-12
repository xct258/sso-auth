<script setup>
import { dismissToast, toasts } from '@/composables/useToast'
</script>

<template>
  <Teleport to="body">
    <div class="toast-host" aria-live="polite" aria-atomic="false">
      <TransitionGroup name="toast">
        <button
          v-for="item in toasts"
          :key="item.id"
          type="button"
          :class="['toast-item', item.type]"
          @click="dismissToast(item.id)"
        >
          {{ item.message }}
        </button>
      </TransitionGroup>
    </div>
  </Teleport>
</template>
