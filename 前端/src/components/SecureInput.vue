<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'

const props = defineProps({
  modelValue: { type: String, default: '' },
  visible: { type: Boolean, default: false },
  autofocus: { type: Boolean, default: false },
  placeholder: { type: String, default: '访问密码' },
})

const emit = defineEmits([
  'update:modelValue',
  'submit',
  'toggle-visibility',
  'keyboard-change',
  'paste-error',
  'change',
])

const isFinePointer = window.matchMedia?.('(pointer: fine)').matches ?? true
const displayRef = ref(null)
const codeRef = ref(null)
const keypadRef = ref(null)
const displayFocused = ref(false)
const keypadOpen = ref(false)
const mode = ref('abc')
const caps = ref(false)
const caretIndex = ref(0)
const selStart = ref(0)
const selEnd = ref(0)
const hasSelection = computed(() => selEnd.value > selStart.value)
const showCaret = computed(() => (isFinePointer ? displayFocused.value : keypadOpen.value))
let resizeObserver = null
let lastTapAt = 0

const displayChars = computed(() => props.modelValue.split(''))

const value = computed({
  get: () => props.modelValue,
  set: (next) => emit('update:modelValue', next),
})

const letterRow1 = ['q', 'w', 'e', 'r', 't', 'y', 'u', 'i', 'o', 'p']
const letterRow2 = ['a', 's', 'd', 'f', 'g', 'h', 'j', 'k', 'l']
const letterRow3 = ['z', 'x', 'c', 'v', 'b', 'n', 'm']
const digitRow = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '0']

const shiftRow1 = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '0']
const shiftRow2 = ['@', '#', '$', '_', '&', '-', '+', '(', ')', '/']
const shiftRow3 = ['*', '"', "'", ':', ';', '!', '?']

function label(key) {
  return mode.value === 'abc' && caps.value && /[a-z]/.test(key) ? key.toUpperCase() : key
}

function clearSelection() {
  selStart.value = 0
  selEnd.value = 0
}

function isSelected(index) {
  return index >= selStart.value && index < selEnd.value
}

function selectAll() {
  if (!value.value) return
  selStart.value = 0
  selEnd.value = value.value.length
  caretIndex.value = value.value.length
}

function replaceSelection(text) {
  const start = selStart.value
  const end = selEnd.value
  value.value = value.value.slice(0, start) + text + value.value.slice(end)
  caretIndex.value = start + text.length
  clearSelection()
  emit('change')
}

function press(key) {
  if (!key) return
  navigator.vibrate?.(8)
  const char =
    mode.value === 'abc' && caps.value && /[a-z]/.test(key) ? key.toUpperCase() : key

  if (hasSelection.value) {
    replaceSelection(char)
    return
  }

  value.value =
    value.value.slice(0, caretIndex.value) + char + value.value.slice(caretIndex.value)
  caretIndex.value += char.length
  emit('change')
}

function backspace() {
  navigator.vibrate?.(8)

  if (hasSelection.value) {
    replaceSelection('')
    return
  }
  if (caretIndex.value <= 0) return
  value.value =
    value.value.slice(0, caretIndex.value - 1) + value.value.slice(caretIndex.value)
  caretIndex.value -= 1
  emit('change')
}

function deleteForward() {
  if (hasSelection.value) {
    replaceSelection('')
    return
  }
  if (caretIndex.value >= value.value.length) return
  value.value =
    value.value.slice(0, caretIndex.value) + value.value.slice(caretIndex.value + 1)
  emit('change')
}

function setCaret(index) {
  clearSelection()
  caretIndex.value = Math.max(0, Math.min(value.value.length, index))
}

async function ensureCaretVisible() {
  await nextTick()
  const box = codeRef.value
  const caret = box?.querySelector('.caret')
  if (!box) return

  if (!caret) {
    // 没有光标时（例如键盘收起后粘贴），至少把末尾滚动到可视区域。
    if (box.scrollWidth > box.clientWidth) box.scrollLeft = box.scrollWidth
    return
  }

  const boxRect = box.getBoundingClientRect()
  const caretRect = caret.getBoundingClientRect()
  if (caretRect.right > boxRect.right - 2) {
    box.scrollLeft += caretRect.right - boxRect.right + 6
  } else if (caretRect.left < boxRect.left + 2) {
    box.scrollLeft -= boxRect.left - caretRect.left + 6
  }
}

watch(
  [caretIndex, () => value.value, showCaret, () => props.visible],
  () => {
    nextTick(ensureCaretVisible)
  },
)

