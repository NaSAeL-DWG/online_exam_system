<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { NAlert, NButton } from 'naive-ui'
import { gradingApi, taskStatusLabels } from '../api/grading'
import { useAuthStore } from '../stores/auth'
import { usePagedList } from '../composables/usePagedList'
import PageHeader from '../components/ui/PageHeader.vue'
import SurfacePanel from '../components/ui/SurfacePanel.vue'
import LoadingSkeleton from '../components/ui/LoadingSkeleton.vue'
import StatusBadge from '../components/ui/StatusBadge.vue'
import ListPager from '../components/ListPager.vue'
import { errorMessage } from '../api/client'
import '../features/grading/grading.css'

const auth = useAuthStore()
const metrics = ref<{ label: string; value: number }[]>([])
const metricsFailure = ref('')
const scope = ref<'mine' | 'unassigned' | 'completed' | 'all'>(
  auth.user?.user_type === 'ADMIN' ? 'unassigned' : 'mine',
)
const { items, page, total, pageSize, loading, failure, load, changePage } = usePagedList((query) =>
  gradingApi.tasks({
    ...query,
    assigned_teacher_id: scope.value === 'mine' ? auth.user!.id : undefined,
    status:
      scope.value === 'unassigned'
        ? 'UNASSIGNED'
        : scope.value === 'completed'
          ? 'COMPLETED'
          : undefined,
  }),
)
function selectScope(value: typeof scope.value): void {
  scope.value = value
  page.value = 1
  void load()
}
async function loadMetrics(): Promise<void> {
  metricsFailure.value = ''
  try {
    const assigned_teacher_id = auth.user?.user_type === 'TEACHER' ? auth.user.id : undefined
    const base = { page: 1, page_size: 1, assigned_teacher_id }
    const [all, completed, pending, active] = await Promise.all([
      gradingApi.tasks(base),
      gradingApi.tasks({ ...base, status: 'COMPLETED' }),
      gradingApi.tasks({ ...base, status: 'PENDING' }),
      gradingApi.tasks({ ...base, status: 'IN_PROGRESS' }),
    ])
    metrics.value = [
      { label: '分配给我', value: all.total },
      { label: '已完成', value: completed.total },
      { label: '待阅卷', value: pending.total },
      { label: '阅卷中', value: active.total },
    ]
  } catch (error) {
    metricsFailure.value = errorMessage(error)
  }
}
function refresh(): void {
  void load()
  void loadMetrics()
}
onMounted(loadMetrics)
</script>

