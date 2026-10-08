<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { NAlert, NButton } from 'naive-ui'
import { mistakesApi } from '../api/mistakes'
import { ApiError, errorMessage, isWriteResultUnknown } from '../api/client'
import PageHeader from '../components/ui/PageHeader.vue'
import SurfacePanel from '../components/ui/SurfacePanel.vue'
import SnapshotReviewQuestion from '../features/results/SnapshotReviewQuestion.vue'
import { usePrivateResource } from '../features/results/usePrivateResource'
import '../features/results/results.css'

const route = useRoute()
const { data, loading, failure, load } = usePrivateResource(
  () => route.params.id,
  (signal) => mistakesApi.detail(String(route.params.id), signal),
)
const note = ref('')
const mastered = ref(false)
const saving = ref(false)
const saveFailure = ref('')
const success = ref('')
const needsReload = ref(false)
const dirty = computed(
  () =>
    !!data.value &&
    (note.value !== (data.value.note ?? '') || mastered.value !== data.value.mastered),
)
watch(
  data,
  (record) => {
    note.value = record?.note ?? ''
    mastered.value = record?.mastered ?? false
    saveFailure.value = ''
    success.value = ''
    needsReload.value = false
  },
  { flush: 'sync' },
)
async function save(): Promise<void> {
  const record = data.value
  if (!record || saving.value || needsReload.value || !dirty.value) return
  saving.value = true
  saveFailure.value = ''
  success.value = ''
  try {
    const result = await mistakesApi.annotate(record.answer_id, {
      note: note.value || null,
      mastered: mastered.value,
    })
    // 页面已重新读取或切走时，旧写入结果不能恢复失去授权的题目内容。
    if (data.value === record) {
      data.value = { ...record, ...result }
      success.value = '学习标记已保存。'
    }
  } catch (error) {
    if (error instanceof ApiError && error.problem.code === 'MISTAKE_NOT_FOUND') {
      void load()
    } else {
      saveFailure.value = errorMessage(error)
      needsReload.value = isWriteResultUnknown(error)
    }
  } finally {
    saving.value = false
  }
}
</script>
<template>
  <div class="page-stack">
    <RouterLink to="/student/mistakes">← 返回我的错题</RouterLink>
    <PageHeader
      title="错题详情"
      :description="data ? `${data.exam_title} · 第 ${data.attempt_no} 次作答` : undefined"
    >
      <template #actions
        ><NButton :loading="loading" :disabled="saving" @click="load">刷新错题</NButton></template
      >
    </PageHeader>
    <NAlert v-if="failure" type="error">{{ failure }}</NAlert>
    <p v-if="!data" class="result-empty" role="status">
      {{ loading ? '正在读取可见错题…' : '暂无可查看的错题。' }}
    </p>
    <template v-if="data">
      <SnapshotReviewQuestion :question="data.question" />
      <SurfacePanel title="学习标记" description="备注与掌握状态独立保存，不改变本次分数。">
        <NAlert v-if="saveFailure" class="form-alert" type="error"
          >{{ saveFailure
          }}<NButton v-if="needsReload" size="small" @click="load">核对最新标记</NButton></NAlert
        >
        <NAlert v-if="success" class="form-alert" type="success">{{ success }}</NAlert>
        <form class="annotation-form" @submit.prevent="save">
          <label class="field"
            >学习备注<textarea
              v-model="note"
              aria-label="学习备注"
              maxlength="20000"
              rows="4"
              placeholder="记录易错原因、复习方法或待解决的问题"
              :disabled="saving || needsReload"
            />
          </label>
          <label class="check-field"
            ><input
              v-model="mastered"
              aria-label="已掌握本题"
              type="checkbox"
              :disabled="saving || needsReload"
            />已掌握本题</label
          >
          <div class="editor-actions">
            <NButton
              type="primary"
              attr-type="submit"
              :loading="saving"
              :disabled="!dirty || needsReload"
              >保存学习标记</NButton
            >
          </div>
        </form>
      </SurfacePanel>
    </template>
  </div>
</template>
<style scoped>
.annotation-form {
  display: grid;
  gap: 20px;
}
</style>
