<script setup lang="ts">
import type { AnswerData } from '../../api/grading'
import type { QuestionType } from '../../api/questions'
import SafeMarkdown from '../../components/SafeMarkdown.vue'
defineProps<{
  type: QuestionType
  options: { id: string; content: string }[]
  value: AnswerData
  markdown?: boolean
}>()
</script>
<template>
  <div v-if="Array.isArray(value)" class="answer-options">
    <p v-if="!value.length" class="muted">未作答</p>
    <div
      v-for="(option, index) in options.filter((item) => (value as string[]).includes(item.id))"
      :key="option.id"
      class="answer-option"
    >
      <strong
        >{{ String.fromCharCode(65 + options.findIndex((item) => item.id === option.id)) }}.</strong
      ><SafeMarkdown :content="option.content" />
    </div>
  </div>
  <p v-else-if="typeof value === 'boolean'" class="answer-text">
    {{ value ? '正确（真）' : '错误（假）' }}
  </p>
  <SafeMarkdown
    v-else-if="markdown && typeof value === 'string' && value.trim()"
    :content="value"
  />
  <p v-else class="answer-text" :class="{ muted: value === null || value === '' }">
    {{ value === null || value === '' ? (markdown ? '未提供参考答案' : '未作答') : value }}
  </p>
</template>
<style scoped>
.answer-text {
  margin: 0;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  line-height: 1.85;
}
.answer-options {
  display: grid;
  gap: 10px;
}
.answer-option {
  display: flex;
  gap: 8px;
  align-items: baseline;
}
</style>
