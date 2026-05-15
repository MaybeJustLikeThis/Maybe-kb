<template>
  <div class="chat-page">
    <section class="page-hero">
      <div>
        <p class="eyebrow">Assistant</p>
        <h2>Knowledge Chat</h2>
        <p class="hero-description">
          Ask questions against indexed local notes.
        </p>
      </div>
      <span class="rag-badge">RAG</span>
    </section>

    <section class="chat-surface">
      <div class="messages-area" ref="chatContainer">
        <div v-if="messages.length === 0 && !loading" class="empty-state chat-empty">
          <div class="empty-state-icon">AI</div>
          <p>Ask a question about your knowledge base.</p>
        </div>

        <div
          v-for="msg in messages"
          :key="msg.id"
          :class="['message-row', msg.role === 'user' ? 'message-row-user' : 'message-row-assistant']"
        >
          <div
            :class="msg.role === 'user' ? 'msg-user' : 'msg-assistant'"
            class="msg-bubble"
          >
            <div class="message-content">{{ msg.content }}</div>
          </div>
        </div>

        <div v-if="loading" class="message-row message-row-assistant">
          <div class="msg-assistant msg-bubble">
            <div class="typing-dots">
              <span></span><span></span><span></span>
            </div>
          </div>
        </div>
      </div>

      <div class="command-bar">
        <input
          v-model="query"
          @keyup.enter="ask"
          class="input command-input"
          placeholder="Ask about your notes..."
          :disabled="loading"
        />
        <button
          @click="ask"
          :disabled="loading || !query.trim()"
          class="btn btn-primary command-button"
        >
          Send
        </button>
      </div>
    </section>
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
    const message = e instanceof Error && e.message.includes('config required')
      ? 'Chat providers are not configured yet. Configure LLM and embedding providers, then ask again.'
      : `Error: ${e instanceof Error ? e.message : 'Unknown error'}`
    messages.value.push({ id: ++nextId, role: 'assistant', content: message })
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
.chat-page {
  display: flex;
  max-width: 1120px;
  min-height: calc(100vh - 64px);
  margin: 0 auto;
  flex-direction: column;
}

.page-hero {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 18px;
  padding: 24px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.96), rgba(241, 248, 255, 0.92)),
    radial-gradient(circle at top right, rgba(99, 102, 241, 0.16), transparent 26rem);
  box-shadow: var(--shadow-sm);
}

.eyebrow {
  margin: 0 0 8px;
  color: var(--color-primary-hover);
  font-size: 0.72rem;
  font-weight: 850;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.page-hero h2 {
  margin: 0;
  color: var(--color-text);
  font-size: clamp(1.9rem, 3vw, 3rem);
  font-weight: 850;
  line-height: 1.05;
}

.hero-description {
  max-width: 620px;
  margin: 10px 0 0;
  color: var(--color-text-muted);
  font-size: 0.98rem;
  line-height: 1.65;
}

.rag-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 52px;
  min-height: 34px;
  padding: 0 12px;
  border: 1px solid rgba(8, 145, 178, 0.2);
  border-radius: 999px;
  background: rgba(207, 250, 254, 0.7);
  color: var(--color-primary-hover);
  font-size: 0.74rem;
  font-weight: 900;
  letter-spacing: 0.08em;
}

.chat-surface {
  display: flex;
  min-height: 0;
  flex: 1;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: rgba(255, 255, 255, 0.82);
  box-shadow: var(--shadow-sm);
}

.messages-area {
  min-height: 360px;
  flex: 1;
  overflow-y: auto;
  padding: 22px;
}

.chat-empty {
  padding-top: 72px;
}

.message-row {
  display: flex;
  margin-bottom: 14px;
}

.message-row-user {
  justify-content: flex-end;
}

.message-row-assistant {
  justify-content: flex-start;
}

.msg-bubble {
  max-width: min(76%, 760px);
  padding: 12px 16px;
  border-radius: var(--radius-lg);
  line-height: 1.6;
}

.msg-user {
  border-bottom-right-radius: 4px;
  background: linear-gradient(135deg, var(--color-primary), var(--color-secondary));
  color: #fff;
  box-shadow: 0 12px 24px rgba(8, 145, 178, 0.18);
}

.msg-assistant {
  border: 1px solid var(--color-border);
  border-bottom-left-radius: 4px;
  background: var(--color-surface-solid);
  color: var(--color-text);
  box-shadow: 0 10px 22px rgba(15, 23, 42, 0.06);
}

.message-content {
  color: inherit;
  font-size: 0.9rem;
  white-space: pre-wrap;
}

.command-bar {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 10px;
  align-items: center;
  padding: 14px;
  border-top: 1px solid var(--color-border);
  background: rgba(248, 251, 255, 0.86);
}

.command-input {
  min-height: 44px;
  border-radius: 999px;
  padding: 10px 18px;
  font-size: 0.92rem;
}

.command-button {
  min-width: 92px;
  min-height: 44px;
  border-radius: 999px;
}

.typing-dots {
  display: flex;
  gap: 5px;
  padding: 5px 0;
}

.typing-dots span {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--color-primary);
  animation: typing-bounce 1.4s ease-in-out infinite both;
}

.typing-dots span:nth-child(1) { animation-delay: 0s; }
.typing-dots span:nth-child(2) { animation-delay: 0.16s; }
.typing-dots span:nth-child(3) { animation-delay: 0.32s; }

@keyframes typing-bounce {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
  40% { transform: scale(1); opacity: 1; }
}

@media (max-width: 720px) {
  .chat-page {
    min-height: calc(100vh - 48px);
  }

  .page-hero {
    align-items: flex-start;
    flex-direction: column;
    padding: 20px;
  }

  .messages-area {
    padding: 16px;
  }

  .msg-bubble {
    max-width: 88%;
  }

  .command-bar {
    grid-template-columns: minmax(0, 1fr);
  }

  .command-button {
    width: 100%;
  }
}
</style>
