<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { NAlert, NButton } from 'naive-ui'
import { studentExamsApi, type StudentExam } from '../api/studentExams'
import { errorMessage, isWriteResultUnknown } from '../api/client'
import PageHeader from '../components/ui/PageHeader.vue'
import SurfacePanel from '../components/ui/SurfacePanel.vue'
import StatusBadge from '../components/ui/StatusBadge.vue'
import { availabilityMessages, examPhase, examTime } from '../features/attempts/examAvailability'

const route = useRoute()
const router = useRouter()
const exam = ref<StudentExam | null>(null)
const failure = ref('')
const loading = ref(false)
const starting = ref(false)
const uncertain = ref(false)
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
</script>

<template>
  <div class="page-stack narrow-page">
    <RouterLink to="/student/exams">← 返回我的考试</RouterLink>
    <PageHeader :title="exam?.title || '考试详情'">
      <template v-if="exam" #actions
        ><StatusBadge
          :label="examPhase(exam)"
          :tone="
            exam.status === 'CANCELLED' || exam.participant_status === 'CANCELLED'
              ? 'danger'
              : 'info'
          "
      /></template>
    </PageHeader>
    <NAlert v-if="failure" type="error"
      >{{ failure }} <NButton size="small" @click="load">重新读取考试状态</NButton></NAlert
    >
    <p v-if="loading && !exam" class="muted" role="status">正在加载考试…</p>
    <template v-if="exam">
      <NAlert
        v-if="availability"
        :type="
          exam.status === 'CANCELLED' || exam.participant_status === 'CANCELLED' ? 'error' : 'info'
        "
        >{{ availability }}
        <p v-if="exam.cancelled_reason">取消原因：{{ exam.cancelled_reason }}</p></NAlert
      >
      <SurfacePanel title="考试安排">
        <dl class="exam-facts">
          <div>
            <dt>开放时间（上海）</dt>
            <dd>{{ examTime(exam.start_at) }} — {{ examTime(exam.end_at) }}</dd>
          </div>
          <div>
            <dt>单次时长</dt>
            <dd>
              {{
                exam.duration_seconds ? `${Math.ceil(exam.duration_seconds / 60)} 分钟` : '未配置'
              }}
            </dd>
          </div>
          <div>
            <dt>作答机会</dt>
            <dd>已使用 {{ exam.used_attempts }} / {{ exam.max_attempts }} 次</dd>
            <p>剩余 {{ exam.remaining_attempts }} 次</p>
          </div>
          <div>
            <dt>试卷总分</dt>
            <dd>{{ exam.total_score }} 分</dd>
          </div>
        </dl>
      </SurfacePanel>
      <SurfacePanel title="作答说明">
        <p class="exam-description">{{ exam.description || '本场考试暂无补充说明。' }}</p>
        <ul class="attempt-rules">
          <li>点击开始才使用一次机会；已有进行中的作答会恢复，继续作答不额外计次。</li>
          <li>实际截止时间取单次时长与考试结束时间中较早的一项。关闭页面、刷新和断网不会暂停。</li>
          <li>选择答案会自动保存，简答停止输入后保存。交卷前请核对保存状态。</li>
          <li>截止后仅服务器已保存答案计入答卷，未上传的本地内容不计入。</li>
        </ul>
        <div class="detail-start">
          <NButton
            v-if="exam.can_start"
            type="primary"
            :loading="starting"
            :disabled="uncertain"
            @click="start"
            >{{ exam.current_attempt_status === 'IN_PROGRESS' ? '继续作答' : '开始作答' }}</NButton
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
          <span v-if="exam.can_start" class="muted">{{
            exam.current_attempt_status === 'IN_PROGRESS'
              ? '恢复当前答卷，截止时间保持不变。'
              : '开始后立即计时。请确认已准备好。'
          }}</span>
        </div>
      </SurfacePanel>
    </template>
  </div>
</template>

<style scoped>
.exam-facts {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 24px;
  margin: 0;
}
dt {
  font-size: 13px;
  color: var(--color-muted);
  margin-bottom: 8px;
}
dd {
  margin: 0;
  line-height: 1.7;
  font-weight: 600;
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
</style>
