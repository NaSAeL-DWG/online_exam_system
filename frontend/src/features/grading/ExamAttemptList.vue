<script setup lang="ts">
import { computed, ref } from 'vue'
import { NAlert, NButton } from 'naive-ui'
import {
  gradingApi,
  gradingStatusLabels,
  taskStatusLabels,
  type StaffAttemptDetail,
} from '../../api/grading'
import { errorMessage } from '../../api/client'
import { usePagedList } from '../../composables/usePagedList'
import StatusBadge from '../../components/ui/StatusBadge.vue'
import LoadingSkeleton from '../../components/ui/LoadingSkeleton.vue'
import ListPager from '../../components/ListPager.vue'
import './grading.css'
import { useAuthStore } from '../../stores/auth'
import ReassignTask from './ReassignTask.vue'
const auth = useAuthStore()
const canGrade = computed(() => auth.user?.user_type === 'TEACHER')
const isAdmin = computed(() => auth.user?.user_type === 'ADMIN')
const reassignment = ref<StaffAttemptDetail | null>(null)
const openingTask = ref<string | null>(null)
const reassignmentFailure = ref('')
const reassignmentSuccess = ref('')
const props = defineProps<{ examId: string }>()
const { items, page, total, query, loading, failure, load, changePage } = usePagedList((query) =>
  gradingApi.attempts(props.examId, query),
)
async function openReassignment(attemptId: string): Promise<void> {
  if (openingTask.value) return
  openingTask.value = attemptId
  reassignmentFailure.value = ''
  reassignmentSuccess.value = ''
  try {
    // 管理员在进度列表管理任务，答卷内容不进入评分工作区。
    const detail = await gradingApi.attempt(attemptId)
    if (detail.can_reassign) reassignment.value = detail
    else reassignmentFailure.value = '该任务当前不可改派，请刷新进度后重试。'
  } catch (error) {
    reassignmentFailure.value = errorMessage(error)
  } finally {
    openingTask.value = null
  }
}
function reassigned(): void {
  reassignment.value = null
  reassignmentSuccess.value = '阅卷任务已改派，已有题分和评分历史已保留。'
  void load()
}
</script>
<template>
  <form class="toolbar" @submit.prevent="changePage(1)">
    <input
      v-model="query"
      class="form-control toolbar-search"
      aria-label="搜索答卷学生"
      placeholder="搜索学生姓名或学号"
    />
    <NButton attr-type="submit" :loading="loading">查询答卷</NButton
    ><span class="toolbar-meta">全部有效作答，含多次提交</span>
  </form>
  <NAlert v-if="failure" type="error"
    >{{ failure }} <NButton size="small" @click="load">重试加载答卷</NButton></NAlert
  >
  <NAlert v-if="reassignmentFailure" class="form-alert" type="error">{{
    reassignmentFailure
  }}</NAlert>
  <NAlert v-if="reassignmentSuccess" class="form-alert" type="success">{{
    reassignmentSuccess
  }}</NAlert>
  <LoadingSkeleton v-if="loading && !items.length" variant="table" label="正在读取答卷进度" />
  <div v-else class="table-region" :aria-busy="loading">
    <table class="grading-table">
      <thead>
        <tr>
          <th>学生</th>
          <th>作答次数</th>
          <th>判分状态</th>
          <th>本次得分</th>
          <th>人工任务</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="attempt in items" :key="attempt.id">
          <td>
            {{ attempt.student.real_name
            }}<span class="table-subtitle">{{ attempt.student.login_name }}</span>
          </td>
          <td>第 {{ attempt.attempt_no }} 次</td>
          <td>
            <StatusBadge
              :label="
                attempt.status === 'IN_PROGRESS'
                  ? '作答中'
                  : gradingStatusLabels[attempt.grading_status]
              "
              :tone="
                attempt.status === 'IN_PROGRESS'
                  ? 'info'
                  : attempt.grading_status === 'GRADED'
                    ? 'success'
                    : 'warning'
              "
            />
          </td>
          <td>
            <strong
              v-if="attempt.grading_status === 'GRADED' && attempt.final_score !== null"
              class="score-value"
              >{{ attempt.final_score }} 分</strong
            ><span v-else class="muted">尚未形成总分</span>
          </td>
          <td>
            {{ attempt.task ? taskStatusLabels[attempt.task.status] : '无需人工任务或等待分配'
            }}<span v-if="attempt.task?.assigned_teacher" class="table-subtitle">{{
              attempt.task.assigned_teacher.real_name
            }}</span>
          </td>
          <td v-if="canGrade">
            <RouterLink :to="`/staff/attempts/${attempt.id}`">查看答卷 →</RouterLink>
          </td>
          <td v-else>
            <NButton
              v-if="isAdmin && attempt.task && !['COMPLETED', 'VOID'].includes(attempt.task.status)"
              size="small"
              :loading="openingTask === attempt.id"
              :disabled="openingTask !== null"
              @click="openReassignment(attempt.id)"
              >改派任务</NButton
            >
            <span v-else class="muted">—</span>
          </td>
        </tr>
        <tr v-if="!items.length">
          <td colspan="6" class="empty-state">
            {{ loading ? '正在读取答卷…' : '暂无有效答卷。' }}
          </td>
        </tr>
      </tbody>
    </table>
  </div>
  <ListPager
    label="答卷"
    :page="page"
    :total="total"
    :page-size="20"
    :loading="loading"
    @change="changePage"
  />
  <ReassignTask
    v-if="reassignment"
    :attempt="reassignment"
    @close="reassignment = null"
    @saved="reassigned"
    @refreshed="reassignment = $event"
  />
</template>
