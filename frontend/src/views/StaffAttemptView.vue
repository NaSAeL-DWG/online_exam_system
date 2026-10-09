<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { NAlert, NButton, useDialog } from 'naive-ui'
import { gradingStatusLabels, taskStatusLabels, type StaffAttemptDetail } from '../api/grading'
import PageHeader from '../components/ui/PageHeader.vue'
import SurfacePanel from '../components/ui/SurfacePanel.vue'
import StatusBadge from '../components/ui/StatusBadge.vue'
import GradingQuestion from '../features/grading/GradingQuestion.vue'
import GradeForm from '../features/grading/GradeForm.vue'
import GradingHistory from '../features/grading/GradingHistory.vue'
import ReassignTask from '../features/grading/ReassignTask.vue'
import { useGradingWorkspace } from '../features/grading/useGradingWorkspace'
import { useUnsavedChanges } from '../composables/useUnsavedChanges'
const route = useRoute()
const dialog = useDialog()
const { attempt, loading, saving, failure, success, needsReload, load, grade } =
  useGradingWorkspace(() => String(route.params.id))
const dirty = ref(false)
useUnsavedChanges(() => dirty.value)
const historyAnswerId = ref<string | null>(null)
const reassignmentVisible = ref(false)
function taskReassigned(detail: StaffAttemptDetail): void {
  attempt.value = detail
  success.value = '阅卷任务已改派，已有题分和评分历史已保留。'
}
const currentIndex = ref(0)
const current = computed(() => attempt.value?.questions[currentIndex.value])
const requiresManualReview = computed(
  () =>
    attempt.value?.questions.some(
      (question) =>
        question.type === 'SHORT_ANSWER' &&
        typeof question.answer.answer_data === 'string' &&
        !!question.answer.answer_data.trim(),
    ) || false,
)
const taskLabel = computed(() =>
  attempt.value?.task
    ? taskStatusLabels[attempt.value.task.status]
    : requiresManualReview.value
      ? '等待任务分配'
      : '无需人工阅卷',
)
const firstReviewLabel = computed(() =>
  !requiresManualReview.value
    ? '无需首阅'
    : attempt.value?.task?.first_review_completed_at
      ? '整卷首阅已完成'
      : attempt.value?.task
        ? '整卷首阅尚未完成'
        : '等待任务分配',
)
function selectQuestion(index: number): void {
  if (index === currentIndex.value || saving.value) return
  const select = () => {
    dirty.value = false
    currentIndex.value = index
  }
  if (!dirty.value) {
    select()
    return
  }
  dialog.warning({
    title: '本题评分尚未保存',
    content: '切换题目将放弃当前表单的修改。',
    positiveText: '放弃修改并切换',
    negativeText: '继续评分',
    onPositiveClick: select,
  })
}
function reload(): void {
  if (!dirty.value && !needsReload.value) {
    void load()
    return
  }
  dialog.warning({
    title: '重新读取最新评分',
    content: '将放弃此表单尚未保存的评分和评语，读取服务器最新答卷。',
    positiveText: '放弃输入并重新读取',
    negativeText: '保留当前输入',
    onPositiveClick: async () => {
      await load()
      dirty.value = false
    },
  })
}
onMounted(load)
</script>
<template>
  <div class="page-stack">
    <RouterLink v-if="attempt" :to="`/staff/exams/${attempt.exam_id}`">← 返回考试管理</RouterLink>
    <PageHeader
      :title="attempt?.exam_title || '答卷详情'"
      :description="
        attempt
          ? `${attempt.student.real_name}（${attempt.student.login_name}）· 第 ${attempt.attempt_no} 次作答`
          : undefined
      "
      ><template #actions
        ><StatusBadge
          v-if="attempt"
          :label="gradingStatusLabels[attempt.grading_status]"
          :tone="attempt.grading_status === 'GRADED' ? 'success' : 'warning'"
        /><NButton
          v-if="attempt?.can_reassign"
          :disabled="saving"
          @click="reassignmentVisible = true"
          >改派阅卷任务</NButton
        ><NButton :loading="loading" :disabled="saving" @click="reload">刷新答卷</NButton></template
      ></PageHeader
    >
    <NAlert v-if="failure" type="error"
      ><span>{{ failure }}</span>
      <NButton size="small" :disabled="saving" @click="reload">{{
        needsReload ? '重新读取最新评分' : '重新加载答卷'
      }}</NButton></NAlert
    >
    <NAlert v-if="success" type="success">{{ success }}</NAlert>
    <p v-if="loading && !attempt" class="muted" role="status">正在读取答卷…</p>
    <template v-if="attempt">
      <div class="attempt-overview">
        <div>
          <span>本次得分</span
          ><strong>{{
            attempt.grading_status === 'GRADED' && attempt.final_score !== null
              ? `${attempt.final_score} 分`
              : '待批改'
          }}</strong>
        </div>
        <div>
          <span>人工任务</span><strong>{{ taskLabel }}</strong>
        </div>
        <div>
          <span>指定教师</span
          ><strong>{{
            attempt.task?.assigned_teacher?.real_name ||
            (requiresManualReview ? '尚未指派' : '无需指派')
          }}</strong>
        </div>
        <div>
          <span>首阅状态</span><strong>{{ firstReviewLabel }}</strong>
        </div>
      </div>
      <NAlert v-if="attempt.results_published" type="warning"
        >本场结果已公布。修改评分或标准答案前必须先撤回结果。<RouterLink
          :to="`/staff/exams/${attempt.exam_id}`"
          >前往考试管理撤回结果 →</RouterLink
        ></NAlert
      >
      <NAlert v-else-if="requiresManualReview && !attempt.task" type="info"
        >非空简答题将在考试结束并完成自动判分后分配整卷任务。当前可共享查看答卷，等待后台分配。</NAlert
      >
      <NAlert
        v-else-if="
          requiresManualReview && !attempt.can_grade && !attempt.task?.first_review_completed_at
        "
        type="info"
        >仅指定教师可完成整卷首阅。其他工作人员可共享查看答卷；管理员通过改派激活教师处理未完成任务。</NAlert
      >
      <div v-if="current" class="grading-workspace">
        <aside>
          <SurfacePanel title="答卷题目"
            ><nav class="grading-navigation" aria-label="阅卷题目导航">
              <button
                v-for="(question, index) in attempt.questions"
                :key="question.id"
                type="button"
                :aria-label="`查看第 ${index + 1} 题`"
                :aria-current="currentIndex === index ? 'step' : undefined"
                :disabled="saving"
                @click="selectQuestion(index)"
              >
                <span>第 {{ index + 1 }} 题</span
                ><span>{{
                  question.answer.grading_status === 'GRADED'
                    ? `${question.answer.score} / ${question.score}`
                    : '待批改'
                }}</span>
              </button>
            </nav></SurfacePanel
          >
        </aside>
        <SurfacePanel
          ><GradingQuestion :question="current" :number="currentIndex + 1" /><GradeForm
            v-if="current.can_grade && !attempt.results_published"
            :key="current.answer.id"
            :question="current"
            :saving="saving"
            :disabled="needsReload || loading"
            @dirty="dirty = $event"
            @save="grade(current!, $event)"
          />
          <div class="history-action">
            <NButton :disabled="saving" @click="historyAnswerId = current!.answer.id"
              >查看本题评分历史</NButton
            >
          </div></SurfacePanel
        >
      </div>
      <p v-else class="muted">本份作答暂无可查看的题目。</p>
    </template>
    <GradingHistory
      v-if="historyAnswerId"
      :answer-id="historyAnswerId"
      @close="historyAnswerId = null"
    />
    <ReassignTask
      v-if="reassignmentVisible && attempt"
      :attempt="attempt"
      @close="reassignmentVisible = false"
      @saved="taskReassigned"
      @refreshed="attempt = $event"
    />
  </div>
