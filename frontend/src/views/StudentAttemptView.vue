<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { NAlert, NButton, NModal, useDialog } from 'naive-ui'
import { useAuthStore } from '../stores/auth'
import PageHeader from '../components/ui/PageHeader.vue'
import SurfacePanel from '../components/ui/SurfacePanel.vue'
import AttemptQuestion from '../features/attempts/AttemptQuestion.vue'
import {
  useAttemptWorkspace,
  type AnswerRow,
  type SaveState,
} from '../features/attempts/useAttemptWorkspace'
import { isUnanswered } from '../features/attempts/answerDrafts'
import { examTime } from '../features/attempts/examAvailability'

const route = useRoute()
const auth = useAuthStore()
const dialog = useDialog()
const workspace = useAttemptWorkspace(String(route.params.id), auth.user!.id)
const {
  attempt,
  rows,
  loading,
  failure,
  notice,
  readonlyReason,
  submitting,
  canEdit,
  countdown,
  remaining,
  missedUploads,
  draftUnavailable,
  pendingCount,
  emptyNumbers,
  answeredCount,
  load,
  poll,
  change,
  mark,
  saveRow,
  saveAll,
  prepareSubmission,
  submit,
  reloadAnswers,
  takeover,
} = workspace
const currentIndex = ref(0)
const current = computed(() => rows.value[currentIndex.value])
const confirmation = ref(false)
const canTakeover = computed(
  () =>
    attempt.value?.status === 'IN_PROGRESS' &&
    remaining.value > 0 &&
    readonlyReason.value.includes('另一页面'),
)
const navigationSaveStates: Record<SaveState, string> = {
  saved: '已保存',
  unsaved: '尚未上传，待保存',
  saving: '正在保存',
  failed: '保存失败，待重试',
  conflict: '版本冲突，尚未保存',
}
/** 状态作为可访问描述更新，题号名称和当前位置语义保持稳定。 */
function navigationDescription(row: AnswerRow): string {
  return [
    isUnanswered(row.value) ? '未作答' : '已作答',
    navigationSaveStates[row.state],
    ...(row.marked ? ['待检查'] : []),
  ].join('，')
}
async function beginSubmission(): Promise<void> {
  if (await prepareSubmission()) confirmation.value = true
}
async function finishSubmission(): Promise<void> {
  if (await submit()) confirmation.value = false
}
function confirmReload(): void {
  dialog.warning({
    title: '重新读取服务器答案',
    content: '这会放弃本页尚未上传的修改。请先复制需要保留的简答内容。',
    positiveText: '放弃本地修改并读取',
    negativeText: '保留本地修改',
    onPositiveClick: reloadAnswers,
  })
}
</script>

