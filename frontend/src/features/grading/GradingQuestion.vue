<script setup lang="ts">
import type { StaffAttemptQuestion } from '../../api/grading'
import { gradingStatusLabels } from '../../api/grading'
import { questionTypeLabels } from '../../api/questions'
import StatusBadge from '../../components/ui/StatusBadge.vue'
import SafeMarkdown from '../../components/SafeMarkdown.vue'
import AnswerContent from './AnswerContent.vue'
defineProps<{ question: StaffAttemptQuestion; number: number }>()
</script>
<template>
  <article class="grading-question">
    <header class="question-header">
      <div>
        <h2>第 {{ number }} 题</h2>
        <span class="question-eyebrow"
          >{{ questionTypeLabels[question.type] }} · 满分 {{ question.score }} 分</span
        >
      </div>
      <StatusBadge
        :label="gradingStatusLabels[question.answer.grading_status]"
        :tone="question.answer.grading_status === 'GRADED' ? 'success' : 'warning'"
      />
    </header>
    <SafeMarkdown :content="question.content" />
    <section class="student-answer">
      <h3>学生答案</h3>
      <AnswerContent
        :type="question.type"
        :options="question.options"
        :value="question.answer.answer_data"
      />
    </section>
    <section class="grading-reference">
      <h3>{{ question.type === 'SHORT_ANSWER' ? '参考答案与评分依据' : '标准答案' }}</h3>
      <AnswerContent
        :type="question.type"
        :options="question.options"
        :value="question.standard_answer"
        markdown
      />
      <div v-if="question.explanation" class="answer-explanation">
        <h4>解析与评分说明</h4>
        <SafeMarkdown :content="question.explanation" />
      </div>
    </section>
    <div v-if="question.answer.score !== null" class="graded-score">
      <span>{{
        question.answer.grading_status === 'GRADED' ? '本题得分' : '旧依据评分（待重判）'
      }}</span
      ><strong
        >{{ question.answer.score }} <small>/ {{ question.score }} 分</small></strong
      >
      <p v-if="question.answer.grader_comment">{{ question.answer.grader_comment }}</p>
    </div>
  </article>
</template>
<style scoped>
.question-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 22px;
  padding-bottom: 24px;
  border-bottom: 1px solid var(--color-border);
}
.question-header > div {
  display: flex;
  gap: 14px;
  align-items: baseline;
  flex-wrap: wrap;
}
.grading-question > :deep(.safe-markdown) {
  font-size: 16px;
  line-height: 1.9;
}
.question-eyebrow {
  color: var(--color-muted);
  font-size: 12px;
}
h2 {
  font-size: 22px;
  margin: 0;
  font-weight: 500;
}
h3,
h4 {
  font-size: 13px;
  margin: 0 0 12px;
  font-weight: 650;
}
.student-answer {
  margin-top: 24px;
  padding: 0;
}
.student-answer :deep(.answer-text),
.student-answer :deep(.answer-options) {
  padding: 18px 20px;
  border-left: 2px solid var(--color-muted);
  background: var(--color-bg);
}
.grading-reference {
  margin-top: 24px;
  padding-top: 22px;
  border-top: 1px solid var(--color-border);
}
.answer-explanation {
  margin-top: 20px;
  color: var(--color-muted);
}
.graded-score {
  margin-top: 24px;
  display: grid;
  gap: 8px;
  border-top: 1px solid var(--color-border);
  padding-top: 22px;
}
.graded-score > span {
  color: var(--color-muted);
  font-size: 12px;
}
.graded-score strong {
  color: var(--color-primary);
  font-size: 24px;
  font-variant-numeric: tabular-nums;
}
.graded-score small {
  color: var(--color-muted);
  font-size: 12px;
  font-weight: 400;
}
.graded-score p {
  margin: 0;
  white-space: pre-wrap;
}
</style>
