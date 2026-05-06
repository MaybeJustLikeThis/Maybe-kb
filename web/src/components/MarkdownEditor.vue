<template>
  <div class="flex gap-4" :class="preview ? 'flex-row' : 'flex-col'">
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
    <div v-if="preview" class="flex-1 border rounded-lg p-4 prose prose-sm max-w-none overflow-auto h-96">
      <div v-html="renderedHtml"></div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

const props = defineProps<{
  modelValue: string
}>()

defineEmits<{
  'update:modelValue': [value: string]
}>()

const preview = ref(true)

const renderedHtml = computed(() => {
  const raw = marked(props.modelValue || '', { breaks: true }) as string
  return DOMPurify.sanitize(raw)
})
</script>
