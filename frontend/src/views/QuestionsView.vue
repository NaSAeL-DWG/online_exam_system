<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import { NAlert, NButton, NModal, useDialog } from 'naive-ui'
import { questionsApi, questionTypeLabels } from '../api/questions'
import ListPager from '../components/ListPager.vue'
import QuestionFields from '../components/QuestionFields.vue'
import PageHeader from '../components/ui/PageHeader.vue'
import SurfacePanel from '../components/ui/SurfacePanel.vue'
import StatusBadge from '../components/ui/StatusBadge.vue'
import AppIcon from '../components/ui/AppIcon.vue'
import { usePagedList } from '../composables/usePagedList'
import { useUnsavedChanges } from '../composables/useUnsavedChanges'
import { useQuestionEditor } from '../features/questions/useQuestionEditor'
import { difficultyLabels, questionSummary } from '../features/questions/questionDraft'

const filters = reactive({ subject: '', difficulty: '', tag: '', status: '', type: '' })
const { items, page, total, query, loading, failure, load, changePage } = usePagedList((query) =>
  questionsApi.list(query, filters),
)
const {
  visible,
  selected,
  form,
  saving,
  uploading,
  failure: editorFailure,
  conflict,
  dirty,
  create,
  edit,
  persist,
} = useQuestionEditor(load)
const questionFields = ref<InstanceType<typeof QuestionFields> | null>(null)
watch(visible, () => questionFields.value?.resetValidation())
async function saveQuestion(): Promise<void> {
  if (questionFields.value?.validate()) await persist()
}
const { confirmDiscard } = useUnsavedChanges(() => dirty.value)
async function closeEditor(): Promise<void> {
  if (!saving.value && !uploading.value && (await confirmDiscard())) visible.value = false
}
const dialog = useDialog()
function closeQuestion(): void {
  dialog.warning({
    title: '关闭题目',
    content: `关闭后不能新增组卷，已有试卷和考试仍保留题目。${dirty.value ? '尚未保存的修改不会应用到题目。' : ''}`,
    positiveText: '确认关闭',
    negativeText: '取消',
    onPositiveClick: () => persist('close'),
  })
}
function resetFilters(): void {
  query.value = ''
  Object.assign(filters, { subject: '', difficulty: '', tag: '', status: '', type: '' })
  changePage(1)
}
</script>

