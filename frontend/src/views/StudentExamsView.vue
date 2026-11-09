<script setup lang="ts">
import { computed, ref } from 'vue'
import { NAlert, NButton } from 'naive-ui'
import { studentExamsApi } from '../api/studentExams'
import { usePagedList } from '../composables/usePagedList'
import PageHeader from '../components/ui/PageHeader.vue'
import SurfacePanel from '../components/ui/SurfacePanel.vue'
import StatusBadge from '../components/ui/StatusBadge.vue'
import ListPager from '../components/ListPager.vue'
import LoadingSkeleton from '../components/ui/LoadingSkeleton.vue'
import { examPhase, examTime } from '../features/attempts/examAvailability'

const { items, page, total, query, failure, loading, load, changePage } = usePagedList(
  studentExamsApi.list,
)
const selectedStatus = ref('全部考试')
const statuses = ['全部考试', '进行中', '可参加', '未开始', '已结束']
function statusOf(exam: (typeof items.value)[number]): string {
  const phase = examPhase(exam)
  if (phase === '作答中') return '进行中'
  if (phase === '未开始') return '未开始'
  if (phase === '已结束') return '已结束'
  return phase
}
const displayedExams = computed(() =>
  items.value
    .filter(
      (exam) => selectedStatus.value === '全部考试' || statusOf(exam) === selectedStatus.value,
    )
    .sort((left, right) => {
      const rank = (exam: (typeof items.value)[number]) =>
        exam.current_attempt_status === 'IN_PROGRESS' ? 0 : exam.can_start ? 1 : 2
      return rank(left) - rank(right)
    }),
)
</script>

<template>
  <div class="page-stack">
    <PageHeader
      eyebrow="EXAM / MY EXAMS"
      title="我的考试"
      description="优先处理正在作答的考试，再查看可参加及即将开始的考试。"
    />
    <NAlert v-if="failure" type="error"
      >{{ failure }} <NButton size="small" @click="load">重新加载考试</NButton></NAlert
    >
    <div class="exam-tabs" role="tablist" aria-label="本页考试状态">
      <button
        v-for="status in statuses"
        :key="status"
        type="button"
        role="tab"
        :aria-selected="selectedStatus === status"
        :class="{ active: selectedStatus === status }"
        @click="selectedStatus = status"
      >
        {{ status
        }}<span>{{
          status === '全部考试'
            ? items.length
            : items.filter((exam) => statusOf(exam) === status).length
        }}</span>
      </button>
    </div>
    <form class="toolbar" @submit.prevent="changePage(1)">
      <input
        v-model="query"
        class="form-control toolbar-search"
        aria-label="搜索我的考试"
        placeholder="搜索考试名称"
      />
      <NButton attr-type="submit" :loading="loading">查询考试</NButton>
      <span class="toolbar-meta"
        >共 {{ total }} 场考试<span v-if="total > 20"> · 状态筛选仅作用于当前页</span></span
      >
    </form>
    <SurfacePanel class="exam-list-panel">
      <div class="student-exam-list" :aria-busy="loading">
        <LoadingSkeleton v-if="loading" label="正在加载我的考试" />
        <article v-for="exam in displayedExams" :key="exam.id" class="student-exam-row">
          <div class="student-exam-copy">
            <div class="exam-title-row">
              <RouterLink :to="`/student/exams/${exam.id}`" class="student-exam-title">{{
                exam.title
              }}</RouterLink>
              <StatusBadge
                :class="{ 'exam-status-current': exam.current_attempt_status === 'IN_PROGRESS' }"
                :label="examPhase(exam)"
                :tone="
                  exam.status === 'CANCELLED' || exam.participant_status === 'CANCELLED'
                    ? 'danger'
                    : exam.can_start
                      ? 'info'
                      : 'neutral'
                "
              />
            </div>
            <p>
              {{
                exam.duration_seconds
                  ? `${Math.ceil(exam.duration_seconds / 60)} 分钟`
                  : '时长未配置'
              }}
              · 满分 {{ exam.total_score }} 分
              <span
                >已使用 {{ exam.used_attempts }} / {{ exam.max_attempts }} 次 · 剩余
                {{ exam.remaining_attempts }} 次</span
              >
            </p>
          </div>
          <div class="student-exam-date">
            <span>考试时间（上海）</span><strong>{{ examTime(exam.start_at) }}</strong
            ><span>至 {{ examTime(exam.end_at) }}</span>
          </div>
          <div class="student-exam-action">
            <RouterLink
              :to="
                exam.current_attempt_status === 'IN_PROGRESS' && exam.current_attempt_id
                  ? `/student/attempts/${exam.current_attempt_id}`
                  : `/student/exams/${exam.id}`
              "
              class="exam-action-link"
              :class="{ primary: exam.current_attempt_status === 'IN_PROGRESS' }"
              >{{ exam.current_attempt_status === 'IN_PROGRESS' ? '继续作答' : '查看详情' }}
              <span aria-hidden="true">→</span></RouterLink
            >
          </div>
        </article>
        <p v-if="!loading && !displayedExams.length" class="empty-list muted">
          {{ loading ? '正在加载考试…' : '暂无可查看的考试。' }}
        </p>
      </div>
      <ListPager
        label="考试"
        :page="page"
        :page-size="20"
        :total="total"
        :loading="loading"
        @change="changePage"
      />
    </SurfacePanel>
    <p class="muted exam-start-note">仅点击开始作答才会使用一次考试机会。</p>
  </div>
