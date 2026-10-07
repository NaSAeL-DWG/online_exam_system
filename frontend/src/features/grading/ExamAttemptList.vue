<script setup lang="ts">
import { NAlert, NButton } from 'naive-ui'
import { gradingApi, gradingStatusLabels, taskStatusLabels } from '../../api/grading'
import { usePagedList } from '../../composables/usePagedList'
import StatusBadge from '../../components/ui/StatusBadge.vue'
import ListPager from '../../components/ListPager.vue'
import './grading.css'
const props = defineProps<{ examId: string }>()
const { items, page, total, query, loading, failure, load, changePage } = usePagedList((query) =>
  gradingApi.attempts(props.examId, query),
)
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
  <div class="table-region" :aria-busy="loading">
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
              :tone="attempt.grading_status === 'GRADED' ? 'success' : 'warning'"
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
          <td><RouterLink :to="`/staff/attempts/${attempt.id}`">查看答卷 →</RouterLink></td>
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
</template>
