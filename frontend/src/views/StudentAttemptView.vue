<script setup lang="ts">
import { computed, onUnmounted, ref } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import { NAlert, NButton, NModal, useDialog } from 'naive-ui'
import { useAuthStore } from '../stores/auth'
import PageHeader from '../components/ui/PageHeader.vue'
import SurfacePanel from '../components/ui/SurfacePanel.vue'
import LoadingSkeleton from '../components/ui/LoadingSkeleton.vue'
import AttemptQuestion from '../features/attempts/AttemptQuestion.vue'
import {
  useAttemptWorkspace,
  type AnswerRow,
  type SaveState,
} from '../features/attempts/useAttemptWorkspace'
import { isUnanswered } from '../features/attempts/answerDrafts'
import { examTime } from '../features/attempts/examAvailability'

const route = useRoute()
const router = useRouter()
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
const savingCount = computed(() => rows.value.filter((row) => row.state === 'saving').length)
const confirmation = ref(false)
const compactWorkspace = window.matchMedia('(max-width: 900px)')
const navigationOpen = ref(!compactWorkspace.matches)
function resizeNavigation(event: MediaQueryListEvent): void {
  navigationOpen.value = !event.matches
}
compactWorkspace.addEventListener('change', resizeNavigation)
onUnmounted(() => compactWorkspace.removeEventListener('change', resizeNavigation))
const exitConfirmation = ref(false)
const exitSaving = ref(false)
const exitTarget = ref('')
let exitAcknowledged = false
/** 退出只离开界面；先尝试同步，并在弹窗中如实区分服务器答案与本地草稿。 */
async function requestExit(target?: string): Promise<void> {
  if (exitSaving.value) return
  exitTarget.value = target || `/student/exams/${attempt.value?.exam_id}`
  exitConfirmation.value = true
  if (canEdit.value && pendingCount.value) {
    exitSaving.value = true
    try {
      await saveAll()
    } finally {
      exitSaving.value = false
    }
  }
}
async function acknowledgeExit(): Promise<void> {
  exitAcknowledged = true
  try {
    await router.push(exitTarget.value)
  } finally {
    exitAcknowledged = false
  }
}
// 侧栏、返回链接等路由离开操作也必须经过同一提醒。
onBeforeRouteLeave((to) => {
  if (!auth.authenticated || attempt.value?.status !== 'IN_PROGRESS' || exitAcknowledged)
    return true
  void requestExit(to.fullPath)
  return false
})
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
    <RouterLink v-if="!attempt" to="/student/exams">← 返回我的考试</RouterLink>
    <RouterLink
      v-if="attempt?.status !== 'IN_PROGRESS' && attempt"
      :to="`/student/exams/${attempt.exam_id}`"
      >← 返回考试详情</RouterLink
    >
    <header v-if="attempt?.status === 'IN_PROGRESS'" class="attempt-header">
      <div class="attempt-heading">
        <span class="attempt-brand">知衡 <small>考试作答</small></span>
        <h1>{{ attempt.exam_title }}</h1>
        <p>第 {{ attempt.attempt_no }} 次作答 · 截止 {{ examTime(attempt.deadline_at) }}（上海）</p>
      </div>
      <div class="attempt-identity">
        <div>
          <strong>{{ auth.user?.real_name }}</strong
          ><span
            >学号 <span class="identity-number">{{ auth.user?.login_name }}</span></span
          >
        </div>
      </div>
      <div class="deadline-clock" :class="{ urgent: remaining < 300000 }">
        <span>剩余时间</span><strong role="timer" aria-label="剩余作答时间">{{ countdown }}</strong>
      </div>
      <NButton type="primary" :disabled="!canEdit" :loading="submitting" @click="beginSubmission"
        >提交答卷</NButton
      >
      <NButton :disabled="submitting" @click="requestExit()">退出作答界面</NButton>
    </header>
    <PageHeader
      v-if="attempt?.status !== 'IN_PROGRESS'"
      :eyebrow="attempt?.status === 'SUBMITTED' ? 'EXAM / SUBMITTED' : 'EXAM / ATTEMPT'"
      :title="
        attempt?.status === 'SUBMITTED' ? '本次作答已提交' : attempt?.exam_title || '考试作答'
      "
      :description="
        attempt
          ? `第 ${attempt.attempt_no} 次作答 · 截止 ${examTime(attempt.deadline_at)}（上海）`
          : undefined
      "
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
    <LoadingSkeleton v-if="loading && !attempt" variant="detail" label="正在读取作答与保存状态" />
    <SurfacePanel v-if="attempt?.status === 'SUBMITTED'" class="submitted-panel">
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
      <NAlert type="info" title="关于再次作答"
        >若考试仍在开放时间内且有剩余次数，可从考试详情再次开始。最终成绩取最后一次有效提交。</NAlert
      >
    </SurfacePanel>
    <template v-else-if="attempt && current">
      <NAlert
        v-if="remaining > 0 && remaining < 300000 && canEdit"
        type="warning"
        title="距离个人作答截止不足 5 分钟"
      >
        请优先检查未答题和保存状态。截止后仅服务器已保存的答案计入答卷。
      </NAlert>
      <div v-if="pendingCount || savingCount" class="attempt-progress">
        <span
          >已作答 <strong>{{ answeredCount }} / {{ rows.length }}</strong></span
        ><span>{{
          savingCount
            ? `正在同步 ${savingCount} 题答案`
            : pendingCount
              ? `${pendingCount} 题待保存`
              : '当前答案均已保存'
        }}</span
        ><NButton
          v-if="pendingCount && canEdit && !savingCount"
          size="small"
          :disabled="submitting"
          @click="saveAll"
          >重试保存全部</NButton
        >
      </div>
      <div class="attempt-workspace">
        <aside class="attempt-sidebar">
          <details
            class="answer-card"
            :open="navigationOpen"
            @toggle="navigationOpen = ($event.target as HTMLDetailsElement).open"
          >
            <summary>
              答题卡与交卷 <span>{{ answeredCount }} / {{ rows.length }}</span>
            </summary>
            <div class="answer-card-content">
              <div
                class="answer-progress-track"
                role="progressbar"
                aria-label="答题进度"
                :aria-valuenow="answeredCount"
                :aria-valuemin="0"
                :aria-valuemax="rows.length"
              >
                <span
                  :style="{ width: `${rows.length ? (answeredCount / rows.length) * 100 : 0}%` }"
                />
              </div>
              <nav class="question-navigation" aria-label="题目导航">
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
                  <span>{{ String(index + 1).padStart(2, '0') }}</span
                  ><span v-if="row.marked" class="navigation-mark" aria-hidden="true">◆</span
                  ><span v-if="row.state !== 'saved'" class="navigation-pending" aria-hidden="true"
                    >•</span
                  >
                  <span :id="`question-state-${row.question.id}`" class="sr-only">{{
                    navigationDescription(row)
                  }}</span>
                </button>
              </nav>
              <div class="navigation-key">
                <span><i class="current-key" />当前题</span
                ><span><i class="answered-key" />已作答</span><span>◆ 待检查</span
                ><span>• 待保存</span>
              </div>
              <p class="navigation-note">
                选择题自动保存；简答停止输入后保存。截止时间由服务器决定。
              </p>
              <div class="navigation-submit">
                <p>
                  尚未作答 <strong>{{ emptyNumbers.length }} 题</strong>
                </p>
                <NButton block :disabled="!canEdit" :loading="submitting" @click="beginSubmission"
                  >检查并交卷</NButton
                >
              </div>
            </div>
          </details>
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
              ><NButton
                type="primary"
                :disabled="currentIndex === rows.length - 1"
                @click="currentIndex += 1"
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
    <NModal
      v-model:show="exitConfirmation"
      preset="card"
      title="退出作答界面？"
      class="responsive-modal"
    >
      <p>
        已保存到服务器的答案会保留，退出后可在考试允许的时间内继续作答。退出不会暂停计时，到截止时间系统将使用服务器已保存的答案自动提交。
      </p>
      <NAlert v-if="exitSaving" type="info">正在尝试保存本页修改，请稍候。</NAlert>
      <NAlert v-else-if="pendingCount" type="warning"
        >仍有
        {{ pendingCount }}
        题修改未确认保存到服务器。尚未同步的本地输入不计入自动提交，请返回作答重试保存。</NAlert
      >
      <p v-else class="muted">当前答案均已确认保存到服务器。退出作答界面不会立即交卷。</p>
      <div class="confirmation-actions">
        <NButton type="primary" @click="exitConfirmation = false">返回作答</NButton
        ><NButton :disabled="exitSaving" @click="acknowledgeExit">我已知晓</NButton>
      </div>
    </NModal>
  </div>