</template>

<style scoped>
.exam-tabs {
  display: flex;
  gap: 26px;
  border-bottom: 1px solid var(--color-border);
  overflow-x: auto;
}
.exam-tabs button {
  padding: 12px 0;
  border: 0;
  border-bottom: 2px solid transparent;
  background: none;
  color: var(--color-muted);
  white-space: nowrap;
  cursor: pointer;
}
.exam-tabs button.active {
  border-bottom-color: var(--blue-700);
  color: var(--blue-700);
  font-weight: 600;
}
.exam-start-note {
  margin: 0;
  font-size: 12px;
}
.exam-status-current {
  background: var(--blue-600);
  border-color: var(--blue-600);
  color: white;
}
.exam-tabs span {
  margin-left: 7px;
  font:
    11px Consolas,
    monospace;
  color: var(--color-muted);
}
.toolbar {
  margin-bottom: 0;
}
.toolbar-search {
  max-width: 360px;
}
.exam-list-panel :deep(.surface-panel-body) {
  padding: 0;
}
.student-exam-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 190px 110px;
  align-items: center;
  justify-content: space-between;
  gap: 22px;
  padding: 22px 24px;
  border-bottom: 1px solid var(--color-border);
}
.student-exam-row:last-child {
  border-bottom: 0;
}
.exam-title-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
}
.student-exam-date {
  display: grid;
  gap: 6px;
  font-size: 12px;
  color: var(--color-muted);
}
.student-exam-date strong {
  color: var(--color-text);
  font-size: 13px;
  font-weight: 500;
}
.exam-action-link {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border: 1px solid var(--color-border);
  border-radius: 2px;
  padding: 10px 12px;
  color: var(--color-text);
  white-space: nowrap;
}
.exam-action-link.primary {
  background: var(--color-primary);
  border-color: var(--color-primary);
  color: white;
}
.exam-list-panel :deep(.list-pager) {
  padding: 16px 24px;
}
.student-exam-copy {
  min-width: 0;
}
.student-exam-title {
  color: var(--color-text);
  font-size: 15px;
  font-weight: 600;
  overflow-wrap: anywhere;
}
.student-exam-copy p {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
  margin: 8px 0;
  font-size: 13px;
  color: var(--color-muted);
}
.student-exam-copy > span {
  font-size: 13px;
}
.student-exam-action {
  display: flex;
  align-items: center;
  gap: 24px;
  flex-shrink: 0;
  font-size: 13px;
}
.empty-list {
  text-align: center;
  padding: 30px 0;
}
@media (max-width: 650px) {
  .student-exam-row {
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 14px;
    padding: 20px;
  }
  .student-exam-copy {
    grid-column: 1 / -1;
  }
  .student-exam-action {
    width: 100%;
    justify-content: space-between;
  }
}
</style>