<template>
  <div class="page-stack attempt-page">
    <RouterLink v-if="attempt" :to="`/student/exams/${attempt.exam_id}`">← 返回考试详情</RouterLink>
    <PageHeader
      :title="attempt?.exam_title || '考试作答'"
      :description="
        attempt
          ? `第 ${attempt.attempt_no} 次作答 · 截止 ${examTime(attempt.deadline_at)}（上海）`
          : undefined
      "
    >
      <template v-if="attempt?.status === 'IN_PROGRESS'" #actions
        ><div class="deadline-clock" :class="{ urgent: remaining < 300000 }">
          <span>剩余时间</span
          ><strong role="timer" aria-label="剩余作答时间">{{ countdown }}</strong>
        </div>
        <NButton type="primary" :disabled="!canEdit" :loading="submitting" @click="beginSubmission"
          >提交答卷</NButton
        ></template
      >
    </PageHeader>
    <NAlert v-if="failure" type="error"
      >{{ failure }} <NButton v-if="!attempt" size="small" @click="load">重新加载作答</NButton
      ><NButton v-else-if="!canEdit" size="small" @click="poll">重新读取提交状态</NButton></NAlert
    >
    <NAlert v-if="readonlyReason && attempt?.status === 'IN_PROGRESS'" type="warning"
      >{{ readonlyReason }}
      <div v-if="canTakeover" class="takeover-action">
        <NButton :loading="loading" @click="takeover">主动接管此答卷</NButton
        ><span>接管后先读取服务器答案，不合并旧草稿。</span>
      </div></NAlert
    >
    <NAlert v-if="notice" type="info">{{ notice }}</NAlert>
    <NAlert v-if="draftUnavailable" type="warning"
      >当前浏览器无法暂存草稿，请保持网络连接并核对逐题保存状态。</NAlert
    >
    <NAlert v-if="missedUploads" type="warning"
      >有
      {{ missedUploads }}
      题本地草稿未确认上传。未上传的内容不计入答卷，系统只提交服务器已保存的答案。</NAlert
    >
    <p v-if="loading && !attempt" class="muted" role="status">正在读取作答与保存状态…</p>
    <SurfacePanel v-if="attempt?.status === 'SUBMITTED'" title="答卷已提交">
      <div class="submission-summary">
        <div class="submission-check" aria-hidden="true">✓</div>
        <div>
          <h3>
            {{ attempt.submission_type === 'TIMEOUT' ? '时间到，系统已自动交卷' : '手动交卷成功' }}
          </h3>
          <p>第 {{ attempt.attempt_no }} 次作答已提交，答案无法再修改。</p>
          <p>
            {{
              attempt.grading_status === 'GRADED'
                ? '本次答卷已完成批改，成绩将在整场结果公布后开放。'
                : attempt.grading_status === 'GRADING'
                  ? '本次答卷正在等待人工阅卷，成绩将在整场结果公布后开放。'
                  : '本次答卷等待判分，成绩将在整场结果公布后开放。'
            }}
          </p>
          <p v-if="attempt.effective_submitted_at">
            有效提交时间：{{ examTime(attempt.effective_submitted_at) }}（上海）
          </p>
          <p v-if="attempt.submission_type === 'TIMEOUT'">
            系统使用截止前服务器已保存的答案，未上传内容不计入本次答卷。
          </p>
          <RouterLink :to="`/student/exams/${attempt.exam_id}`"
            >返回考试详情查看剩余机会 →</RouterLink
          >
          <p>
            <RouterLink :to="`/student/results/${attempt.exam_id}`"
              >查看本场结果公布状态 →</RouterLink
            >
          </p>
        </div>
      </div>
    </SurfacePanel>
    <template v-else-if="attempt && current">
      <div class="attempt-progress">
        <span
          >已作答 <strong>{{ answeredCount }} / {{ rows.length }}</strong></span
        ><span>{{ pendingCount ? `${pendingCount} 题待保存` : '当前答案均已保存' }}</span
        ><NButton
          v-if="pendingCount && canEdit"
          size="small"
          :disabled="submitting"
          @click="saveAll"
          >重试保存全部</NButton
        >
      </div>
      <div class="attempt-workspace">
        <aside class="attempt-sidebar">
          <SurfacePanel title="题目导航"
            ><nav class="question-navigation" aria-label="题目导航">
              <button
                v-for="(row, index) in rows"
                :key="row.question.id"
                type="button"
                :aria-label="`第 ${index + 1} 题`"
                :aria-describedby="`question-state-${row.question.id}`"
                :aria-current="currentIndex === index ? 'step' : undefined"
                :class="{
                  current: currentIndex === index,
                  answered: !isUnanswered(row.value),
                  pending: row.state !== 'saved',
                  marked: row.marked,
                }"
                @click="currentIndex = index"
              >
                <span>{{ index + 1 }}</span
                ><span v-if="row.marked" class="navigation-mark" aria-hidden="true">★</span
                ><span v-if="row.state !== 'saved'" class="navigation-pending" aria-hidden="true"
                  >•</span
                >
                <span :id="`question-state-${row.question.id}`" class="sr-only">{{
                  navigationDescription(row)
                }}</span>
              </button>
            </nav>
            <div class="navigation-key">
              <span><i class="answered-key" />已作答</span><span>★ 待检查</span
              ><span>• 待保存</span>
            </div>
            <p class="navigation-note">
              选择题自动保存；简答停止输入后保存。截止时间由服务器决定。
            </p></SurfacePanel
          >
        </aside>
        <div class="attempt-main">
          <SurfacePanel
            ><AttemptQuestion
              :row="current"
              :number="currentIndex + 1"
              :disabled="!canEdit || submitting"
              @change="change(current!, $event)"
              @save="saveRow(current!)"
              @mark="mark(current!)"
            />
            <div v-if="current.state === 'conflict'" class="conflict-action">
              <NButton :disabled="!canEdit || submitting" @click="confirmReload"
                >重新读取服务器答案</NButton
              >
            </div>
            <div class="question-step">
              <NButton :disabled="currentIndex === 0" @click="currentIndex -= 1">上一题</NButton
              ><span>{{ currentIndex + 1 }} / {{ rows.length }}</span
              ><NButton :disabled="currentIndex === rows.length - 1" @click="currentIndex += 1"
                >下一题</NButton
              >
            </div></SurfacePanel
          >
        </div>
      </div>
    </template>
    <NModal
      v-model:show="confirmation"
      preset="card"
      title="确认交卷"
      class="responsive-modal"
      :mask-closable="!submitting"
      :closable="!submitting"
      :close-on-esc="!submitting"
    >
      <p>提交后，本次答卷的答案不能修改。</p>
      <NAlert v-if="emptyNumbers.length" type="warning"
        ><strong>以下 {{ emptyNumbers.length }} 题尚未作答：</strong>
        <p class="empty-question-numbers">
          {{ emptyNumbers.map((number) => `第 ${number} 题`).join('、') }}
        </p>
        <span>可返回补答，也可确认提交空题。</span></NAlert
      >
      <p v-else class="muted">全部题目已作答，保存状态已核对。</p>
      <div class="confirmation-actions">
        <NButton :disabled="submitting" @click="confirmation = false">返回检查</NButton
        ><NButton
          type="primary"
          :loading="submitting"
          :disabled="!canEdit"
          @click="finishSubmission"
          >确认交卷</NButton
        >
      </div>
    </NModal>
  </div>
