<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { NAlert, NButton } from 'naive-ui'
import { studentExamsApi, type StudentExam } from '../api/studentExams'
import { errorMessage, isWriteResultUnknown } from '../api/client'
import PageHeader from '../components/ui/PageHeader.vue'
import SurfacePanel from '../components/ui/SurfacePanel.vue'
import StatusBadge from '../components/ui/StatusBadge.vue'
import LoadingSkeleton from '../components/ui/LoadingSkeleton.vue'
import { availabilityMessages, examPhase, examTime } from '../features/attempts/examAvailability'

const route = useRoute()
const router = useRouter()
const exam = ref<StudentExam | null>(null)
const failure = ref('')
const loading = ref(false)
const starting = ref(false)
const uncertain = ref(false)
const serverNow = ref(0)
let clockAnchor = 0
let serverAnchor = 0
const phase = computed(() =>
  exam.value
    ? examPhase({
        ...exam.value,
        server_now: new Date(serverNow.value).toISOString(),
        ...(unavailable.value ? { current_attempt_status: null } : {}),
      })
    : '',
)
const unavailable = computed(
  () =>
    !!exam.value &&
    (exam.value.status === 'CANCELLED' ||
      exam.value.participant_status === 'CANCELLED' ||
      (!!exam.value.end_at && serverNow.value >= Date.parse(exam.value.end_at))),
)
const countdownLabel = computed(() => {
  if (!exam.value) return ''
  if (exam.value.status === 'CANCELLED') return '本场考试已取消'
  if (exam.value.participant_status === 'CANCELLED') return '参考资格已撤销'
  if (unavailable.value) return '本场考试已结束'
  if (!exam.value.start_at || !exam.value.end_at) return '考试时间尚未配置'
  return serverNow.value < Date.parse(exam.value.start_at)
    ? '距离考试开始还有'
    : '距离整场考试结束还有'
})
const countdownValue = computed(() => {
  if (!exam.value) return '—'
  if (unavailable.value)
    return examPhase({
      ...exam.value,
      server_now: new Date(serverNow.value).toISOString(),
      current_attempt_status: null,
    })
  if (!exam.value.start_at || !exam.value.end_at) return '待安排'
  const target =
    serverNow.value < Date.parse(exam.value.start_at) ? exam.value.start_at : exam.value.end_at
  const seconds = Math.max(0, Math.ceil((Date.parse(target) - serverNow.value) / 1000))
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  return hours ? `${hours} 小时 ${minutes} 分钟` : `${minutes} 分 ${seconds % 60} 秒`
})
const schedule = computed(() => {
  const format = (value: string | null) =>
    value
      ? new Intl.DateTimeFormat('zh-CN', {
          timeZone: 'Asia/Shanghai',
          year: 'numeric',
          month: 'long',
          day: 'numeric',
          hour: '2-digit',
          minute: '2-digit',
          hour12: false,
        }).format(new Date(value))
      : '未配置'
  return exam.value ? `${format(exam.value.start_at)} — ${format(exam.value.end_at)}（上海）` : ''
})
const availability = computed(() =>
  exam.value?.unavailable_reason
    ? availabilityMessages[exam.value.unavailable_reason] || '本场考试当前不可开始。'
    : '',
)
async function load(): Promise<void> {
  loading.value = true
  failure.value = ''
  try {
    exam.value = await studentExamsApi.get(String(route.params.id))
    // 以服务端时间为锚点递进，不使用本机系统时间判断考试开放窗口。
    serverAnchor = Date.parse(exam.value.server_now)
    clockAnchor = performance.now()
    serverNow.value = serverAnchor
    uncertain.value = false
  } catch (error) {
    failure.value = errorMessage(error)
  } finally {
    loading.value = false
  }
}
async function start(): Promise<void> {
  if (!exam.value || starting.value) return
  starting.value = true
  failure.value = ''
  try {
    const attempt = await studentExamsApi.start(exam.value.id)
    await router.push(`/student/attempts/${attempt.id}`)
  } catch (error) {
    failure.value = errorMessage(error)
    uncertain.value = isWriteResultUnknown(error)
  } finally {
    starting.value = false
  }
}
onMounted(load)
const clockTimer = setInterval(() => {
  if (!exam.value) return
  const previous = serverNow.value
  serverNow.value = serverAnchor + performance.now() - clockAnchor
  // 开考边界到达后重新读取可用性，开始按钮仍以服务端许可为准。
  if (
    !loading.value &&
    exam.value.start_at &&
    previous < Date.parse(exam.value.start_at) &&
    serverNow.value >= Date.parse(exam.value.start_at)
  )
    void load()
}, 1000)
onUnmounted(() => clearInterval(clockTimer))
</script>

