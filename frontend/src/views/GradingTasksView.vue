<script setup lang="ts">
import { ref } from 'vue'
import { NAlert, NButton } from 'naive-ui'
import { gradingApi, taskStatusLabels } from '../api/grading'
import { useAuthStore } from '../stores/auth'
import { usePagedList } from '../composables/usePagedList'
import PageHeader from '../components/ui/PageHeader.vue'
import SurfacePanel from '../components/ui/SurfacePanel.vue'
import StatusBadge from '../components/ui/StatusBadge.vue'
import ListPager from '../components/ListPager.vue'
import '../features/grading/grading.css'

const auth = useAuthStore()
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
</script>

<template>
  <div class="page-stack">
    <PageHeader
      title="阅卷工作台"
      description="按整份答卷处理非空简答题，首次整卷阅完前由指定教师独占评分。"
    >
      <template #actions><NButton :loading="loading" @click="load">刷新任务</NButton></template>
    </PageHeader>
    <SurfacePanel
      title="阅卷任务"
      description="考试结束后自动分配；指定教师不可用的任务等待管理员改派。"
    >
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
      <NAlert v-if="failure" type="error"
        >{{ failure }} <NButton size="small" @click="load">重试加载任务</NButton></NAlert
      >
      <p v-if="loading" class="muted" role="status">正在读取任务…</p>
      <div v-else-if="items.length" class="table-region">
        <table class="grading-table">
          <thead>
            <tr>
              <th>考试与答卷</th>
              <th>学生</th>
              <th>指定教师</th>
              <th>任务状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="task in items" :key="task.id">
              <td>
                {{ task.exam_title
                }}<span class="table-subtitle">第 {{ task.attempt_no }} 次作答</span>
              </td>
              <td>
                {{ task.student.real_name
                }}<span class="table-subtitle">{{ task.student.login_name }}</span>
              </td>
              <td>{{ task.assigned_teacher?.real_name || '等待管理员指派' }}</td>
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
  </div>
</template>
