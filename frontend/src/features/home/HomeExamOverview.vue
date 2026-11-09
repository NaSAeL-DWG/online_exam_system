<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { NAlert, NButton } from 'naive-ui'
import { errorMessage } from '../../api/client'
import { examsApi, examStatusLabels, type ExamSummary } from '../../api/exams'
import { gradingApi, taskStatusLabels, type GradingTaskSummary } from '../../api/grading'
import { examTime } from '../attempts/examAvailability'
import { useAuthStore } from '../../stores/auth'
import SurfacePanel from '../../components/ui/SurfacePanel.vue'
import StatusBadge from '../../components/ui/StatusBadge.vue'
import LoadingSkeleton from '../../components/ui/LoadingSkeleton.vue'

const auth = useAuthStore()
const loading = ref(true)
const failure = ref('')
const staffExams = ref<ExamSummary[]>([])
const tasks = ref<GradingTaskSummary[]>([])
const pendingCount = ref(0)
const examCount = ref(0)
const waitingCount = ref(0)
const activeCount = ref(0)
const completedCount = ref(0)
const teacher = computed(() => auth.user?.user_type === 'TEACHER')
const metrics = computed(() => [
  { label: '可管理考试', value: examCount.value, unit: '场' },
  { label: teacher.value ? '我的待阅卷' : '等待指派', value: waitingCount.value, unit: '份' },
  { label: teacher.value ? '我的阅卷中' : '待完成阅卷', value: activeCount.value, unit: '份' },
  { label: teacher.value ? '我的已完成' : '已完成阅卷', value: completedCount.value, unit: '份' },
])

