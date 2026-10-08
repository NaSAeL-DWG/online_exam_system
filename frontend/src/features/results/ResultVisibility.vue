<script setup lang="ts">
import { NAlert } from 'naive-ui'
import { resultStateLabels, type ResultState } from '../../api/results'
defineProps<{ state: ResultState; allowReview: boolean }>()
</script>
<template>
  <NAlert v-if="state !== 'PUBLISHED'" :type="state === 'CORRECTING' ? 'warning' : 'info'">
    <strong>{{ resultStateLabels[state] }}</strong>
    <p v-if="state === 'CORRECTING'">
      教师正在复核本场结果。成绩、答案、错题及相关分析暂时不可查看，重新公布后恢复。
    </p>
    <p v-else-if="state === 'NOT_PUBLISHED'">
      整场公布后才能查看各次得分和最终成绩，请等待教师公布。
    </p>
    <p v-else>本场历史作答已失效，不计入成绩、错题与分析。</p>
  </NAlert>
  <NAlert v-else-if="!allowReview" type="info"
    >本场未开放答卷回看。成绩可查看，答案、解析、错题及题目表现不开放。</NAlert
  >
</template>
