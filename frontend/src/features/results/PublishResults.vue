<script setup lang="ts">
import { ref } from 'vue'
import { NAlert, NButton, NModal } from 'naive-ui'
import { examsApi, type Exam } from '../../api/exams'
import { ApiError, errorMessage, isWriteResultUnknown } from '../../api/client'

const props = defineProps<{ exam: Exam }>()
const emit = defineEmits<{ close: []; saved: []; refresh: [] }>()
const saving = ref(false)
const failure = ref('')
const needsReload = ref(false)
function refreshAndClose(): void {
  emit('refresh')
  emit('close')
}

async function publish(): Promise<void> {
  if (saving.value || needsReload.value) return
  saving.value = true
  failure.value = ''
  try {
    // 公布条件由服务端在考试锁内检查，页面时间与已见分数不能替代授权判断。
    await examsApi.publishResults(props.exam.id, props.exam.version)
    emit('saved')
    emit('close')
  } catch (error) {
    failure.value = errorMessage(error)
    needsReload.value =
      isWriteResultUnknown(error) ||
      (error instanceof ApiError && error.problem.code === 'VERSION_CONFLICT')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <NModal
    :show="true"
    preset="card"
    title="公布整场结果"
    class="responsive-modal"
    :mask-closable="false"
    :closable="!saving"
    :close-on-esc="!saving"
    @update:show="emit('close')"
  >
    <NAlert class="form-alert" type="info">
      考试结束、全部有效作答提交并按当前依据判完、人工任务完成后，才能整场公布。
      公布后学生可查看本人各次得分与最终成绩；答案、解析和错题仍受回看设置控制。
    </NAlert>
    <NAlert v-if="failure" class="form-alert" type="error">
      {{ failure }}
      <NButton v-if="needsReload" size="small" @click="refreshAndClose"> 核对最新考试状态 </NButton>
    </NAlert>
    <div class="editor-actions">
      <NButton :disabled="saving" @click="emit('close')">暂不公布</NButton>
      <NButton type="primary" :loading="saving" :disabled="needsReload" @click="publish">
        确认公布结果
      </NButton>
    </div>
  </NModal>
</template>
