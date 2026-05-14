<template>
  <div :class="preview ? 'flex gap-4' : ''">
    <div :class="preview ? 'flex-1' : 'w-full'">
      <div class="flex items-center justify-between mb-1">
        <label class="text-sm font-medium text-gray-600">Markdown</label>
        <button
          @click="preview = !preview"
          class="text-xs text-blue-600 hover:underline"
        >{{ preview ? 'Hide Preview' : 'Show Preview' }}</button>
      </div>
      <textarea
        :value="modelValue"
        @input="$emit('update:modelValue', ($event.target as HTMLTextAreaElement).value)"
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
import { Marked } from 'marked'
import { markedHighlight } from 'marked-highlight'
import DOMPurify from 'dompurify'
import hljs from 'highlight.js'
import 'highlight.js/styles/github-dark.min.css'

const props = defineProps<{
  modelValue: string
}>()

defineEmits<{
  'update:modelValue': [value: string]
}>()

const preview = ref(true)

const marked = new Marked(
  markedHighlight({
    langPrefix: 'hljs language-',
    highlight(code: string, lang: string) {
      if (lang && hljs.getLanguage(lang)) {
        return hljs.highlight(code, { language: lang }).value
      }
      return hljs.highlightAuto(code).value
    },
  }),
  { breaks: true, gfm: true },
)

const renderedHtml = computed(() => {
  const raw = marked.parse(props.modelValue || '', { async: false }) as string
  return DOMPurify.sanitize(raw)
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
