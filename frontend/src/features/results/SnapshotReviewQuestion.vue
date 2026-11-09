<script setup lang="ts">
import { computed } from 'vue'
import type { ReviewQuestion } from '../../api/results'
import { questionTypeLabels } from '../../api/questions'
import SafeMarkdown from '../../components/SafeMarkdown.vue'
import StatusBadge from '../../components/ui/StatusBadge.vue'
import AnswerContent from '../grading/AnswerContent.vue'

const props = defineProps<{ question: ReviewQuestion; number?: number; compact?: boolean }>()
const fullScore = computed(
  () =>
    props.question.answer.score !== null &&
    Number(props.question.answer.score) === Number(props.question.score),
)
</script>
<template>
  <article
    class="review-question"
    :class="{ 'review-question--compact': compact }"
    :aria-label="`第 ${number ?? question.display_order} 题`"
  >
    <header class="review-question-header">
      <div>
        <strong v-if="!compact">{{
          String(number ?? question.display_order).padStart(2, '0')
        }}</strong>
        <h2 v-else>题目与解析</h2>
        <span class="muted"
          >{{ questionTypeLabels[question.type] }} · 满分 {{ question.score }} 分</span
        >
      </div>
      <StatusBadge
        :label="`${question.answer.score ?? '待批改'} / ${question.score} 分`"
        :tone="fullScore ? 'success' : 'warning'"
      />
    </header>
    <div v-if="question.knowledge_tags.length && !compact" class="review-tags">
      <span v-for="tag in question.knowledge_tags" :key="tag">{{ tag }}</span>
    </div>
    <SafeMarkdown class="review-question-copy" :content="question.content" />
    <component
      :is="compact ? 'details' : 'div'"
      v-if="question.options.length"
      class="review-options-container"
    >
      <summary v-if="compact">查看全部选项</summary>
      <div class="review-options">
        <div
          v-for="(option, index) in question.options"
          :key="option.id"
          :class="{
            selected:
              Array.isArray(question.answer.answer_data) &&
              question.answer.answer_data.includes(option.id),
          }"
        >
          <span class="review-option-letter">{{ String.fromCharCode(65 + index) }}</span
          ><SafeMarkdown :content="option.content" />
          <span class="review-option-label">{{
            [
              Array.isArray(question.answer.answer_data) &&
              question.answer.answer_data.includes(option.id)
                ? '你的答案'
                : '',
              Array.isArray(question.standard_answer) &&
              question.standard_answer.includes(option.id)
                ? '正确答案'
                : '',
            ]
              .filter(Boolean)
              .join(' · ')
          }}</span>
        </div>
      </div>
    </component>
    <div class="review-answer-grid">
      <section>
        <h3>我的答案</h3>
        <AnswerContent
          :type="question.type"
          :options="question.options"
          :value="question.answer.answer_data"
        />
      </section>
      <section>
        <h3>参考答案</h3>
        <AnswerContent
          :type="question.type"
          :options="question.options"
          :value="question.standard_answer"
          markdown
        />
      </section>
    </div>
    <section v-if="question.explanation" class="review-explanation">
      <h3>答案解析</h3>
      <SafeMarkdown :content="question.explanation" />
    </section>
    <section v-if="question.answer.grader_comment" class="review-explanation">
      <h3>教师评语</h3>
      <p>{{ question.answer.grader_comment }}</p>
    </section>
    <div v-if="compact && question.knowledge_tags.length" class="review-tags compact-tags">
      <span v-for="tag in question.knowledge_tags" :key="tag">{{ tag }}</span>
    </div>
  </article>
</template>
<style scoped>
.review-question {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 32px;
  min-width: 0;
}
.review-question--compact {
  padding: 24px;
}
.review-question--compact .review-question-header h2 {
  font-size: 18px;
  font-weight: 600;
  margin: 0;
}
.review-question--compact .review-question-copy {
  margin: 20px 0;
}
.review-question--compact .review-answer-grid {
  margin-top: 20px;
  gap: 16px;
}
.review-question--compact .review-answer-grid section {
  border: 0;
  padding: 14px 16px;
}
.compact-tags {
  margin: 24px 0 0;
}
.review-options-container summary {
  color: var(--color-muted);
  font-size: 12px;
  cursor: pointer;
  padding: 8px 0;
}
.review-question-header {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 18px;
  padding-bottom: 18px;
  border-bottom: 1px solid var(--color-border);
}
.review-question-header > div {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
  font-size: 13px;
}
.review-question-header strong {
  font:
    24px Consolas,
    monospace;
}
.review-question-copy {
  font-size: 17px;
  line-height: 1.95;
  margin: 24px 0;
}
.review-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 0 0 14px;
}
.review-tags span {
  padding: 3px 8px;
  background: var(--color-bg);
  border-radius: 4px;
  font-size: 12px;
  color: var(--color-muted);
}
.review-options {
  display: grid;
  gap: 10px;
  margin: 18px 0;
}
.review-options > div {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  font-size: 14px;
  border: 1px solid var(--color-border);
  border-radius: 2px;
  padding: 16px 18px;
}
.review-options > div.selected {
  background: var(--blue-50);
  border-color: var(--color-primary);
}
.review-option-letter {
  display: grid;
  place-items: center;
  width: 23px;
  height: 23px;
  flex-shrink: 0;
  background: var(--neutral-100);
  border: 1px solid var(--color-border);
  font:
    12px Consolas,
    monospace;
}
.review-option-label {
  margin-left: auto;
  flex-shrink: 0;
  color: var(--color-muted);
  font-size: 11px;
}
.review-answer-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 20px;
  margin-top: 22px;
}
.review-answer-grid section {
  background: var(--neutral-50);
  border: 1px solid var(--neutral-200);
  border-radius: var(--radius-sm);
  padding: 16px;
  min-width: 0;
}
.review-question h3 {
  margin: 0 0 10px;
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text);
}
.review-explanation {
  border-top: 1px solid var(--color-border);
  padding-top: 18px;
  margin-top: 20px;
  font-size: 14px;
}
.review-explanation :deep(.safe-markdown) {
  background: var(--neutral-50);
  border: 1px solid var(--color-border);
  padding: 16px;
  line-height: 1.9;
}
.review-explanation p {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
@media (max-width: 600px) {
  .review-question {
    padding: 18px;
  }
  .review-answer-grid {
    grid-template-columns: 1fr;
    gap: 12px;
  }
}
</style>
