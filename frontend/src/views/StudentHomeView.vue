<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { NAlert, NButton } from 'naive-ui'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { studentExamsApi, type AttemptDetail, type StudentExam } from '../api/studentExams'
import { resultsApi, resultStateLabels } from '../api/results'
import { mistakesApi } from '../api/mistakes'
import { errorMessage } from '../api/client'
import { usePrivateResource } from '../features/results/usePrivateResource'
import { examPhase, examTime } from '../features/attempts/examAvailability'
import { isUnanswered } from '../features/attempts/answerDrafts'
import StatusBadge from '../components/ui/StatusBadge.vue'
import LoadingSkeleton from '../components/ui/LoadingSkeleton.vue'
import AppIcon from '../components/ui/AppIcon.vue'

const auth = useAuthStore()
const router = useRouter()
const tick = ref(performance.now())
let timer: ReturnType<typeof setInterval> | undefined
onMounted(() => {
  timer = setInterval(() => {
    tick.value = performance.now()
  }, 1000)
})
onBeforeUnmount(() => clearInterval(timer))

const exams = usePrivateResource(
  () => auth.user?.id,
  async (signal) => {
    const page = await studentExamsApi.list({ page: 1, page_size: 20 }, signal)
    const current = page.items.filter((exam) => examPhase(exam) === '作答中')
    const focus =
      current[0] ??
      page.items.find((exam) => exam.can_start) ??
      [...page.items].filter((exam) => examPhase(exam) === '未开始').sort(byStart)[0]
    let attempt: AttemptDetail | null = null
    let attemptFailure = ''
    if (focus?.current_attempt_id && examPhase(focus) === '作答中') {
      try {
        // 首页只读服务器快照，不调用 activate，不接管仍在其他标签页的作答权限。
        attempt = await studentExamsApi.attempt(focus.current_attempt_id, signal)
      } catch (error) {
        attemptFailure = errorMessage(error)
      }
    }
    return {
      items: page.items,
      currentCount: current.length,
      completeList: page.total <= page.items.length,
      focus,
      attempt,
      attemptFailure,
      receivedAt: performance.now(),
    }
  },
)
const learning = usePrivateResource(
  () => auth.user?.id,
  async (signal) => {
    const [results, mistakes] = await Promise.all([
      resultsApi.list({ page: 1, page_size: 20 }, signal),
      mistakesApi.list({ page: 1, page_size: 3 }, { mastered: 'false' }, signal),
    ])
    return { results: results.items, mistakes }
  },
)
const data = exams.data
const learningData = learning.data
const focus = computed(() => data.value?.focus)
const attempt = computed(() => data.value?.attempt)
function byStart(a: StudentExam, b: StudentExam): number {
  return Date.parse(a.start_at ?? '') - Date.parse(b.start_at ?? '')
}
const nextExams = computed(() =>
  (data.value?.items ?? [])
    .filter(
      (exam) => exam.id !== focus.value?.id && (exam.can_start || examPhase(exam) === '未开始'),
    )
    .sort(byStart)
    .slice(0, 2),
)
const answered = computed(
  () =>
    attempt.value?.questions.filter((question) => !isUnanswered(question.answer.answer_data))
      .length ?? 0,
)
const remaining = computed(() => {
  if (!attempt.value || !data.value) return null
  const elapsed = Math.max(0, tick.value - data.value.receivedAt)
  return Math.max(
    0,
    Date.parse(attempt.value.deadline_at) - Date.parse(attempt.value.server_now) - elapsed,
  )
})
const countdown = computed(() => {
  if (remaining.value === null) return '—'
  const seconds = Math.ceil(remaining.value / 1000)
  const minutes = Math.floor(seconds / 60)
  return `${String(minutes).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`
})
const resumable = computed(
  () => attempt.value?.status === 'IN_PROGRESS' && (remaining.value ?? 0) > 0,
)
const focusStatus = computed(() => {
  if (resumable.value) return '作答进行中'
  if (attempt.value?.status === 'SUBMITTED') return '本次作答已提交'
  if (attempt.value && remaining.value === 0) return '本次作答已截止'
  return focus.value ? examPhase(focus.value) : ''
})
const newestResult = computed(
  () =>
    learningData.value?.results.find((item) => item.result_state === 'PUBLISHED') ??
    learningData.value?.results[0],
)
const knowledgeTags = computed(() =>
  [...new Set(learningData.value?.mistakes.items.flatMap((item) => item.knowledge_tags) ?? [])]
    .slice(0, 3)
    .join('、'),
)
const today = new Date()
const greetingHour = Number(
  new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    hour: '2-digit',
    hourCycle: 'h23',
  })
    .formatToParts(today)
    .find((part) => part.type === 'hour')!.value,
)
const greeting = greetingHour < 12 ? '上午好' : greetingHour < 18 ? '下午好' : '晚上好'
const todayLabel =
  new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  })
    .format(today)
    .replaceAll('/', '.') +
  ' · ' +
  new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai', weekday: 'short' }).format(today)
