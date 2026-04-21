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
    focusMessageInput()
  }
  socket.onclose = () => {
    connected.value = false
  }
  socket.onerror = () => {
    errorBanner.value = 'WebSocket connection error'
  }
  socket.onmessage = (ev) => {
    const data = JSON.parse(ev.data)
    if (data.type === 'token') {
      appendAssistantToken(data.text)
      scrollToBottom()
    } else if (data.type === 'done') {
      const last = messages.value[messages.value.length - 1]
      if (last && last.role === 'assistant') last.streaming = false
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
  messages.value.push({ role: 'user', text })
  messages.value.push({ role: 'assistant', text: '', streaming: true })
  scrollToBottom()
  socket.send(JSON.stringify({ content: text }))
  input.value = ''
}
</script>

<template>
  <q-layout view="hHh lpR fFf">
    <q-header elevated class="bg-primary text-white">
      <q-toolbar>
        <q-toolbar-title>Octo Chat</q-toolbar-title>
        <q-badge :color="connected ? 'positive' : 'negative'">
          {{ connected ? 'Online' : 'Offline' }}
        </q-badge>
      </q-toolbar>
    </q-header>

    <q-page-container>
      <q-page class="q-pa-md column" style="height: calc(100vh - 50px)">
        <q-banner
          v-if="errorBanner"
          class="bg-negative text-white q-mb-md"
          dense
        >
          {{ errorBanner }}
        </q-banner>

        <div ref="scrollPanelRef" class="q-mb-md chat-scroll-panel">
          <div class="chat-scroll-inner q-gutter-sm">
            <template v-for="(m, i) in messages" :key="i">
              <q-chat-message v-if="m.role === 'user'" sent name="You">
                <div
                  class="chat-msg-html"
                  v-html="formatChatHtml(m.text)"
                />
              </q-chat-message>
              <q-chat-message v-else name="Assistant">
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
                  v-else
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
          outlined
          dense
          placeholder="Message…"
          :disable="!connected || sending"
          @keyup.enter.exact="send"
        >
          <template #append>
            <q-btn
              round
              dense
              flat
              icon="send"
              color="primary"
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
.chat-scroll-panel {
  flex: 1 1 0;
  min-height: 0;
  overflow-x: hidden;
  overflow-y: auto;
  scrollbar-gutter: stable;
}

.chat-scroll-inner {
  padding-left: 12px;
  padding-right: 12px;
  box-sizing: border-box;
}

.chat-msg-html :deep(strong) {
  font-weight: 700;
}

/* Native scroll reserves gutter; avoid hover/transition shifts on bubbles */
.chat-scroll-panel :deep(.q-message-container),
.chat-scroll-panel :deep(.q-message-text) {
  transition: none !important;
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
