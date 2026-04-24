<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { formatChatHtml } from './chatFormat.js'

const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws/chat'

const input = ref('')
const messages = ref([])
const connected = ref(false)
const sending = ref(false)
const errorBanner = ref('')
const scrollPanelRef = ref(null)
const messageInputRef = ref(null)
let socket = null

function stampNow() {
  return new Date().toLocaleTimeString(undefined, {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

function appendAssistantToken(text) {
  const last = messages.value[messages.value.length - 1]
  if (last && last.role === 'assistant' && last.streaming) {
    last.text += text
  }
}

function scrollToBottom() {
  nextTick(() => {
    const el = scrollPanelRef.value
    if (el) {
      el.scrollTop = el.scrollHeight
    }
  })
}

function focusMessageInput() {
  nextTick(() => {
    messageInputRef.value?.focus?.()
  })
}

onMounted(() => {
  socket = new WebSocket(WS_URL)
  socket.onopen = () => {
    connected.value = true
    errorBanner.value = ''
  }
  socket.onclose = () => {
    connected.value = false
  }
  socket.onerror = () => {
    errorBanner.value = 'WebSocket connection error'
  }
  socket.onmessage = (ev) => {
    const data = JSON.parse(ev.data)
    if (data.type === 'opening_start') {
      messages.value.push({
        role: 'assistant',
        text: '',
        streaming: true,
        stamp: undefined,
      })
      scrollToBottom()
    } else if (data.type === 'opening_done') {
      const last = messages.value[messages.value.length - 1]
      if (last && last.role === 'assistant') {
        last.streaming = false
        last.stamp = stampNow()
      }
      scrollToBottom()
      focusMessageInput()
    } else if (data.type === 'token') {
      appendAssistantToken(data.text)
      scrollToBottom()
    } else if (data.type === 'done') {
      const last = messages.value[messages.value.length - 1]
      if (last && last.role === 'assistant') {
        last.streaming = false
        last.stamp = stampNow()
      }
      sending.value = false
      scrollToBottom()
      focusMessageInput()
    } else if (data.type === 'error') {
      errorBanner.value = data.message
      sending.value = false
      const last = messages.value[messages.value.length - 1]
      if (last && last.role === 'assistant' && last.streaming) {
        last.streaming = false
        if (!last.text) last.text = '(no response)'
        last.stamp = stampNow()
      }
      focusMessageInput()
    }
  }
})

onUnmounted(() => {
  socket?.close()
})

function send() {
  const text = input.value.trim()
  if (!text || !connected.value || sending.value) return
  sending.value = true
  errorBanner.value = ''
  messages.value.push({ role: 'user', text, stamp: stampNow() })
  messages.value.push({
    role: 'assistant',
    text: '',
    streaming: true,
    stamp: undefined,
  })
  scrollToBottom()
  socket.send(JSON.stringify({ content: text }))
  input.value = ''
}
</script>

<template>
  <q-layout view="lhh lpR lff" class="retro-layout">
    <div class="connection-float" aria-live="polite">
      <q-badge
        class="connection-badge"
        :class="connected ? 'connection-badge--on' : 'connection-badge--off'"
      >
        {{ connected ? 'ONLINE' : 'OFFLINE' }}
      </q-badge>
    </div>

    <q-page-container class="retro-page-container">
      <q-page class="retro-page column">
        <q-banner
          v-if="errorBanner"
          class="retro-banner q-mb-md"
          dense
        >
          {{ errorBanner }}
        </q-banner>

        <div ref="scrollPanelRef" class="q-mb-md chat-scroll-panel">
          <div class="chat-scroll-inner q-gutter-sm">
            <template v-for="(m, i) in messages" :key="i">
              <q-chat-message
                v-if="m.role === 'user'"
                sent
                name="You"
                :stamp="m.stamp"
                class="retro-chat-msg retro-chat-msg--user"
              >
                <div
                  class="chat-msg-html"
                  v-html="formatChatHtml(m.text)"
                />
              </q-chat-message>
              <q-chat-message
                v-else
                name="Narrador"
                :stamp="m.stamp"
                class="retro-chat-msg retro-chat-msg--narrator"
              >
                <span
                  v-if="m.streaming && !m.text"
                  class="typing-dots"
                  aria-hidden="true"
                >
                  <span class="typing-dots__dot" />
                  <span class="typing-dots__dot" />
                  <span class="typing-dots__dot" />
                </span>
                <div
                  v-else-if="m.text"
                  class="chat-msg-html"
                  v-html="formatChatHtml(m.text)"
                />
              </q-chat-message>
            </template>
          </div>
        </div>

        <q-input
          ref="messageInputRef"
          v-model="input"
          class="retro-input"
          outlined
          dense
          dark
          placeholder=">"
          :disable="!connected || sending"
          @keyup.enter.exact="send"
        >
          <template #append>
            <q-btn
              round
              dense
              flat
              icon="send"
              class="retro-send-btn"
              :disable="!connected || sending"
              aria-label="Send"
              @click="send"
            />
          </template>
        </q-input>
      </q-page>
    </q-page-container>
  </q-layout>
</template>

<style scoped>
/* CRT / 80s terminal */
.retro-layout {
  background: #050505;
  font-family: 'Consolas', 'Lucida Console', 'Courier New', monospace;
}

.retro-page-container {
  padding-top: 0;
}

.retro-page {
  min-height: 100vh;
  height: 100vh;
  padding: 12px 14px 14px;
  padding-top: 44px;
  box-sizing: border-box;
  background: #050505;
  color: #33ff33;
}

.connection-float {
  position: fixed;
  top: 10px;
  right: 12px;
  left: auto;
  transform: none;
  z-index: 6000;
  pointer-events: none;
}

.connection-badge {
  pointer-events: auto;
  font-family: inherit;
  font-size: 11px;
  letter-spacing: 0.12em;
  padding: 6px 14px;
  border-radius: 2px;
  font-weight: 700;
  box-shadow: 0 0 12px rgba(51, 255, 51, 0.25);
}

.connection-badge--on {
  background: rgba(0, 40, 0, 0.92) !important;
  color: #39ff14 !important;
  border: 1px solid #39ff14;
}

.connection-badge--off {
  background: rgba(40, 10, 0, 0.92) !important;
  color: #ff6b35 !important;
  border: 1px solid #ff6b35;
  box-shadow: 0 0 12px rgba(255, 107, 53, 0.35);
}

.retro-banner {
  background: rgba(80, 20, 0, 0.85) !important;
  color: #ffb366 !important;
  border: 1px solid #ff6b35;
}

.chat-scroll-panel {
  flex: 1 1 0;
  min-height: 0;
  overflow-x: hidden;
  overflow-y: auto;
  scrollbar-gutter: stable;
  scrollbar-color: #1a6b1a #0a0a0a;
}

.chat-scroll-inner {
  padding-left: 4px;
  padding-right: 8px;
  box-sizing: border-box;
}

.retro-chat-msg--user .chat-msg-html {
  color: #e6eee6;
  line-height: 1.55;
}

/* Quasar chat bubbles */
.retro-chat-msg :deep(.q-message-name) {
  font-size: 11px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.retro-chat-msg--user :deep(.q-message-name) {
  color: #b8d4b8;
  text-shadow: none;
}

.retro-chat-msg--narrator :deep(.q-message-name) {
  color: #8fbc8f;
  text-shadow: none;
}

.retro-chat-msg :deep(.q-message-stamp) {
  font-size: 10px;
  opacity: 0.9;
}

.retro-chat-msg--user :deep(.q-message-stamp) {
  color: #9ab89a;
}

.retro-chat-msg--narrator :deep(.q-message-stamp) {
  color: #7a9a7a;
}

.retro-chat-msg :deep(.q-message-text) {
  border-radius: 2px;
  border: 1px solid rgba(51, 255, 51, 0.35);
}

.retro-chat-msg--user :deep(.q-message-text) {
  color: #e6eee6;
  text-shadow: none;
  border-color: rgba(200, 220, 200, 0.45);
}

.retro-chat-msg--narrator :deep(.q-message-text) {
  color: #dce8dc;
  text-shadow: none;
  border-color: rgba(200, 220, 200, 0.35);
}

.retro-chat-msg--narrator :deep(.q-message-text--received) {
  background: rgba(25, 35, 28, 0.92) !important;
}

.retro-chat-msg--narrator .chat-msg-html {
  color: #dce8dc;
  line-height: 1.55;
}

.retro-chat-msg .chat-msg-html :deep(strong) {
  color: #5dff8a;
  font-weight: 800;
  text-shadow: 0 0 12px rgba(70, 255, 130, 0.55), 0 0 2px rgba(0, 0, 0, 0.8);
}

.retro-chat-msg--user :deep(.q-message-text--sent) {
  background: rgba(22, 32, 26, 0.94) !important;
  border-color: rgba(200, 220, 200, 0.4);
}

.retro-chat-msg :deep(.q-message-container) {
  margin-bottom: 10px;
}

.retro-chat-msg :deep(.q-message-container),
.retro-chat-msg :deep(.q-message-text) {
  transition: none !important;
}

.retro-input :deep(.q-field__control) {
  color: #33ff33 !important;
  background: rgba(0, 20, 0, 0.65) !important;
}

.retro-input :deep(.q-field__native) {
  color: #33ff33 !important;
  font-family: inherit;
}

.retro-input :deep(.q-field__native::placeholder) {
  color: #1a6b1a;
}

.retro-input :deep(.q-field__outline) {
  color: rgba(51, 255, 51, 0.45) !important;
}

.retro-send-btn {
  color: #39ff14 !important;
}

.retro-send-btn.q-btn--disabled {
  opacity: 0.35;
}

.typing-dots {
  display: inline-flex;
  gap: 2px;
  align-items: center;
  min-height: 1.25em;
  vertical-align: middle;
}

.typing-dots__dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
  opacity: 0.35;
  animation: typing-dot 1s ease-in-out infinite;
}

.typing-dots__dot:nth-child(2) {
  animation-delay: 0.15s;
}

.typing-dots__dot:nth-child(3) {
  animation-delay: 0.3s;
}

.retro-chat-msg--narrator .typing-dots {
  color: #f5f5f5;
}

.retro-chat-msg--narrator .typing-dots__dot {
  background: #f5f5f5;
  animation-name: typing-dot-narrator;
}

.retro-chat-msg--narrator .typing-dots__dot:nth-child(2) {
  background: #f5f5f5;
  animation-delay: 0.15s;
}

.retro-chat-msg--narrator .typing-dots__dot:nth-child(3) {
  background: #f5f5f5;
  animation-delay: 0.3s;
}

@keyframes typing-dot-narrator {
  0%,
  80%,
  100% {
    opacity: 0.5;
    transform: translateY(0);
  }
  40% {
    opacity: 1;
    transform: translateY(-3px);
  }
}

@keyframes typing-dot {
  0%,
  80%,
  100% {
    opacity: 0.25;
    transform: translateY(0);
  }
  40% {
    opacity: 1;
    transform: translateY(-3px);
  }
}
</style>
