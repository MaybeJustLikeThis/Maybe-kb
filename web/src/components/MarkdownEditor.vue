<template>
  <div :class="preview ? 'flex gap-4' : ''">
    <div :class="preview ? 'flex-1' : 'w-full'">
      <div class="flex items-center justify-between mb-1">
        <label class="text-sm font-medium text-gray-600">Markdown</label>
        <div class="flex items-center gap-3">
          <button
            @click="preview = !preview"
            class="text-xs text-blue-600 hover:underline"
          >{{ preview ? 'Hide Preview' : 'Show Preview' }}</button>
          <label
            class="text-xs text-blue-600 hover:underline cursor-pointer"
            tabindex="0"
            @keydown.enter.prevent="fileInput?.click()"
            @keydown.space.prevent="fileInput?.click()"
          >
            {{ uploading ? 'Uploading...' : 'Upload Asset' }}
            <input
              ref="fileInput"
              type="file"
              class="hidden"
              :disabled="uploading"
              @change="uploadAsset"
            />
          </label>
        </div>
      </div>
      <p v-if="uploadError" class="text-xs text-red-600 mb-1">{{ uploadError }}</p>
      <textarea
        :value="modelValue"
        @input="emit('update:modelValue', ($event.target as HTMLTextAreaElement).value)"
        class="w-full p-3 border rounded-lg font-mono text-sm focus:ring-2 focus:ring-blue-300 focus:border-blue-500 outline-none"
        :class="preview ? 'h-96' : 'h-[32rem]'"
      ></textarea>
    </div>
    <div v-if="preview" class="flex-1 border rounded-lg p-4 overflow-auto h-96">
      <div v-html="renderedHtml" class="prose prose-slate max-w-none"></div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { api } from '../api'
import { renderMarkdown } from '../markdown'

const props = defineProps<{
  modelValue: string
  noteDir?: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const preview = ref(true)
const uploading = ref(false)
const uploadError = ref('')
const fileInput = ref<HTMLInputElement | null>(null)

async function uploadAsset(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file || uploading.value) return

  uploading.value = true
  uploadError.value = ''
  try {
    const result = await api.uploadAttachment(file)
    const isImage = file.type.startsWith('image/')
    const label = escapeMarkdownLinkText(file.name)
    const markdown = isImage
      ? `![${label}](${result.path})`
      : `[${label}](${result.path})`
    const nextValue = props.modelValue
      ? `${props.modelValue.replace(/\s*$/, '')}\n\n${markdown}\n`
      : `${markdown}\n`
    emit('update:modelValue', nextValue)
  } catch (e) {
    uploadError.value = e instanceof Error ? e.message : 'Upload failed.'
  } finally {
    uploading.value = false
    input.value = ''
  }
}

function escapeMarkdownLinkText(text: string) {
  return text.replace(/[\r\n]+/g, ' ').replace(/([\\[\]])/g, '\\$1')
}

const renderedHtml = computed(() => {
  let html = renderMarkdown(props.modelValue || '')
  if (props.noteDir) {
    html = html.replace(
      /(<img\s[^>]*\bsrc=")((?!https?:\/\/|\/|data:)[^"]+)(")/gi,
      (_m: string, prefix: string, src: string, suffix: string) => {
        const base = src.startsWith('attachments/') ? '' : props.noteDir
        return `${prefix}/vault/${base}${src}${suffix}`
      },
    )
  }
  return html
})
</script>

<style>
/* Grade markdown rendered content */
.prose pre {
  background: #0d1117;
  padding: 1rem;
  border-radius: 0.5rem;
  overflow-x: auto;
}
.prose pre code {
  background: transparent;
  padding: 0;
  font-size: 0.875em;
}
.prose code::before { content: none; }
.prose code::after  { content: none; }
.prose code {
  background: #f1f5f9;
  padding: 0.125rem 0.25rem;
  border-radius: 0.25rem;
  font-size: 0.875em;
}
.prose table {
  display: block;
  overflow-x: auto;
}
.prose img {
  border-radius: 0.375rem;
}
.prose blockquote {
  border-left-color: #e2e8f0;
}
.prose input[type="checkbox"] {
  margin-right: 0.5rem;
}
</style>
