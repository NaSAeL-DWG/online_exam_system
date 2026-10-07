<script setup lang="ts">
import { NAlert, NButton } from 'naive-ui'
import { studentExamsApi } from '../api/studentExams'
import { usePagedList } from '../composables/usePagedList'
import PageHeader from '../components/ui/PageHeader.vue'
import SurfacePanel from '../components/ui/SurfacePanel.vue'
import StatusBadge from '../components/ui/StatusBadge.vue'
import ListPager from '../components/ListPager.vue'
import { examPhase, examTime } from '../features/attempts/examAvailability'

const { items, page, total, query, failure, loading, load, changePage } = usePagedList(
  studentExamsApi.list,
)
</script>

<template>
  <div class="page-stack">
    <PageHeader title="我的考试" description="阅读考试说明，确认时间和剩余机会后开始作答。" />
    <NAlert v-if="failure" type="error"
      >{{ failure }} <NButton size="small" @click="load">重新加载考试</NButton></NAlert
    >
    <SurfacePanel>
      <form class="toolbar" @submit.prevent="changePage(1)">
        <input
          v-model="query"
          class="form-control toolbar-search"
          aria-label="搜索我的考试"
          placeholder="搜索考试名称"
        />
        <NButton attr-type="submit" :loading="loading">查询考试</NButton>
        <span class="toolbar-meta">共 {{ total }} 场考试</span>
      </form>
      <p class="muted attempt-list-note">仅点击开始作答才会使用一次考试机会。</p>
      <div class="student-exam-list" :aria-busy="loading">
        <article v-for="exam in items" :key="exam.id" class="student-exam-row">
          <div class="student-exam-copy">
            <RouterLink :to="`/student/exams/${exam.id}`" class="student-exam-title">{{
              exam.title
            }}</RouterLink>
            <p>
              {{ examTime(exam.start_at) }} — {{ examTime(exam.end_at) }} ·
              {{
                exam.duration_seconds
                  ? `${Math.ceil(exam.duration_seconds / 60)} 分钟`
                  : '时长未配置'
              }}
            </p>
            <span class="muted"
              >已使用 {{ exam.used_attempts }} / {{ exam.max_attempts }} 次 · 剩余
              {{ exam.remaining_attempts }} 次</span
            >
          </div>
          <div class="student-exam-action">
            <StatusBadge
              :label="examPhase(exam)"
              :tone="
                exam.status === 'CANCELLED' || exam.participant_status === 'CANCELLED'
                  ? 'danger'
                  : exam.can_start
                    ? 'success'
                    : 'neutral'
              "
            />
            <RouterLink :to="`/student/exams/${exam.id}`"
              >查看考试 <span aria-hidden="true">→</span></RouterLink
            >
          </div>
        </article>
        <p v-if="!items.length" class="empty-list muted">
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
  </div>
</template>

<style scoped>
.attempt-list-note {
  margin: 0 0 16px;
  font-size: 13px;
}
.student-exam-list {
  border-top: 1px solid var(--color-border);
}
.student-exam-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 22px;
  padding: 22px 0;
  border-bottom: 1px solid var(--color-border);
}
.student-exam-copy {
  min-width: 0;
}
.student-exam-title {
  color: var(--color-text);
  font-size: 17px;
  font-weight: 650;
  overflow-wrap: anywhere;
}
.student-exam-copy p {
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
    align-items: flex-start;
    flex-direction: column;
    gap: 14px;
  }
  .student-exam-action {
    width: 100%;
    justify-content: space-between;
  }
}
</style>
