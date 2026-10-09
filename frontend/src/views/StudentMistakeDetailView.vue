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
import { useUnsavedChanges } from '../composables/useUnsavedChanges'
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
const baseline = ref<{ answerId: string; note: string; mastered: boolean } | null>(null)
const draftChanged = computed(
  () =>
    !!baseline.value &&
    (note.value !== baseline.value.note || mastered.value !== baseline.value.mastered),
)
const dirty = computed(() => !!data.value && draftChanged.value)
const { confirmDiscard } = useUnsavedChanges(() => draftChanged.value)
watch(
  data,
  (record) => {
    if (!record) return
    // 焦点刷新仍先清空敏感题目；同一错题重新获得授权后保留本页尚未保存的输入。
    const preserveDraft = baseline.value?.answerId === record.answer_id && draftChanged.value
    baseline.value = {
      answerId: record.answer_id,
      note: record.note ?? '',
      mastered: record.mastered,
    }
    if (!preserveDraft) {
      note.value = baseline.value.note
      mastered.value = baseline.value.mastered
    }
    saveFailure.value = ''
    success.value = ''
    needsReload.value = false
  },
  { flush: 'sync' },
)
watch([loading, failure], () => {
  if (!loading.value && !data.value) {
    // 已不能读取时不保留可恢复到界面的旧草稿，撤回和资格失效优先于编辑便利。
    baseline.value = null
    note.value = ''
    mastered.value = false
  }
})
async function reload(): Promise<void> {
  if (!(await confirmDiscard('刷新'))) return
  baseline.value = null
  await load()
}
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
        ><NButton :loading="loading" :disabled="saving" @click="reload">刷新错题</NButton></template
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
          }}<NButton v-if="needsReload" size="small" @click="reload">核对最新标记</NButton></NAlert
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
