<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'

const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws/chat'

const input = ref('')
const messages = ref([])
const connected = ref(false)
const sending = ref(false)
const errorBanner = ref('')
const scrollArea = ref(null)
let socket = null

function appendAssistantToken(text) {
  const last = messages.value[messages.value.length - 1]
  if (last && last.role === 'assistant' && last.streaming) {
    last.text += text
  }
}

function scrollToBottom() {
  nextTick(() => {
    const sa = scrollArea.value
    if (sa && typeof sa.setScrollPosition === 'function') {
      sa.setScrollPosition('vertical', 999999, 0)
    }
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
    if (data.type === 'token') {
      appendAssistantToken(data.text)
      scrollToBottom()
    } else if (data.type === 'done') {
      const last = messages.value[messages.value.length - 1]
      if (last && last.role === 'assistant') last.streaming = false
      sending.value = false
      scrollToBottom()
    } else if (data.type === 'error') {
      errorBanner.value = data.message
      sending.value = false
      const last = messages.value[messages.value.length - 1]
      if (last && last.role === 'assistant' && last.streaming) {
        last.streaming = false
        if (!last.text) last.text = '(no response)'
      }
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

        <q-scroll-area ref="scrollArea" class="col q-mb-md" style="min-height: 0">
          <div class="q-gutter-sm">
            <q-chat-message
              v-for="(m, i) in messages"
              :key="i"
              :text="[m.text || (m.streaming ? '…' : '')]"
              :sent="m.role === 'user'"
              :name="m.role === 'user' ? 'You' : 'Assistant'"
            />
          </div>
        </q-scroll-area>

        <q-input
          v-model="input"
          outlined
          dense
          placeholder="Message…"
          :disable="!connected || sending"
          @keyup.enter="send"
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