function onCharClick(event, index) {
  const rect = event.currentTarget.getBoundingClientRect()
  const after = event.clientX >= rect.left + rect.width / 2
  setCaret(index + (after ? 1 : 0))
}

function insertText(text) {
  const clean = String(text || '').replace(/[^\x20-\x7E]/g, '')
  if (!clean) return
  if (hasSelection.value) {
    replaceSelection(clean)
    return
  }
  value.value =
    value.value.slice(0, caretIndex.value) + clean + value.value.slice(caretIndex.value)
  caretIndex.value += clean.length
  emit('change')
}

async function pasteFromClipboard() {
  try {
    if (!navigator.clipboard?.readText) throw new Error('unsupported')
    const text = await navigator.clipboard.readText()
    insertText(text)
  } catch (_) {
    emit('paste-error', '无法读取剪贴板，请允许粘贴权限或手动输入')
  }
}

function onPasteEvent(event) {
  const text = event.clipboardData?.getData('text')
  if (!text) return
  event.preventDefault()
  insertText(text)
}

function toggleMode() {
  mode.value = mode.value === 'abc' ? 'sym' : 'abc'
}

function onDisplayClick(event) {
  const onChar =
    event.target.closest?.('.char') || event.target.closest?.('.dot-hit')

  if (!isFinePointer) {
    const now = Date.now()
    if (now - lastTapAt < 320) {
      lastTapAt = 0
      keypadOpen.value = true
      selectAll()
      return
    }
    lastTapAt = now
    keypadOpen.value = true
  } else {
    displayRef.value?.focus()
  }

  if (!onChar) setCaret(value.value.length)
}

function onDisplayBlur() {
  displayFocused.value = false
  if (isFinePointer) clearSelection()
}

function onDisplayKeydown(event) {
  if (!isFinePointer) return

  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'v') {
    event.preventDefault()
    pasteFromClipboard()
    return
  }
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'a') {
    event.preventDefault()
    selectAll()
    return
  }
  if (event.key === 'Enter') {
    event.preventDefault()
    emit('submit')
    return
  }
  if (event.key === 'Backspace') {
    event.preventDefault()
    backspace()
    return
  }
  if (event.key === 'Delete') {
    event.preventDefault()
    deleteForward()
    return
  }
  if (event.key === 'ArrowLeft') {
    event.preventDefault()
    if (hasSelection.value) setCaret(selStart.value)
    else setCaret(caretIndex.value - 1)
    return
  }
  if (event.key === 'ArrowRight') {
    event.preventDefault()
    if (hasSelection.value) setCaret(selEnd.value)
    else setCaret(caretIndex.value + 1)
    return
  }
  if (event.key === 'Home') {
    event.preventDefault()
    setCaret(0)
    return
  }
  if (event.key === 'End') {
    event.preventDefault()
    setCaret(value.value.length)
    return
  }
  if (event.key.length === 1 && event.key >= ' ' && event.key <= '~') {
    event.preventDefault()
    press(event.key)
  }
}

function onDocumentPointerDown(event) {
  if (!keypadOpen.value) return
  if (keypadRef.value?.contains(event.target)) return
  if (displayRef.value?.contains(event.target)) return
  keypadOpen.value = false
}

function remeasureKeyboard() {
  if (!keypadOpen.value) return
  emit('keyboard-change', {
    open: true,
    height: keypadRef.value?.offsetHeight || 0,
  })
}

async function notifyKeyboard(open) {
  await nextTick()
  if (open) {
    remeasureKeyboard()
  } else {
    emit('keyboard-change', { open: false, height: 0 })
  }
}

watch(
  () => props.modelValue,
  (value) => {
    if (caretIndex.value > value.length) caretIndex.value = value.length
    if (selEnd.value > value.length) selEnd.value = value.length
    if (selStart.value > selEnd.value) selStart.value = selEnd.value
    if (!value) {
      clearSelection()
      caretIndex.value = 0
    }
  },
)

watch(keypadOpen, async (open) => {
  if (open) {
    document.addEventListener('pointerdown', onDocumentPointerDown, true)
    window.addEventListener('resize', remeasureKeyboard)
  } else {
    document.removeEventListener('pointerdown', onDocumentPointerDown, true)
    window.removeEventListener('resize', remeasureKeyboard)
    clearSelection()
  }
  await notifyKeyboard(open)

  resizeObserver?.disconnect()
  resizeObserver = null
  if (open && typeof ResizeObserver !== 'undefined' && keypadRef.value) {
    resizeObserver = new ResizeObserver(() => remeasureKeyboard())
    resizeObserver.observe(keypadRef.value)
  }
})