function scheduleLabel(exam: StudentExam): string {
  if (!exam.start_at || !exam.end_at) return '时间未配置'
  const dayFormat = new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  })
  const start = new Date(exam.start_at)
  const end = new Date(exam.end_at)
  if (dayFormat.format(start) !== dayFormat.format(today)) return examTime(exam.start_at)
  const timeFormat = new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  })
  return `今天 ${timeFormat.format(start)}—${dayFormat.format(start) === dayFormat.format(end) ? timeFormat.format(end) : examTime(exam.end_at)}`
}
function openFocus(): void {
  if (!focus.value) return
  void router.push(
    resumable.value ? `/student/attempts/${attempt.value!.id}` : `/student/exams/${focus.value.id}`,
  )
}
</script>

<template>
  <div class="student-home page-stack">
    <header class="page-header student-home-header">
      <div class="page-header-copy">
        <div class="student-home-eyebrow">STUDENT / WORKSPACE</div>
        <h1>{{ greeting }}，{{ auth.user?.real_name }}</h1>
        <p>
          {{
            data?.currentCount
              ? data.completeList
                ? `你有 ${data.currentCount} 场考试正在作答，请留意剩余时间。`
                : '你有考试正在作答，请留意剩余时间。'
              : '查看接下来的考试安排与学习记录。'
          }}
        </p>
      </div>
      <time class="student-home-date">{{ todayLabel }}</time>
    </header>
    <LoadingSkeleton v-if="exams.loading.value" variant="detail" label="正在读取考试安排" />
    <NAlert v-else-if="exams.failure.value" type="error" title="考试安排暂时无法加载">
      {{ exams.failure.value }} <NButton size="small" @click="exams.load">重新加载考试</NButton>
    </NAlert>
    <section v-else-if="focus" class="student-home-feature" aria-label="当前考试">
      <div class="student-feature-main">
        <StatusBadge
          :label="focusStatus"
          :tone="resumable ? 'info' : 'neutral'"
          :class="{ 'student-status-active': resumable }"
        />
        <h2>{{ focus.title }}</h2>
        <p v-if="attempt?.status === 'IN_PROGRESS'">
          继续上次作答，服务器已保存 {{ answered }} / {{ attempt.questions.length }} 题的答案。
        </p>
        <p v-else>
          {{
            focus.can_start
              ? '阅读考试说明，确认规则后开始作答。'
              : '查看考试安排，提前准备连续的作答时间。'
          }}
        </p>
        <div class="student-feature-meta">
          <span v-if="attempt"
            >本次截止 <strong>{{ examTime(attempt.deadline_at) }}</strong></span
          >
          <span v-else
            >考试时间
            <strong>{{ examTime(focus.start_at) }} — {{ examTime(focus.end_at) }}</strong></span
          >
          <span v-if="attempt"
            >第 <strong>{{ attempt.attempt_no }} / {{ focus.max_attempts }}</strong> 次作答</span
          >
          <span v-else
            >作答时长
            <strong>{{
              focus.duration_seconds ? `${Math.ceil(focus.duration_seconds / 60)} 分钟` : '未配置'
            }}</strong></span
          >
          <span
            >满分 <strong>{{ Number(focus.total_score) }}</strong> 分</span
          >
        </div>
        <p v-if="data?.attemptFailure" class="student-progress-error">
          作答进度暂时无法读取。<NButton text type="primary" @click="exams.load">重试读取</NButton>
        </p>
      </div>
      <div class="student-feature-side">
        <small>{{ attempt?.status === 'IN_PROGRESS' ? '距离本次作答截止' : '当前考试安排' }}</small>
        <strong
          v-if="attempt?.status === 'IN_PROGRESS'"
          class="student-feature-clock"
          role="timer"
          aria-label="本次作答剩余时间"
          >{{ countdown }}</strong
        >
        <strong v-else class="student-feature-state">{{ focusStatus }}</strong>
        <NButton type="primary" @click="openFocus"
          >{{ resumable ? '继续作答' : '查看考试' }} <AppIcon name="arrow-right" :size="16"
        /></NButton>
        <span class="student-snapshot-note">{{
          attempt ? '进度依据服务器已保存答案' : '查看详情不会消耗作答机会'
        }}</span>
      </div>
    </section>
    <section v-else class="student-home-empty">暂无考试安排，新的考试发布后会显示在这里。</section>
    <div class="student-home-columns">
      <section aria-label="接下来的考试">
        <header class="student-section-heading">
          <h2>接下来的考试 <small>按开始时间排序</small></h2>
          <NButton @click="router.push('/student/exams')">全部考试 ↗</NButton>
        </header>
        <div class="student-home-panel">
          <LoadingSkeleton v-if="exams.loading.value" :rows="2" />
          <template v-else-if="nextExams.length">
            <article v-for="exam in nextExams" :key="exam.id" class="student-next-exam">
              <div class="student-next-copy">
                <div class="student-next-title">
                  <h3>{{ exam.title }}</h3>
                  <StatusBadge
                    :label="examPhase(exam)"
                    :tone="exam.can_start ? 'info' : 'neutral'"
                    :class="{ 'student-status-upcoming': examPhase(exam) === '未开始' }"
                  />
                </div>
                <p>
                  {{
                    exam.duration_seconds
                      ? `${Math.ceil(exam.duration_seconds / 60)} 分钟`
                      : '时长未配置'
                  }}
                  · {{ Number(exam.total_score) }} 分
                </p>
              </div>
              <div class="student-next-time">
                <small>考试时间</small><strong>{{ scheduleLabel(exam) }}</strong>
              </div>
              <NButton @click="router.push(`/student/exams/${exam.id}`)">{{
                exam.can_start ? '查看考试' : '查看详情'
              }}</NButton>
            </article>
          </template>
          <p v-else class="student-panel-empty">
            {{ exams.failure.value ? '请重新加载考试安排。' : '暂无其他可参加或即将开始的考试。' }}
          </p>
        </div>
      </section>
      <section class="student-home-panel student-learning" aria-label="学习记录">
        <header class="student-learning-header"><h2>学习记录</h2></header>
        <div class="student-learning-body">
          <LoadingSkeleton v-if="learning.loading.value" :rows="2" label="正在读取学习记录" />
          <NAlert v-else-if="learning.failure.value" type="error"
            >学习记录暂时无法加载。<NButton size="small" @click="learning.load"
              >重试</NButton
            ></NAlert
          >
          <template v-else>
            <div v-if="newestResult" class="student-learning-row">
              <div>
                <h3>{{ newestResult.title }}</h3>
                <p>
                  {{ examTime(newestResult.submitted_at) }} ·
                  {{ resultStateLabels[newestResult.result_state] }}
                </p>
              </div>
              <strong
                v-if="
                  newestResult.result_state === 'PUBLISHED' && newestResult.final_score !== null
                "
                class="student-learning-score"
                >{{ Number(newestResult.final_score)
                }}<small> / {{ Number(newestResult.total_score) }}</small></strong
              >
              <span v-else class="muted">{{
                newestResult.result_state === 'PUBLISHED' ? '待批改' : '暂未开放'
              }}</span>
            </div>
            <p v-else class="student-learning-empty">暂无考试结果。</p>
            <div class="student-learning-row">
              <div>
                <h3>待复习错题</h3>
                <p>{{ knowledgeTags || '复习错题，巩固薄弱知识点。' }}</p>
              </div>
              <NButton @click="router.push('/student/mistakes')"
                >{{ learningData?.mistakes.total ?? 0 }} 题 →</NButton
              >
            </div>
          </template>
          <NButton @click="router.push('/student/results')">查看考试历史</NButton>
        </div>
      </section>
    </div>
    <aside class="student-home-reminder">
      <AppIcon name="clock" :size="18" />
      <div>
        <strong>考试提醒</strong>
        <p>
          答案修改后请确认保存状态。断网或关闭页面不会暂停计时；截止后系统将使用已保存的答案交卷。
        </p>
      </div>
    </aside>
    <footer class="student-home-footer">知衡 · 在线限时考试系统</footer>
  </div>