async function load(): Promise<void> {
  loading.value = true
  failure.value = ''
  try {
    const exams = examsApi.list({ page: 1, page_size: 4 })
    if (teacher.value) {
      const [recent, pending, active, completed] = await Promise.all([
        exams,
        gradingApi.tasks({
          page: 1,
          page_size: 4,
          status: 'PENDING',
          assigned_teacher_id: auth.user!.id,
        }),
        gradingApi.tasks({
          page: 1,
          page_size: 4,
          status: 'IN_PROGRESS',
          assigned_teacher_id: auth.user!.id,
        }),
        gradingApi.tasks({
          page: 1,
          page_size: 1,
          status: 'COMPLETED',
          assigned_teacher_id: auth.user!.id,
        }),
      ])
      staffExams.value = recent.items
      examCount.value = recent.total
      tasks.value = [...active.items, ...pending.items].slice(0, 4)
      pendingCount.value = pending.total + active.total
      waitingCount.value = pending.total
      activeCount.value = active.total
      completedCount.value = completed.total
    } else {
      const [recent, unassigned, pending, active, completed] = await Promise.all([
        exams,
        gradingApi.tasks({ page: 1, page_size: 1, status: 'UNASSIGNED' }),
        gradingApi.tasks({ page: 1, page_size: 1, status: 'PENDING' }),
        gradingApi.tasks({ page: 1, page_size: 1, status: 'IN_PROGRESS' }),
        gradingApi.tasks({ page: 1, page_size: 1, status: 'COMPLETED' }),
      ])
      staffExams.value = recent.items
      examCount.value = recent.total
      waitingCount.value = unassigned.total
      activeCount.value = pending.total + active.total
      completedCount.value = completed.total
    }
  } catch (error) {
    failure.value = errorMessage(error)
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <section class="home-exam-overview" aria-label="考试与待办">
    <LoadingSkeleton v-if="loading" variant="detail" :rows="3" label="正在读取考试与待办" />
    <NAlert v-else-if="failure" type="error" title="考试与待办暂时无法加载">
      {{ failure }} <NButton size="small" @click="load">重新加载</NButton>
    </NAlert>
    <template v-else>
      <section v-if="teacher" class="staff-priority" aria-label="优先阅卷任务">
        <div class="staff-priority-copy">
          <StatusBadge label="待完成阅卷" tone="info" />
          <span v-if="tasks[0]" class="priority-exam">{{ tasks[0].exam_title }}</span>
          <h2>
            {{ pendingCount ? `还有 ${pendingCount} 份答卷等待评分` : '当前阅卷任务已处理完毕' }}
          </h2>
          <p>人工阅卷完成后，核对全部有效作答再公布结果。</p>
          <span class="priority-meta">{{
            tasks[0]
              ? `优先处理：${tasks[0].student.real_name} · 第 ${tasks[0].attempt_no} 次作答`
              : '可以开始准备下一场考试。'
          }}</span>
        </div>
        <div class="staff-priority-action">
          <small>当前优先任务</small><strong>{{ pendingCount }}<small> 份待阅</small></strong
          ><RouterLink class="priority-button" to="/staff/grading-tasks"
            >进入阅卷工作台 →</RouterLink
          >
        </div>
      </section>
      <div class="staff-metrics" aria-label="考试与阅卷统计">
        <div v-for="metric in metrics" :key="metric.label">
          <span>{{ metric.label }}</span
          ><strong
            >{{ metric.value }}<small>{{ metric.unit }}</small></strong
          >
        </div>
      </div>
      <div class="staff-home-grid" :class="{ 'staff-home-grid--admin': !teacher }">
        <SurfacePanel
          :title="teacher ? '近期考试' : '考试与阅卷进度'"
          description="按近期创建顺序展示，进入考试查看完整安排与阅卷进度。"
        >
          <template #actions><RouterLink to="/staff/exams">全部考试 →</RouterLink></template>
          <div v-if="staffExams.length" class="staff-exam-list">
            <article v-for="exam in staffExams" :key="exam.id">
              <div>
                <h3>{{ exam.title }}</h3>
                <p>{{ examTime(exam.start_at) }} — {{ examTime(exam.end_at) }}</p>
                <span class="exam-scope"
                  >{{ exam.audience_type === 'PUBLIC' ? '公开考试' : '限定名单' }} · 总分
                  {{ exam.total_score }} 分</span
                >
              </div>
              <StatusBadge
                :label="examStatusLabels[exam.status]"
                :tone="
                  exam.status === 'RELEASED'
                    ? 'info'
                    : exam.status === 'RESULTS_PUBLISHED'
                      ? 'success'
                      : 'neutral'
                "
              />
              <RouterLink :to="`/staff/exams/${exam.id}`">{{
                exam.status === 'DRAFT' ? '配置考试' : '查看考试'
              }}</RouterLink>
            </article>
          </div>
          <p v-else class="home-empty">暂无考试安排，可以从考试管理中创建考试。</p>
        </SurfacePanel>
        <slot v-if="teacher" name="preparation" />
      </div>
      <p v-if="!teacher" class="staff-role-note">
        <strong>管理员职责</strong
        >维护考试与参考名单、查看阅卷进度并管理结果公布；人工评分由阅卷教师完成。
      </p>
      <div v-if="teacher" class="staff-tasks">
        <SurfacePanel
          title="我的阅卷待办"
          :description="`待阅与阅卷中共 ${pendingCount} 份，优先继续已开始的答卷。`"
        >
          <template #actions
            ><RouterLink to="/staff/grading-tasks">全部任务 →</RouterLink></template
          >
          <div v-if="tasks.length" class="home-record-list">
            <article v-for="task in tasks" :key="task.id" class="home-record">
              <div class="home-record-copy">
                <h3>{{ task.exam_title }}</h3>
                <p>{{ task.student.real_name }} · 第 {{ task.attempt_no }} 次作答</p>
              </div>
              <StatusBadge :label="taskStatusLabels[task.status]" tone="info" />
              <RouterLink :to="`/staff/attempts/${task.attempt_id}`">{{
                task.can_grade ? '进入阅卷' : '查看答卷'
              }}</RouterLink>
            </article>
          </div>
          <p v-else class="home-empty">当前没有等待你处理的阅卷任务。</p>
        </SurfacePanel>
      </div>
    </template>
  </section>
</template>
<style scoped>
.home-exam-overview {
  gap: 24px;
}
.staff-priority {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 250px;
  border: 1px solid var(--blue-200);
  border-left: 4px solid var(--blue-600);
  background: var(--color-surface);
}
.staff-priority-copy {
  padding: 28px;
}
.priority-exam {
  margin-left: 12px;
  font-size: 12px;
  color: var(--color-muted);
}
.staff-priority h2 {
  margin: 16px 0 12px;
  font-size: 24px;
  letter-spacing: -0.6px;
}
.staff-priority p {
  margin: 0 0 18px;
  color: var(--color-muted);
  font-size: 13px;
  line-height: 1.8;
}
.priority-meta {
  font-size: 12px;
  color: var(--color-muted);
}
.staff-priority-action {
  padding: 28px;
  border-left: 1px solid var(--blue-200);
  background: var(--blue-50);
  display: flex;
  flex-direction: column;
  justify-content: center;
}
.staff-priority-action > small {
  color: var(--color-muted);
  font-size: 12px;
}
.staff-priority-action strong {
  margin: 4px 0 18px;
  font-size: 36px;
  color: var(--blue-700);
  font-family: Consolas, monospace;
  font-weight: 400;
}
.staff-priority-action strong small {
  font-size: 14px;
}
.priority-button {
  padding: 10px 12px;
  text-align: center;
  background: var(--color-primary);
  color: white;
  font-size: 12px;
  border-radius: 2px;
}
.staff-metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  background: var(--color-surface);
  border: 1px solid var(--color-border);
}
.staff-metrics > div {
  padding: 22px 24px;
  border-right: 1px solid var(--color-border);
}
.staff-metrics > div:last-child {
  border-right: 0;
}
.staff-metrics span {
  color: var(--color-muted);
  font-size: 12px;
}
.staff-metrics strong {
  display: block;
  margin-top: 8px;
  font-size: 29px;
  font-weight: 500;
  color: var(--blue-700);
  font-variant-numeric: tabular-nums;
}
.staff-metrics small {
  font-size: 11px;
  color: var(--color-muted);
  margin-left: 7px;
}
.staff-home-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.6fr) minmax(280px, 1fr);
  gap: 24px;
}
.staff-home-grid--admin {
  grid-template-columns: minmax(0, 1fr);
}
.staff-exam-list article {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  align-items: center;
  gap: 16px;
  padding: 20px 0;
  border-bottom: 1px solid var(--color-border);
  font-size: 12px;
}
.staff-exam-list article:first-child {
  padding-top: 0;
}
.staff-exam-list article:last-child {
  border-bottom: 0;
  padding-bottom: 0;
}
.staff-exam-list h3 {
  margin: 0 0 8px;
  font-size: 14px;
  font-weight: 600;
  overflow-wrap: anywhere;
}
.staff-exam-list p {
  margin: 0 0 5px;
  color: var(--color-muted);
  font-size: 12px;
}
.exam-scope {
  color: var(--color-muted);
  font-size: 11px;
}
.staff-role-note {
  padding: 18px 22px;
  margin: 0;
  background: var(--blue-50);
  border: 1px solid var(--blue-200);
  font-size: 13px;
  line-height: 1.8;
  color: var(--color-muted);
}
.staff-role-note strong {
  display: block;
  color: var(--color-text);
  margin-bottom: 6px;
}
@media (max-width: 900px) {
  .staff-home-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
@media (max-width: 600px) {
  .staff-priority {
    grid-template-columns: 1fr;
  }
  .staff-priority-copy {
    padding: 22px;
  }
  .staff-priority h2 {
    font-size: 21px;
  }
  .staff-priority-action {
    padding: 18px 22px;
    border-left: 0;
    border-top: 1px solid var(--blue-200);
    display: grid;
    grid-template-columns: 1fr 1fr;
    align-items: center;
    gap: 4px 12px;
  }
  .staff-priority-action strong {
    grid-column: 1;
    margin: 0;
    font-size: 30px;
  }
  .priority-button {
    grid-column: 2;
    grid-row: 1 / 3;
  }
  .staff-metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .staff-metrics > div {
    padding: 18px;
  }
  .staff-metrics > div:nth-child(2) {
    border-right: 0;
  }
  .staff-metrics > div:nth-child(-n + 2) {
    border-bottom: 1px solid var(--color-border);
  }
  .staff-exam-list article {
    grid-template-columns: minmax(0, 1fr) auto;
  }
  .staff-exam-list article > div {
    grid-column: 1 / -1;
  }
  .staff-exam-list article > a {
    text-align: right;
  }
}
</style>