<template>
  <div class="page-stack">
    <PageHeader
      eyebrow="GRADING / MY TASKS"
      title="阅卷工作台"
      description="优先处理分配给你的答卷，整卷完成后计入已阅数量。"
    >
      <template #actions
        ><StatusBadge :label="`${auth.user?.real_name} · 阅卷教师`" tone="neutral" /><NButton
          :loading="loading"
          @click="refresh"
          >刷新任务</NButton
        ></template
      >
    </PageHeader>
    <NAlert v-if="metricsFailure" type="error"
      >统计暂时无法读取：{{ metricsFailure }}
      <NButton size="small" @click="loadMetrics">重试统计</NButton></NAlert
    >
    <div v-else-if="metrics.length" class="grading-metrics" aria-label="我的阅卷统计">
      <div v-for="metric in metrics" :key="metric.label">
        <span>{{ metric.label }}</span
        ><strong>{{ metric.value }}<small>份</small></strong>
      </div>
    </div>
    <div class="list-filter" aria-label="任务范围">
      <NButton
        :type="scope === 'mine' ? 'primary' : 'default'"
        :aria-pressed="scope === 'mine'"
        @click="selectScope('mine')"
        >我的任务</NButton
      >
      <NButton
        :type="scope === 'unassigned' ? 'primary' : 'default'"
        :aria-pressed="scope === 'unassigned'"
        @click="selectScope('unassigned')"
        >待指派</NButton
      >
      <NButton
        :type="scope === 'completed' ? 'primary' : 'default'"
        :aria-pressed="scope === 'completed'"
        @click="selectScope('completed')"
        >已完成</NButton
      >
      <NButton
        :type="scope === 'all' ? 'primary' : 'default'"
        :aria-pressed="scope === 'all'"
        @click="selectScope('all')"
        >全部任务</NButton
      >
    </div>
    <SurfacePanel class="grading-task-panel">
      <NAlert v-if="failure" type="error"
        >{{ failure }} <NButton size="small" @click="load">重试加载任务</NButton></NAlert
      >
      <LoadingSkeleton v-if="loading" variant="table" label="正在读取阅卷任务" />
      <div v-else-if="items.length" class="table-region">
        <table class="grading-table">
          <thead>
            <tr>
              <th>考试与答卷</th>
              <th>学生</th>
              <th>指定教师 / 首阅</th>
              <th>任务状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="task in items" :key="task.id">
              <td>
                <strong>{{ task.exam_title }}</strong
                ><span class="table-subtitle task-code"
                  >{{ task.attempt_id }} · 第 {{ task.attempt_no }} 次作答</span
                >
              </td>
              <td>
                {{ task.student.real_name
                }}<span class="table-subtitle">{{ task.student.login_name }}</span>
              </td>
              <td>
                {{ task.assigned_teacher?.real_name || '等待管理员指派'
                }}<span class="table-subtitle">{{
                  task.first_review_completed_at ? '整卷首阅已完成' : '整卷首阅尚未完成'
                }}</span>
              </td>
              <td>
                <StatusBadge
                  :label="taskStatusLabels[task.status]"
                  :tone="
                    task.status === 'COMPLETED'
                      ? 'success'
                      : task.status === 'UNASSIGNED'
                        ? 'warning'
                        : 'info'
                  "
                />
              </td>
              <td>
                <RouterLink :to="`/staff/attempts/${task.attempt_id}`"
                  >{{ task.can_grade ? '开始阅卷' : '查看答卷' }} →</RouterLink
                >
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p v-else-if="!failure" class="muted">当前范围暂无阅卷任务。</p>
      <ListPager
        label="阅卷任务"
        :page="page"
        :total="total"
        :page-size="pageSize"
        :loading="loading"
        @change="changePage"
      />
    </SurfacePanel>
    <p class="grading-help">
      考试结束后自动分配整卷任务；首次整卷阅完前由指定教师独占评分，指定教师不可用时由管理员改派。
    </p>
  </div>
</template>
<style scoped>
.grading-metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  border: 1px solid var(--color-border);
  background: var(--color-surface);
}
.grading-metrics > div {
  padding: 22px 24px;
  border-right: 1px solid var(--color-border);
}
.grading-metrics > div:last-child {
  border-right: 0;
}
.grading-metrics span {
  font-size: 12px;
  color: var(--color-muted);
}
.grading-metrics strong {
  display: block;
  margin-top: 8px;
  color: var(--blue-700);
  font-size: 29px;
  font-weight: 500;
  font-variant-numeric: tabular-nums;
}
.grading-metrics small {
  font-size: 11px;
  margin-left: 7px;
  color: var(--color-muted);
}
.list-filter {
  margin: 0;
}
.grading-task-panel :deep(.surface-panel-body) {
  padding: 0;
}
.grading-task-panel :deep(.list-pager) {
  padding: 16px 24px;
}
.grading-table {
  min-width: 800px;
}
.grading-table :is(th, td) {
  padding: 20px 24px;
}
.grading-table th:last-child,
.grading-table td:last-child {
  text-align: right;
}
.grading-table strong {
  font-size: 13px;
  font-weight: 600;
}
.task-code {
  max-width: 290px;
  overflow-wrap: anywhere;
  font:
    10px/1.8 Consolas,
    monospace;
}
.grading-help {
  margin: 0;
  color: var(--color-muted);
  font-size: 12px;
  line-height: 1.8;
}
@media (max-width: 600px) {
  .grading-metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .grading-metrics > div {
    padding: 18px;
  }
  .grading-metrics > div:nth-child(2) {
    border-right: 0;
  }
  .grading-metrics > div:nth-child(-n + 2) {
    border-bottom: 1px solid var(--color-border);
  }
}
</style>