</template>

<style scoped>
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip-path: inset(50%);
}
.deadline-clock {
  text-align: right;
  display: grid;
  gap: 4px;
  min-width: 112px;
}
.deadline-clock span {
  font-size: 12px;
  color: var(--color-muted);
}
.deadline-clock strong {
  font-size: 23px;
  font-variant-numeric: tabular-nums;
  line-height: 1.1;
  font-weight: 650;
  color: var(--color-primary);
}
.deadline-clock.urgent strong {
  color: #b04743;
}
.takeover-action {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
  margin-top: 12px;
  font-size: 12px;
}
.attempt-progress {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 20px;
  font-size: 13px;
  color: var(--color-muted);
}
.attempt-progress strong {
  color: var(--color-text);
  font-weight: 600;
}
.attempt-workspace {
  display: grid;
  grid-template-columns: 244px minmax(0, 1fr);
  gap: 24px;
  align-items: start;
}
.attempt-sidebar {
  position: sticky;
  top: 24px;
}
.question-navigation {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}
.question-navigation button {
  position: relative;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  aspect-ratio: 1;
  padding: 5px;
  color: var(--color-muted);
  font-size: 14px;
}
.question-navigation button.answered {
  background: var(--color-primary-soft);
  color: var(--color-primary);
  border-color: #b8dbce;
}
.question-navigation button.current {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
  font-weight: 700;
}
.navigation-mark {
  position: absolute;
  right: 2px;
  top: 0;
  font-size: 9px;
}
.navigation-pending {
  position: absolute;
  right: 4px;
  bottom: 0;
  color: #986313;
}
.navigation-key {
  display: flex;
  gap: 11px;
  flex-wrap: wrap;
  margin-top: 22px;
  color: var(--color-muted);
  font-size: 11px;
}
.navigation-key > span {
  display: inline-flex;
  gap: 5px;
  align-items: center;
}
.answered-key {
  width: 8px;
  height: 8px;
  background: var(--color-primary-soft);
  border: 1px solid #b8dbce;
}
.navigation-note {
  margin: 18px 0 0;
  font-size: 12px;
  color: var(--color-muted);
}
.attempt-main {
  min-width: 0;
}
.question-step {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 28px;
  padding-top: 22px;
  border-top: 1px solid var(--color-border);
}
.question-step > span {
  font-size: 12px;
  color: var(--color-muted);
}
.conflict-action {
  margin-top: 16px;
}
.confirmation-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 24px;
}
.empty-question-numbers {
  margin: 8px 0;
}
.submission-summary {
  display: flex;
  gap: 22px;
}
.submission-check {
  width: 48px;
  height: 48px;
  background: var(--color-primary-soft);
  color: var(--color-primary);
  font-size: 28px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  flex-shrink: 0;
}
.submission-summary h3 {
  margin: 0 0 12px;
  font-size: 17px;
}
.submission-summary p {
  color: var(--color-muted);
  font-size: 13px;
  margin: 7px 0;
}
.submission-summary a {
  display: inline-block;
  margin-top: 20px;
  font-size: 13px;
}
@media (max-width: 900px) {
  .attempt-workspace {
    grid-template-columns: 1fr;
  }
  .attempt-sidebar {
    position: static;
  }
  .question-navigation {
    grid-template-columns: repeat(8, minmax(0, 44px));
    gap: 10px;
  }
  .navigation-note {
    margin-top: 12px;
  }
}
@media (max-width: 550px) {
  .question-navigation {
    grid-template-columns: repeat(5, minmax(0, 1fr));
  }
  .attempt-workspace {
    gap: 16px;
  }
  .submission-summary {
    gap: 14px;
  }
  .submission-check {
    width: 36px;
    height: 36px;
    font-size: 23px;
  }
  .deadline-clock {
    text-align: left;
    min-width: 120px;
  }
}
</style>