onMounted(() => {
  if (props.autofocus) displayRef.value?.focus()
})

onUnmounted(() => {
  document.removeEventListener('pointerdown', onDocumentPointerDown, true)
  window.removeEventListener('resize', remeasureKeyboard)
  resizeObserver?.disconnect()
  resizeObserver = null
})
</script>

<template>
  <div class="secure-input">
    <div
      ref="displayRef"
      class="secure-display"
      :class="{ focused: displayFocused }"
      role="textbox"
      tabindex="0"
      aria-label="访问密码"
      @click="onDisplayClick"
      @dblclick="selectAll"
      @keydown="onDisplayKeydown"
      @paste="onPasteEvent"
      @focus="displayFocused = true"
      @blur="onDisplayBlur"
    >
      <span v-if="!modelValue && !showCaret" class="placeholder">{{ placeholder }}</span>
      <span v-else class="code" ref="codeRef">
        <template v-for="(char, index) in displayChars" :key="index">
          <span
            v-if="showCaret && !hasSelection && index === caretIndex"
            class="caret"
            aria-hidden="true"
          />
          <span
            v-if="visible"
            class="char"
            :class="{ selected: isSelected(index) }"
            @click="onCharClick($event, index)"
          >{{ char }}</span>
          <span
            v-else
            class="dot-hit"
            :class="{ selected: isSelected(index) }"
            @click="onCharClick($event, index)"
            aria-hidden="true"
          >
            <span class="dot" />
          </span>
        </template>
        <span
          v-if="showCaret && !hasSelection && caretIndex >= displayChars.length"
          class="caret"
          aria-hidden="true"
        />
      </span>

      <button
        class="paste"
        type="button"
        aria-label="粘贴"
        @click.stop="pasteFromClipboard"
      >
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="1.8"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <rect x="6" y="4" width="12" height="17" rx="2" />
          <path d="M9 4.5h6a1 1 0 0 1 1 1V7H8V5.5a1 1 0 0 1 1-1Z" />
          <path d="M9 11h6M9 15h6" />
        </svg>
      </button>

      <button
        class="eye"
        type="button"
        :aria-label="visible ? '隐藏密码' : '显示密码'"
        :aria-pressed="visible"
        @click.stop="$emit('toggle-visibility')"
      >
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="1.8"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12Z" />
          <circle cx="12" cy="12" r="2.6" />
        </svg>
      </button>
    </div>
  </div>

  <Teleport to="body">
    <div
      v-if="!isFinePointer && keypadOpen"
      ref="keypadRef"
      class="keyboard-panel"
      role="group"
      aria-label="安全键盘"
    >
      <template v-if="mode === 'abc'">
        <div class="krow">
          <button v-for="key in digitRow" :key="key" class="key" type="button" @click="press(key)">
            {{ key }}
          </button>
        </div>
        <div class="krow">
          <button v-for="key in letterRow1" :key="key" class="key" type="button" @click="press(key)">
            {{ label(key) }}
          </button>
        </div>
        <div class="krow indent">
          <button v-for="key in letterRow2" :key="key" class="key" type="button" @click="press(key)">
            {{ label(key) }}
          </button>
        </div>
        <div class="krow">
          <button class="key wide" type="button" :class="{ active: caps }" @click="caps = !caps">
            ⇧
          </button>
          <button v-for="key in letterRow3" :key="key" class="key" type="button" @click="press(key)">
            {{ label(key) }}
          </button>
          <button class="key wide" type="button" @click="backspace">⌫</button>
        </div>
      </template>

      <template v-else>
        <div class="krow">
          <button v-for="key in shiftRow1" :key="key" class="key" type="button" @click="press(key)">
            {{ key }}
          </button>
        </div>
        <div class="krow">
          <button v-for="key in shiftRow2" :key="key" class="key" type="button" @click="press(key)">
            {{ key }}
          </button>
        </div>
        <div class="krow indent">
          <button v-for="key in shiftRow3" :key="key" class="key" type="button" @click="press(key)">
            {{ key }}
          </button>
          <button class="key wide" type="button" @click="backspace">⌫</button>
        </div>
      </template>

      <div class="krow bottom">
        <button class="key soft" type="button" @click="toggleMode">
          {{ mode === 'abc' ? '?123' : 'ABC' }}
        </button>
        <button class="key" type="button" @click="press(',')">,</button>
        <button class="key space" type="button" @click="press(' ')">空格</button>
        <button class="key" type="button" @click="press('.')">.</button>
        <button class="key enter" type="button" @click="$emit('submit')">登录</button>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.secure-input {
  width: 100%;
}