</template>

<style scoped>
.student-home {
  gap: 24px;
}
.student-status-active {
  background: var(--blue-600);
  border-color: var(--blue-600);
  color: #fff;
}
.student-status-upcoming {
  background: var(--color-surface);
  border: 1px dashed var(--neutral-400);
}
.student-home-footer {
  color: var(--color-muted);
  font-size: 11px;
  padding-top: 6px;
}
.student-home-eyebrow {
  color: var(--color-muted);
  font-size: 11px;
  letter-spacing: 1.5px;
  margin-bottom: 10px;
}
.student-home-header {
  align-items: center;
}
.student-home-date {
  color: var(--color-muted);
  font-size: 12px;
  white-space: nowrap;
}
.student-home-feature {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 250px;
  background: var(--color-surface);
  border: 1px solid var(--blue-200);
  border-left: 4px solid var(--blue-600);
}
.student-feature-main {
  padding: 28px;
  min-width: 0;
}
.student-feature-main h2 {
  font-size: 24px;
  margin: 16px 0 12px;
  overflow-wrap: anywhere;
}
.student-feature-main p {
  color: var(--color-muted);
  font-size: 13px;
  margin: 0;
}
.student-feature-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 24px;
  font-size: 12px;
  color: var(--color-muted);
  margin-top: 24px;
}
.student-feature-meta strong {
  color: var(--color-text);
  font-weight: 600;
}
.student-feature-side {
  padding: 28px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  border-left: 1px solid var(--blue-200);
  background: var(--blue-50);
}
.student-feature-side small {
  color: var(--color-muted);
  font-size: 12px;
}
.student-feature-clock {
  font:
    36px Consolas,
    monospace;
  color: var(--blue-700);
  margin: 10px 0 16px;
}
.student-feature-state {
  margin: 12px 0 20px;
  font-size: 22px;
  color: var(--blue-700);
}
.student-feature-side :deep(.n-button__content) {
  gap: 8px;
}
.student-snapshot-note {
  color: var(--color-muted);
  font-size: 11px;
  margin-top: 10px;
}
.student-progress-error {
  margin-top: 16px !important;
}
.student-home-columns {
  display: grid;
  grid-template-columns: minmax(0, 1.6fr) minmax(280px, 1fr);
  gap: 24px;
  align-items: start;
}
.student-home-columns > section {
  min-width: 0;
}
.student-section-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}
.student-section-heading h2,
.student-learning h2 {
  margin: 0;
  font-size: 16px;
}
.student-section-heading h2 small {
  color: var(--color-muted);
  font-size: 12px;
  font-weight: 400;
  margin-left: 10px;
}
.student-home-panel {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
}
.student-next-exam {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 112px 92px;
  align-items: center;
  gap: 16px;
  padding: 22px 24px;
  border-bottom: 1px solid var(--color-border);
}
.student-next-exam:last-child {
  border-bottom: 0;
}
.student-next-title {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}
.student-next-copy h3,
.student-learning h3 {
  font-size: 14px;
  margin: 0;
  overflow-wrap: anywhere;
}
.student-next-copy p,
.student-learning p {
  color: var(--color-muted);
  font-size: 12px;
  margin: 8px 0 0;
}
.student-next-time {
  display: grid;
  gap: 6px;
}
.student-next-time small {
  font-size: 11px;
  color: var(--color-muted);
}
.student-next-time strong {
  font-size: 12px;
  font-weight: 500;
}
.student-learning-header {
  padding: 20px 24px;
  border-bottom: 1px solid var(--color-border);
}
.student-learning-body {
  padding: 24px;
}
.student-learning-row {
  display: flex;
  align-items: center;
  gap: 16px;
  justify-content: space-between;
  padding: 0 0 18px;
  margin-bottom: 18px;
  border-bottom: 1px solid var(--color-border);
}
.student-learning-row > div {
  min-width: 0;
}
.student-learning-row > a {
  white-space: nowrap;
  font-size: 13px;
}
.student-learning-score {
  font:
    24px Consolas,
    monospace;
  white-space: nowrap;
}
.student-learning-score small {
  font-size: 12px;
  color: var(--color-muted);
}
.student-learning-empty {
  margin: 0 0 18px !important;
}
.student-panel-empty,
.student-home-empty {
  padding: 24px;
  margin: 0;
  color: var(--color-muted);
  font-size: 13px;
}
.student-home-empty {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
}
.student-home-reminder {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 16px 20px;
  border: 1px solid var(--neutral-300);
  color: var(--neutral-700);
  font-size: 12px;
}
.student-home-reminder strong {
  font-size: 13px;
}
.student-home-reminder p {
  margin: 3px 0 0;
}
@media (max-width: 1200px) {
  .student-home-columns {
    grid-template-columns: minmax(0, 1fr);
  }
}
@media (max-width: 650px) {
  .student-home-header {
    align-items: flex-start;
  }
  .student-home-feature {
    grid-template-columns: minmax(0, 1fr);
  }
  .student-feature-main {
    padding: 22px;
  }
  .student-feature-main h2 {
    font-size: 21px;
  }
  .student-feature-side {
    border-left: 0;
    border-top: 1px solid var(--blue-200);
    padding: 18px 22px;
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: center;
    gap: 4px 16px;
  }
  .student-feature-side > small {
    grid-column: 1;
  }
  .student-feature-clock,
  .student-feature-state {
    grid-column: 1;
    margin: 0;
    font-size: 30px;
  }
  .student-feature-side > :deep(.n-button) {
    grid-column: 2;
    grid-row: 1 / 3;
  }
  .student-snapshot-note {
    grid-column: 1 / -1;
  }
  .student-section-heading h2 small {
    display: none;
  }
  .student-next-exam {
    grid-template-columns: minmax(0, 1fr) auto;
    padding: 20px 18px;
    gap: 14px;
  }
  .student-next-copy {
    grid-column: 1 / -1;
  }
  .student-next-time {
    grid-column: 1;
  }
  .student-learning-header,
  .student-learning-body {
    padding: 18px;
  }
}
</style>