<template>
  <div class="page-stack exam-detail-page">
    <PageHeader
      eyebrow="EXAM / OVERVIEW"
      :title="exam?.title || '考试详情'"
      description="查看考试规则与个人作答情况，确认后进入考试。"
    >
      <template #actions><RouterLink to="/student/exams">← 返回我的考试</RouterLink></template>
    </PageHeader>
    <NAlert v-if="failure" type="error"
      >{{ failure }} <NButton size="small" @click="load">重新读取考试状态</NButton></NAlert
    >
    <LoadingSkeleton v-if="loading && !exam" variant="detail" label="正在加载考试安排" />
    <template v-if="exam">
      <NAlert
        v-if="availability"
        :type="
          exam.status === 'CANCELLED' || exam.participant_status === 'CANCELLED' ? 'error' : 'info'
        "
        >{{ availability }}
        <p v-if="exam.cancelled_reason">取消原因：{{ exam.cancelled_reason }}</p></NAlert
      >
      <section
        class="exam-summary"
        :class="{ 'is-unavailable': unavailable }"
        aria-label="考试概览"
      >
        <article class="summary-card">
          <h2>01 / 考试状态</h2>
          <p class="summary-context">{{ countdownLabel }}</p>
          <strong class="summary-value" :role="unavailable ? undefined : 'timer'">{{
            countdownValue
          }}</strong>
          <p class="summary-meta">{{ schedule }}</p>
        </article>
        <article class="summary-card">
          <h2>02 / 作答时长</h2>
          <p class="summary-context">每次作答限时</p>
          <strong class="summary-value"
            >{{ exam.duration_seconds ? Math.ceil(exam.duration_seconds / 60) : '未配置'
            }}<small v-if="exam.duration_seconds">分钟</small></strong
          >
          <p class="summary-meta">个人截止时间不超过整场考试结束时间</p>
        </article>
        <article class="summary-card">
          <h2>03 / 试卷结构</h2>
          <p class="summary-context">试卷满分</p>
          <strong class="summary-value">{{ exam.total_score }}<small>分</small></strong>
          <p class="summary-meta">题量与题型进入作答后查看</p>
        </article>
      </section>
      <div class="exam-detail-grid">
        <div class="page-stack">
          <SurfacePanel title="详细信息">
            <dl class="exam-facts">
              <div>
                <dt>考试状态</dt>
                <dd><StatusBadge :label="phase" :tone="unavailable ? 'neutral' : 'info'" /></dd>
              </div>
              <div>
                <dt>开放时间（上海）</dt>
                <dd>{{ examTime(exam.start_at) }} — {{ examTime(exam.end_at) }}</dd>
              </div>
              <div>
                <dt>单次时长</dt>
                <dd>
                  {{
                    exam.duration_seconds
                      ? `${Math.ceil(exam.duration_seconds / 60)} 分钟`
                      : '未配置'
                  }}
                </dd>
              </div>
              <div>
                <dt>作答机会</dt>
                <dd>
                  <span>已使用 {{ exam.used_attempts }} / {{ exam.max_attempts }} 次</span>，剩余
                  {{ exam.remaining_attempts }} 次
                </dd>
              </div>
              <div>
                <dt>试卷总分</dt>
                <dd>{{ exam.total_score }} 分</dd>
              </div>
            </dl>
          </SurfacePanel>
          <SurfacePanel title="开始前，请确认">
            <p class="exam-description">{{ exam.description || '本场考试暂无补充说明。' }}</p>
            <ol class="attempt-rules">
              <li>
                <strong>准备好连续的作答时间</strong
                >点击开始才使用一次机会；已有进行中的作答会恢复，继续作答不额外计次。
              </li>
              <li>
                <strong>计时不会因离开而暂停</strong
                >实际截止时间取单次时长与考试结束时间中较早的一项。关闭页面、刷新和断网不会暂停。
              </li>
              <li>
                <strong>关注答案保存结果</strong
                >选择答案会自动保存，简答停止输入后保存。交卷前请核对保存状态。
              </li>
              <li>
                <strong>交卷后不可修改本次答案</strong
                >截止后仅服务器已保存答案计入答卷，未上传的本地内容不计入。
              </li>
            </ol>
          </SurfacePanel>
        </div>
        <div class="page-stack exam-personal">
          <SurfacePanel title="我的作答">
            <p class="personal-attempts">
              考试机会 <strong>{{ exam.used_attempts }} / {{ exam.max_attempts }}</strong> 次已使用
            </p>
            <h2 class="personal-heading">
              {{
                unavailable
                  ? '本场考试不可继续作答'
                  : exam.current_attempt_status === 'IN_PROGRESS'
                    ? '上次作答尚未提交'
                    : exam.can_start
                      ? '准备开始作答'
                      : '暂不可开始作答'
              }}
            </h2>
            <p class="muted personal-note">
              阅读考试详情不会使用次数。只有确认开始后才创建一次作答。
            </p>
            <div class="detail-start">
              <NButton
                v-if="exam.used_attempts > 0 || exam.status === 'RESULTS_PUBLISHED'"
                @click="router.push(`/student/results/${exam.id}`)"
                >查看本场结果</NButton
              >
              <NButton
                v-if="exam.can_start && !unavailable"
                type="primary"
                :loading="starting"
                :disabled="uncertain"
                @click="start"
                >{{
                  exam.current_attempt_status === 'IN_PROGRESS' ? '继续作答' : '开始作答'
                }}</NButton
              >
              <NButton
                v-if="
                  exam.current_attempt_id &&
                  exam.current_attempt_status === 'SUBMITTED' &&
                  exam.status !== 'CANCELLED' &&
                  exam.participant_status !== 'CANCELLED'
                "
                @click="router.push(`/student/attempts/${exam.current_attempt_id}`)"
                >查看提交状态</NButton
              >
              <NButton v-if="!exam.can_start || unavailable" disabled>{{
                unavailable ? '考试不可作答' : '暂不可开始'
              }}</NButton>
              <span v-if="exam.can_start && !unavailable" class="muted">{{
                exam.current_attempt_status === 'IN_PROGRESS'
                  ? '恢复当前答卷，截止时间保持不变。'
                  : '开始后立即计时。请确认已准备好。'
              }}</span>
            </div>
          </SurfacePanel>
          <NAlert type="info" title="结果与回看"
            >成绩以最后一次有效提交为准。教师公布结果后显示成绩；答案与解析仅在允许回看时开放。</NAlert
          >
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.exam-summary {
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) repeat(2, minmax(0, 1fr));
  gap: 16px;
}
.summary-card {
  padding: 24px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 2px;
  min-width: 0;
}
.summary-card h2 {
  margin: 0 0 20px;
  font-size: 12px;
  font-weight: 600;
  color: var(--blue-700);
  letter-spacing: 0.04em;
}
.summary-context {
  margin: 0 0 10px;
  font-size: 13px;
  color: var(--color-muted);
}
.summary-value {
  display: block;
  font-size: clamp(22px, 2.2vw, 30px);
  font-weight: 650;
  color: var(--color-text);
  font-variant-numeric: tabular-nums;
  line-height: 1.4;
}
.summary-card:first-child .summary-value {
  color: var(--blue-700);
}
.summary-value small {
  margin-left: 8px;
  font-size: 13px;
  font-weight: 400;
  color: var(--color-muted);
}
.summary-meta {
  margin: 16px 0 0;
  font-size: 12px;
  color: var(--color-muted);
  line-height: 1.8;
}
.is-unavailable .summary-card {
  background: var(--neutral-100);
}
.is-unavailable .summary-value,
.is-unavailable .summary-card:first-child .summary-value,
.is-unavailable .summary-value small {
  color: var(--neutral-600);
}
.is-unavailable .summary-card h2 {
  color: var(--neutral-600);
}
.exam-detail-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 310px;
  gap: 24px;
  align-items: start;
}
.exam-detail-grid > div {
  min-width: 0;
}
.personal-attempts {
  margin: 0 0 20px;
  color: var(--color-muted);
  font-size: 13px;
}
.personal-attempts strong {
  color: var(--color-text);
  font-variant-numeric: tabular-nums;
}
.personal-heading {
  font-size: 18px;
  margin: 0 0 12px;
}
.personal-note {
  font-size: 13px;
  line-height: 1.8;
}
.exam-personal .detail-start {
  align-items: stretch;
  flex-direction: column;
  gap: 12px;
}
.exam-facts {
  display: grid;
  gap: 17px;
  margin: 0;
}
.exam-facts > div {
  display: grid;
  grid-template-columns: 112px minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}
