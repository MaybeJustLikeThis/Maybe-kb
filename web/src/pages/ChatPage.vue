<template>
  <div class="flex flex-col" style="height: calc(100vh - 96px);">
    <h2 class="text-2xl font-bold mb-5" style="color: var(--color-text);">Chat</h2>

    <!-- Messages area -->
    <div class="flex-1 overflow-y-auto mb-4 space-y-4" ref="chatContainer">
      <div v-if="messages.length === 0 && !loading" class="empty-state" style="margin-top: 80px;">
        <div class="empty-state-icon">💬</div>
        <p>Ask a question about your knowledge base.</p>
      </div>

      <div
        v-for="msg in messages"
        :key="msg.id"
        :class="['flex', msg.role === 'user' ? 'justify-end' : 'justify-start']"
      >
        <div
          :class="msg.role === 'user' ? 'msg-user' : 'msg-assistant'"
          class="msg-bubble"
        >
          <div class="whitespace-pre-wrap text-sm">{{ msg.content }}</div>
        </div>
      </div>

      <!-- Typing indicator -->
      <div v-if="loading" class="flex justify-start">
        <div class="msg-assistant msg-bubble">
          <div class="typing-dots">
            <span></span><span></span><span></span>
          </div>
        </div>
      </div>
    </div>

    <!-- Input area -->
    <div class="flex gap-2 items-end">
      <input
        v-model="query"
        @keyup.enter="ask"
        class="input flex-1"
        style="border-radius: 100px; padding: 10px 18px;"
        placeholder="Ask about your notes..."
        :disabled="loading"
      />
      <button
        @click="ask"
        :disabled="loading || !query.trim()"
        class="btn btn-primary"
        style="border-radius: 100px; padding: 10px 24px;"
      >
        Send
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import { api } from '../api'

interface ChatMessage {
  id: number
  role: 'user' | 'assistant'
  content: string
}

const query = ref('')
const messages = ref<ChatMessage[]>([])
const loading = ref(false)
const chatContainer = ref<HTMLElement | null>(null)
let nextId = 0

async function ask() {
  const q = query.value.trim()
  if (!q || loading.value) return

  messages.value.push({ id: ++nextId, role: 'user', content: q })
  query.value = ''
  loading.value = true

  try {
    const res = await api.chatAsk(q)
    messages.value.push({ id: ++nextId, role: 'assistant', content: res.answer })
  } catch (e) {
    messages.value.push({ id: ++nextId, role: 'assistant', content: `Error: ${e instanceof Error ? e.message : 'Unknown error'}` })
  } finally {
    loading.value = false
  }
}

watch(() => messages.value.length, async () => {
  await nextTick()
  if (chatContainer.value) {
    chatContainer.value.scrollTop = chatContainer.value.scrollHeight
  }
})
</script>

<style scoped>
.msg-bubble {
  max-width: 80%;
  padding: 10px 16px;
  border-radius: var(--radius-lg);
  line-height: 1.6;
}

.msg-user {
  background: var(--color-primary);
  color: #fff;
  border-bottom-right-radius: 4px;
}

.msg-assistant {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  color: var(--color-text);
  border-bottom-left-radius: 4px;
}

/* Typing dots animation */
.typing-dots {
  display: flex;
  gap: 4px;
  padding: 4px 0;
}
.typing-dots span {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--color-text-muted);
  animation: typing-bounce 1.4s ease-in-out infinite both;
}
.typing-dots span:nth-child(1) { animation-delay: 0s; }
.typing-dots span:nth-child(2) { animation-delay: 0.16s; }
.typing-dots span:nth-child(3) { animation-delay: 0.32s; }

@keyframes typing-bounce {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
  40% { transform: scale(1); opacity: 1; }
}
</style>