.secure-display {
  position: relative;
  display: flex;
  align-items: center;
  width: 100%;
  min-height: 48px;
  padding: 0 84px 0 14px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 13px;
  background: rgba(2, 6, 23, 0.62);
  color: #e6ecf5;
  font-size: 16px;
  letter-spacing: 0.1em;
  cursor: text;
  outline: none;
  user-select: none;
  transition: border-color 0.18s ease, box-shadow 0.18s ease, background 0.18s ease;
}

.secure-display.focused {
  border-color: rgba(129, 140, 248, 0.9);
  background: rgba(2, 6, 23, 0.74);
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.2);
}

.placeholder {
  display: inline-flex;
  align-items: center;
  height: 20px;
  color: #667085;
  letter-spacing: 0.12em;
  line-height: 1;
}

.code {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  min-width: 0;
  max-width: 100%;
  overflow-x: auto;
  overflow-y: hidden;
  white-space: nowrap;
  scrollbar-width: none;
}

.code::-webkit-scrollbar {
  display: none;
}

.char {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 9px;
  height: 20px;
  font-size: 16px;
  line-height: 1;
  cursor: text;
}

.char.selected,
.dot-hit.selected {
  background: rgba(99, 102, 241, 0.42);
  border-radius: 5px;
}

.dot-hit {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: none;
  width: 18px;
  height: 24px;
  cursor: text;
}

.dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #cbd5e1;
}

.caret {
  display: inline-block;
  flex: none;
  width: 2px;
  height: 20px;
  margin-left: 1px;
  border-radius: 1px;
  background: #a5b4fc;
  animation: caret-blink 1s steps(1) infinite;
}

@keyframes caret-blink {
  0%, 49% { opacity: 1; }
  50%, 100% { opacity: 0; }
}

.eye,
.paste {
  position: absolute;
  top: 50%;
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  transform: translateY(-50%);
  border: 0;
  border-radius: 10px;
  background: transparent;
  color: #a8b3c7;
  cursor: pointer;
}

.eye { right: 7px; }
.paste { right: 43px; }

.eye:hover,
.paste:hover {
  color: #e6ecf5;
  background: rgba(255, 255, 255, 0.06);
}

.eye svg,
.paste svg {
  width: 19px;
  height: 19px;
}

/* 系统键盘风格：底部固定、滑入 */
.keyboard-panel {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 60;
  display: flex;
  flex-direction: column;
  gap: 5px;
  padding: 7px 6px calc(7px + env(safe-area-inset-bottom));
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  background: #0b1220;
  box-shadow: 0 -16px 48px rgba(0, 0, 0, 0.55);
  animation: keyboard-up 0.22s cubic-bezier(0.22, 1, 0.36, 1) both;
  user-select: none;
}

@keyframes keyboard-up {
  from { transform: translateY(100%); }
  to { transform: translateY(0); }
}

.krow {
  display: flex;
  gap: 5px;
}

.krow.indent {
  padding: 0 4%;
}

.key {
  flex: 1;
  height: 40px;
  min-width: 0;
  border: 0;
  border-radius: 8px;
  background: #1e293b;
  color: #e6ecf5;
  font-size: 17px;
  line-height: 1;
  cursor: pointer;
  touch-action: manipulation;
  -webkit-tap-highlight-color: transparent;
}

.key:active {
  background: #334155;
}

.key.wide {
  flex: 1.5;
  background: #172033;
  color: #cbd5e1;
  font-size: 14px;
}

.key.soft {
  flex: 1.3;
  background: #172033;
  color: #cbd5e1;
  font-size: 12px;
  font-weight: 600;
}

.key.space {
  flex: 4.4;
  font-size: 13px;
}

.key.enter {
  flex: 1.35;
  background: linear-gradient(135deg, #6366f1, #4f46e5 58%, #0ea5e9 135%);
  color: #fff;
  font-size: 12.5px;
  font-weight: 600;
  letter-spacing: 0.08em;
}

.key.active {
  background: rgba(99, 102, 241, 0.55);
  color: #fff;
}

.key.enter:active {
  filter: brightness(1.1);
}
</style>