</template>
<style scoped>
.attempt-overview {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 24px;
  padding: 20px 24px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
}
.attempt-overview > div {
  display: grid;
  gap: 8px;
}
.attempt-overview span {
  font-size: 12px;
  color: var(--color-muted);
}
.attempt-overview strong {
  font-size: 14px;
  font-weight: 600;
}
.attempt-overview > div:first-child strong {
  font-size: 22px;
  color: var(--color-primary);
}
.grading-workspace {
  display: grid;
  grid-template-columns: 228px minmax(0, 1fr);
  align-items: start;
  gap: 24px;
}
.grading-workspace > aside {
  position: sticky;
  top: 24px;
}
.history-action {
  margin-top: 24px;
  border-top: 1px solid var(--color-border);
  padding-top: 20px;
}
.grading-navigation {
  display: grid;
  gap: 8px;
}
.grading-navigation button {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  padding: 12px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  font-size: 12px;
  text-align: left;
}
.grading-navigation button span:last-child {
  color: var(--color-muted);
  font-variant-numeric: tabular-nums;
}
.grading-navigation button[aria-current] {
  border-color: var(--color-primary);
  background: var(--color-primary-soft);
  color: var(--color-primary);
}
@media (max-width: 900px) {
  .attempt-overview {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .grading-workspace {
    grid-template-columns: minmax(0, 1fr);
  }
  .grading-workspace > aside {
    position: static;
  }
  .grading-navigation {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
  .grading-navigation button {
    flex-direction: column;
  }
}
@media (max-width: 480px) {
  .attempt-overview {
    padding: 18px;
    gap: 18px;
  }
  .grading-navigation {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