dt {
  font-size: 13px;
  color: var(--color-muted);
  margin-bottom: 8px;
}
dd {
  margin: 0;
  line-height: 1.7;
  font-weight: 400;
}
.exam-facts p {
  margin: 3px 0 0;
  color: var(--color-muted);
  font-size: 13px;
}
.exam-description {
  white-space: pre-wrap;
  margin-top: 0;
}
.attempt-rules {
  padding-left: 20px;
  color: var(--color-muted);
  line-height: 1.9;
  font-size: 13px;
}
.attempt-rules li {
  padding-left: 8px;
  margin: 16px 0;
}
.attempt-rules strong {
  display: block;
  font-weight: 600;
  color: var(--color-text);
  margin-bottom: 3px;
}
.detail-start {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 16px;
  border-top: 1px solid var(--color-border);
  margin-top: 22px;
  padding-top: 22px;
  font-size: 13px;
}
@media (max-width: 600px) {
  .exam-facts {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 1050px) {
  .exam-detail-grid {
    grid-template-columns: minmax(0, 1fr) 280px;
    gap: 16px;
  }
  .summary-card {
    padding: 20px;
  }
}
@media (max-width: 850px) {
  .exam-detail-grid {
    grid-template-columns: 1fr;
  }
  .exam-summary {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .summary-card:first-child {
    grid-column: 1 / -1;
  }
}
@media (max-width: 450px) {
  .summary-card {
    padding: 18px;
  }
  .summary-card h2 {
    margin-bottom: 14px;
  }
}
</style>