<template>
  <div class="page-stack">
    <PageHeader title="共享题库" description="按科目、题型和知识点查找并维护共享题目。">
      <template #actions
        ><NButton type="primary" @click="create"
          ><template #icon><AppIcon name="plus" :size="17" /></template>新建题目</NButton
        ></template
      >
    </PageHeader>
    <NAlert v-if="failure || (!visible && editorFailure)" type="error"
      >{{ failure || editorFailure }}
      <NButton size="small" @click="load">重新加载题库</NButton></NAlert
    >
    <SurfacePanel>
      <form class="filter-workspace" @submit.prevent="changePage(1)">
        <div class="search-line">
          <label class="search-box"
            ><AppIcon name="search" :size="17" /><input
              v-model="query"
              class="form-control"
              aria-label="搜索题目"
              placeholder="搜索题干内容" /></label
          ><NButton attr-type="submit" :loading="loading">查询题目</NButton
          ><NButton @click="resetFilters">重置</NButton>
        </div>
        <div class="filter-grid">
          <input
            class="form-control"
            v-model="filters.subject"
            aria-label="筛选科目"
            placeholder="全部科目"
          /><select class="form-control" v-model="filters.type" aria-label="筛选题型">
            <option value="">全部题型</option>
            <option v-for="(label, type) in questionTypeLabels" :key="type" :value="type">
              {{ label }}
            </option></select
          ><select class="form-control" v-model="filters.difficulty" aria-label="筛选难度">
            <option value="">全部难度</option>
            <option
              v-for="(label, difficulty) in difficultyLabels"
              :key="difficulty"
              :value="difficulty"
            >
              {{ label }}
            </option></select
          ><input
            class="form-control"
            v-model="filters.tag"
            aria-label="筛选知识点"
            placeholder="知识点标签"
          /><select class="form-control" v-model="filters.status" aria-label="筛选状态">
            <option value="">全部状态</option>
            <option value="ACTIVE">使用中</option>
            <option value="CLOSED">已关闭</option>
          </select>
        </div>
      </form>
      <div class="list-heading">
        <h2>题目列表</h2>
        <span class="muted">共 {{ total }} 道题</span>
      </div>
      <div class="table-region" :aria-busy="loading">
        <table class="question-table">
          <thead>
            <tr>
              <th>题目</th>
              <th>分类</th>
              <th>状态</th>
              <th class="action-cell">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in items" :key="item.id">
              <td>
                <p class="question-summary">{{ questionSummary(item.content) }}</p>
                <span class="question-type">{{ questionTypeLabels[item.type] }}</span>
              </td>
              <td>
                <strong>{{ item.subject }}</strong>
                <p class="row-meta">
                  {{ difficultyLabels[item.difficulty]
                  }}<template v-if="item.knowledge_tags.length">
                    · {{ item.knowledge_tags.join('、') }}</template
                  >
                </p>
              </td>
              <td>
                <StatusBadge
                  :label="item.status === 'ACTIVE' ? '使用中' : '已关闭'"
                  :tone="item.status === 'ACTIVE' ? 'success' : 'neutral'"
                />
              </td>
              <td class="action-cell"><NButton size="small" @click="edit(item)">编辑</NButton></td>
            </tr>
            <tr v-if="!items.length">
              <td colspan="4" class="empty-state">
                {{
                  loading
                    ? '正在加载题目…'
                    : failure
                      ? '题库暂时无法读取，请重试。'
                      : '没有找到题目，可调整筛选或新建题目。'
                }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <ListPager
        label="题库"
        :page="page"
        :page-size="20"
        :total="total"
        :loading="loading"
        @change="changePage"
      />
    </SurfacePanel>
    <NModal
      :show="visible"
      @update:show="closeEditor"
      preset="card"
      :title="selected ? '编辑题目' : '新建题目'"
      class="responsive-modal responsive-modal--editor"
      :mask-closable="false"
      :closable="!saving && !uploading"
      :close-on-esc="!saving && !uploading"
    >
      <NAlert v-if="editorFailure" class="form-alert" type="error"
        >{{ editorFailure }}
        <NButton v-if="conflict && selected" @click="edit(selected)"
          >重新加载最新题目</NButton
        ></NAlert
      >
      <form class="question-form" novalidate @submit.prevent="saveQuestion">
        <QuestionFields ref="questionFields" v-model="form" @uploading="uploading = $event" />
        <div class="editor-actions">
          <span class="muted">{{
            selected ? '修改将更新共享题库；既有考试快照保持不变。' : '保存后可用于手动组卷。'
          }}</span>
          <div class="action-buttons">
            <NButton
              v-if="selected?.status === 'ACTIVE'"
              type="warning"
              :disabled="saving || conflict || uploading"
              @click="closeQuestion"
              >关闭题目</NButton
            ><NButton
              attr-type="submit"
              type="primary"
              :loading="saving"
              :disabled="conflict || uploading"
              >保存题目</NButton
            >
          </div>
        </div>
      </form>
    </NModal>
  </div>
</template>
<style scoped>
.filter-workspace {
  display: grid;
  gap: 12px;
}
.search-line {
  display: flex;
  gap: 10px;
}
.search-box {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
  min-width: 0;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  padding-left: 12px;
  color: var(--color-muted);
}
.search-box input {
  border: 0;
  min-width: 0;
  background: transparent;
}
.filter-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 10px;
}
.list-heading {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin: 24px 0 12px;
}
.list-heading h2 {
  margin: 0;
  font-size: 15px;
}
.list-heading span {
  font-size: 13px;
}
.question-table {
  min-width: 650px;
  width: 100%;
  border-collapse: collapse;
  text-align: left;
}
th {
  background: var(--color-bg);
  color: var(--color-muted);
  font-size: 12px;
  font-weight: 500;
}
th,
td {
  padding: 14px 16px;
  border-bottom: 1px solid var(--color-border);
  vertical-align: middle;
}
td:first-child {
  width: 52%;
}
td:nth-child(2) {
  width: 25%;
}
td strong {
  font-size: 13px;
}
.question-summary {
  margin: 0 0 7px;
  line-height: 1.65;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  overflow-wrap: anywhere;
}
.question-type {
  font-size: 12px;
  color: var(--color-primary);
}
.row-meta {
  margin: 5px 0 0;
  color: var(--color-muted);
  font-size: 12px;
  overflow-wrap: anywhere;
}
.action-cell {
  text-align: right;
  white-space: nowrap;
}
.empty-state {
  text-align: center;
  color: var(--color-muted);
  padding: 48px 16px;
}
.question-form {
  display: grid;
  gap: 24px;
}
.editor-actions {
  justify-content: space-between;
}
.editor-actions > span {
  font-size: 12px;
}
.action-buttons {
  display: flex;
  gap: 10px;
}
@media (max-width: 760px) {
  .filter-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .filter-grid select:last-child {
    grid-column: 1 / -1;
  }
  .search-line {
    flex-wrap: wrap;
  }
  .search-box {
    flex-basis: 100%;
  }
  .editor-actions {
    align-items: stretch;
  }
  .action-buttons {
    flex-wrap: wrap;
  }
}
</style>
