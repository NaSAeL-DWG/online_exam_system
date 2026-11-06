<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { NAlert, NButton } from 'naive-ui'
import { errorMessage } from '../../api/client'
import { studentExamsApi, type StudentExam } from '../../api/studentExams'
import { examsApi, examStatusLabels, type ExamSummary } from '../../api/exams'
import { gradingApi, taskStatusLabels, type GradingTaskSummary } from '../../api/grading'
import { examPhase, examTime } from '../attempts/examAvailability'
import { useAuthStore } from '../../stores/auth'
import SurfacePanel from '../../components/ui/SurfacePanel.vue'
import StatusBadge from '../../components/ui/StatusBadge.vue'
import LoadingSkeleton from '../../components/ui/LoadingSkeleton.vue'
import AppIcon from '../../components/ui/AppIcon.vue'

const auth = useAuthStore()
const router = useRouter()
const loading = ref(true)
const failure = ref('')
const studentExams = ref<StudentExam[]>([])
const staffExams = ref<ExamSummary[]>([])
const tasks = ref<GradingTaskSummary[]>([])
const pendingCount = ref(0)
const student = computed(() => auth.user?.user_type === 'STUDENT')
const teacher = computed(() => auth.user?.user_type === 'TEACHER')

function examPriority(exam: StudentExam): number {
  const phase = examPhase(exam)
  if (phase === '作答中') return 0
  if (exam.can_start) return 1
  if (phase === '未开始') return 2
  return 3
}

const recentExams = computed(() =>
  [...studentExams.value].sort((a, b) => examPriority(a) - examPriority(b)).slice(0, 4),
)
const focusExam = computed(() => recentExams.value.find((exam) => examPriority(exam) < 3))

async function load(): Promise<void> {
  loading.value = true
  failure.value = ''
  try {
    if (student.value) {
      // 首页只呈现近期记录，不把当前分页数量冒充全局统计。
      studentExams.value = (await studentExamsApi.list({ page: 1, page_size: 20 })).items
    } else {
      const exams = examsApi.list({ page: 1, page_size: 4 })
      if (teacher.value) {
        const [recent, pending, active] = await Promise.all([
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
        ])
        staffExams.value = recent.items
        tasks.value = [...active.items, ...pending.items].slice(0, 4)
        pendingCount.value = pending.total + active.total
      } else {
        staffExams.value = (await exams).items
      }
    }
  } catch (error) {
    failure.value = errorMessage(error)
  } finally {
    loading.value = false
  }
}

function studentAction(exam: StudentExam): void {
  // 首页不直接消耗作答次数；首次参加仍先进入考试详情确认规则。
  const path =
    exam.current_attempt_status === 'IN_PROGRESS' && exam.current_attempt_id
      ? `/student/attempts/${exam.current_attempt_id}`
      : `/student/exams/${exam.id}`
  void router.push(path)
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
      <div v-if="student && focusExam" class="home-exam-focus">
        <div class="home-exam-focus-copy">
          <div class="home-exam-kicker"><AppIcon name="exam" :size="18" />当前考试任务</div>
          <h2>{{ focusExam.title }}</h2>
          <p>{{ examTime(focusExam.start_at) }} — {{ examTime(focusExam.end_at) }}</p>
          <div class="home-exam-focus-meta">
            <StatusBadge :label="examPhase(focusExam)" tone="info" />
            <span>作答时长 {{ Math.ceil((focusExam.duration_seconds ?? 0) / 60) }} 分钟</span>
            <span>剩余 {{ focusExam.remaining_attempts }} 次机会</span>
          </div>
        </div>
        <NButton type="primary" size="large" @click="studentAction(focusExam)">
          {{
            focusExam.current_attempt_status === 'IN_PROGRESS'
              ? '继续作答'
              : focusExam.can_start
                ? '查看并参加考试'
                : '查看考试安排'
          }}
          <template #icon><AppIcon name="arrow-right" :size="18" /></template>
        </NButton>
      </div>
      <div class="home-overview-grid" :class="{ 'home-overview-grid--split': teacher }">
        <SurfacePanel
          v-if="teacher"
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
        <SurfacePanel
          title="近期考试"
          :description="
            student
              ? '优先显示近期考试中可继续、可参加与即将开始的场次。'
              : '查看近期创建的考试，安排考试与检查阅卷进度。'
          "
        >
          <template #actions
            ><RouterLink :to="student ? '/student/exams' : '/staff/exams'"
              >全部考试 →</RouterLink
            ></template
          >
          <div v-if="student ? recentExams.length : staffExams.length" class="home-record-list">
            <template v-if="student">
              <article v-for="exam in recentExams" :key="exam.id" class="home-record">
                <div class="home-record-copy">
                  <h3>{{ exam.title }}</h3>
                  <p>{{ examTime(exam.start_at) }} — {{ examTime(exam.end_at) }}</p>
                </div>
                <StatusBadge
                  :label="examPhase(exam)"
                  :tone="examPriority(exam) < 2 ? 'info' : 'neutral'"
                />
                <RouterLink :to="`/student/exams/${exam.id}`">查看详情</RouterLink>
              </article>
            </template>
            <template v-else>
              <article v-for="exam in staffExams" :key="exam.id" class="home-record">
                <div class="home-record-copy">
                  <h3>{{ exam.title }}</h3>
                  <p>{{ examTime(exam.start_at) }} — {{ examTime(exam.end_at) }}</p>
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
                <RouterLink :to="`/staff/exams/${exam.id}`">管理考试</RouterLink>
              </article>
            </template>
          </div>
          <p v-else class="home-empty">
            暂无考试安排。{{
              student ? '新的考试发布后会显示在这里。' : '可以从考试管理中创建考试。'
            }}
          </p>
        </SurfacePanel>
      </div>
    </template>
  </section>
</template>
