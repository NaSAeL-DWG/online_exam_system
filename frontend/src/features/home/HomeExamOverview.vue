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
const teacher = computed(() => auth.user?.user_type === 'TEACHER')

async function load(): Promise<void> {
  loading.value = true
  failure.value = ''
  try {
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
        <SurfacePanel title="近期考试" description="查看近期创建的考试，安排考试与检查阅卷进度。">
          <template #actions><RouterLink to="/staff/exams">全部考试 →</RouterLink></template>
          <div v-if="staffExams.length" class="home-record-list">
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
          </div>
          <p v-else class="home-empty">暂无考试安排，可以从考试管理中创建考试。</p>
        </SurfacePanel>
      </div>
    </template>
  </section>
</template>