</template>

<style scoped>
.attempt-page {
  max-width: 1248px;
  margin-inline: auto;
}
.attempt-header {
  display: flex;
  align-items: center;
  gap: 28px;
  border-bottom: 1px solid var(--color-border);
  padding-bottom: 20px;
  margin-bottom: 8px;
}
.attempt-heading {
  flex: 1;
  min-width: 0;
}
.attempt-brand {
  display: block;
  font-size: 17px;
  font-weight: 650;
  margin-bottom: 10px;
}
.attempt-brand small {
  font-size: 11px;
  font-weight: 400;
  color: var(--color-muted);
  margin-left: 10px;
}
.attempt-heading h1 {
  font-size: 18px;
  margin: 0;
  font-weight: 600;
}
.attempt-heading p {
  color: var(--color-muted);
  font-size: 11px;
  margin: 6px 0 0;
}
.attempt-identity {
  display: flex;
  justify-content: flex-end;
  gap: 20px;
  align-items: center;
}
.attempt-identity > div {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 16px;
  align-items: center;
  font-size: 13px;
}
.attempt-identity > div > span {
  color: var(--color-muted);
}
.identity-number {
  font-variant-numeric: tabular-nums;
  color: var(--color-text);
}
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
  color: var(--red-700);
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
  grid-template-columns: minmax(0, 1fr) 268px;
  gap: 24px;
  align-items: start;
}
.attempt-main :deep(.surface-panel-body) {
  padding: 32px;
}
.attempt-sidebar {
  position: sticky;
  top: 24px;
  grid-column: 2;
  grid-row: 1;
}
.answer-card {
  border: 1px solid var(--color-border);
  border-radius: 2px;
  background: var(--color-surface);
}
.answer-card summary {
  padding: 18px 20px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
}
.answer-card summary > span {
  float: right;
  color: var(--color-muted);
  font-size: 12px;
  font-weight: 400;
  font-variant-numeric: tabular-nums;
}
.answer-card-content {
  padding: 0 20px 20px;
}
.answer-progress-track {
  background: var(--neutral-200);
  height: 4px;
  margin: 0 0 20px;
}
.answer-progress-track span {
  height: 100%;
  background: var(--blue-600);
  display: block;
  transition: width 0.15s;
}
.navigation-submit {
  margin-top: 20px;
  border-top: 1px solid var(--color-border);
  padding-top: 16px;
}
.navigation-submit p {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  color: var(--color-muted);
}
.navigation-submit strong {
  color: var(--color-text);
}
.question-navigation {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
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
  background: var(--blue-100);
  color: var(--blue-800);
  border-color: var(--blue-200);
}
.question-navigation button.current {
  background: var(--blue-600);
  color: white;
  border-color: var(--blue-600);
  font-weight: 700;
}
.question-navigation button:focus-visible {
  outline: none;
  box-shadow: inset 0 0 0 2px var(--blue-900);
  border-color: var(--blue-900);
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
  color: var(--amber-700);
}
.question-navigation button.current .navigation-pending {
  color: white;
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
  background: var(--blue-100);
  border: 1px solid var(--blue-200);
}
.current-key {
  width: 8px;
  height: 8px;
  background: var(--blue-600);
}
.navigation-note {
  margin: 18px 0 0;
  font-size: 12px;
  color: var(--color-muted);
}
.attempt-main {
  min-width: 0;
  grid-column: 1;
  grid-row: 1;
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
  display: grid;
  justify-items: center;
  text-align: center;
  gap: 22px;
  padding: 42px 24px;
}
.submission-check {
  width: 64px;
  height: 64px;
  background: var(--green-50);
  color: var(--green-700);
  font-size: 28px;
  display: grid;
  place-items: center;
  border-radius: 2px;
  flex-shrink: 0;
}
.submission-summary h3 {
  margin: 0 0 12px;
  font-size: 24px;
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
.submission-summary > div:last-child {
  max-width: 600px;
}
.submitted-panel :deep(.surface-panel-body) {
  padding: 24px;
}
@media (max-width: 900px) {
  .attempt-header {
    flex-wrap: wrap;
    gap: 16px;
  }
  .attempt-heading {
    flex-basis: calc(100% - 150px);
  }
  .attempt-identity {
    order: 3;
    margin-right: auto;
  }
  .attempt-workspace {
    grid-template-columns: 1fr;
  }
  .attempt-sidebar {
    position: static;
    grid-column: 1;
    grid-row: 1;
  }
  .attempt-main {
    grid-column: 1;
    grid-row: 2;
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
  .attempt-main :deep(.surface-panel-body) {
    padding: 20px;
  }
  .attempt-header {
    gap: 18px 12px;
  }
  .attempt-heading {
    flex-basis: 100%;
  }
  .attempt-heading h1 {
    font-size: 17px;
  }
  .attempt-identity {
    order: 0;
    flex: 1;
  }
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
  .attempt-identity {
    justify-content: space-between;
    gap: 12px;
    align-items: flex-start;
  }
  .attempt-identity > div {
    display: grid;
  }
}
</style>
