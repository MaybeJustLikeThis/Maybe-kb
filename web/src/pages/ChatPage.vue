<template>
  <div>
    <h2 class="text-2xl font-bold mb-4">Chat</h2>

    <div class="mb-4 p-4 bg-gray-50 rounded-lg min-h-[200px] max-h-[500px] overflow-y-auto">
      <div v-if="messages.length === 0" class="text-gray-400 text-center mt-16">
        Ask a question about your knowledge base
      </div>
      <div v-for="msg in messages" :key="msg.id" class="mb-4">
        <div class="font-semibold text-sm mb-1" :class="msg.role === 'user' ? 'text-blue-600' : 'text-green-600'">
          {{ msg.role === 'user' ? 'You' : 'KB' }}
        </div>
        <div class="whitespace-pre-wrap text-gray-800">{{ msg.content }}</div>
      </div>
      <div v-if="loading" class="text-gray-400 italic">Thinking...</div>
    </div>

    <div class="flex gap-2">
      <input
        v-model="query"
        @keyup.enter="ask"
        class="flex-1 p-3 border rounded-lg outline-none focus:ring-2 focus:ring-blue-300"
        placeholder="Ask about your notes..."
        :disabled="loading"
      />
      <button
        @click="ask"
        :disabled="loading || !query.trim()"
        class="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        Send
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { api } from '../api'

interface ChatMessage {
  id: number
  role: 'user' | 'assistant'
  content: string
}

const query = ref('')
const messages = ref<ChatMessage[]>([])
const loading = ref(false)
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
</script>
