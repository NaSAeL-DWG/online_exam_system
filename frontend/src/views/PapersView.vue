<script setup lang="ts">
import { ref, useId, watch } from 'vue'
import { NAlert, NButton, NModal, useDialog } from 'naive-ui'
import { papersApi } from '../api/papers'
import QuestionPicker from '../components/QuestionPicker.vue'
import ListPager from '../components/ListPager.vue'
import PageHeader from '../components/ui/PageHeader.vue'
import SurfacePanel from '../components/ui/SurfacePanel.vue'
import StatusBadge from '../components/ui/StatusBadge.vue'
import AppIcon from '../components/ui/AppIcon.vue'
import PaperQuestionList from '../features/papers/PaperQuestionList.vue'
import { usePaperEditor } from '../features/papers/usePaperEditor'
import { usePagedList } from '../composables/usePagedList'
import { useUnsavedChanges } from '../composables/useUnsavedChanges'
import {
  textError,
  useContentValidation,
  type ContentFieldErrors,
} from '../features/contentValidation'
const { items, page, total, query, loading, failure, load, changePage } = usePagedList(
  papersApi.list,
)
const {
  visible,
  selected,
  title,
  description,
  questions,
  saving,
  failure: editorFailure,
  conflict,
  dirty,
  archived,
  draftTotal,
  create,
  edit,
  move,
  persist,
} = usePaperEditor(load)
const formRoot = ref<HTMLFormElement | null>(null)
const questionList = ref<InstanceType<typeof PaperQuestionList> | null>(null)
const errorPrefix = useId()
const { errors, validate, resetValidation } = useContentValidation(() => {
  const errors: ContentFieldErrors = {}
  const titleIssue = textError(title.value, '试卷名称', 200, true)
  const descriptionIssue = textError(description.value, '试卷说明', 100000)
  if (titleIssue) errors.title = titleIssue
  if (descriptionIssue) errors.description = descriptionIssue
  return errors
})
watch(visible, () => {
  resetValidation()
  questionList.value?.resetValidation()
})
async function savePaper(): Promise<void> {
  const basicsValid = validate(formRoot.value)
  const scoresValid = questionList.value?.validate(basicsValid) ?? true
  if (basicsValid && scoresValid) await persist('save')
}
const { confirmDiscard } = useUnsavedChanges(() => dirty.value)
async function closeEditor(): Promise<void> {
  if (!saving.value && (await confirmDiscard())) visible.value = false
}
const dialog = useDialog()
function archive(): void {
  dialog.warning({
    title: '归档试卷',
    content: `归档后不能再用于创建新考试，已有考试快照保持不变。${dirty.value ? '尚未保存的修改不会应用到试卷。' : ''}`,
    positiveText: '确认归档',
    negativeText: '取消',
    onPositiveClick: () => persist('archive'),
  })
}
</script>
<template>
  <div class="page-stack">
    <PageHeader title="共享试卷" description="挑选题目，安排顺序与分值，为考试准备试卷。"
      ><template #actions
        ><NButton type="primary" @click="create"
          ><template #icon><AppIcon name="plus" :size="17" /></template>新建试卷</NButton
        ></template
      ></PageHeader
    >
    <NAlert v-if="failure || (!visible && editorFailure)" type="error"
      >{{ failure || editorFailure }}
      <NButton size="small" @click="load">重新加载试卷</NButton></NAlert
    >
    <SurfacePanel>
      <form class="toolbar" @submit.prevent="changePage(1)">
        <input
          v-model="query"
          class="form-control paper-search"
          aria-label="搜索试卷"
          placeholder="搜索试卷名称"
        /><NButton attr-type="submit" :loading="loading">查询试卷</NButton
        ><span class="toolbar-meta">共 {{ total }} 张试卷</span>
      </form>
      <div class="table-region" :aria-busy="loading">
        <table class="paper-table">
          <thead>
            <tr>
              <th>试卷名称</th>
              <th>题数</th>
              <th>总分</th>
              <th>状态</th>
              <th class="action-cell">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="paper in items" :key="paper.id">
              <td>
                <strong>{{ paper.title }}</strong>
                <p v-if="paper.description" class="paper-description">{{ paper.description }}</p>
              </td>
              <td>{{ paper.question_count }} 道</td>
              <td>
                <span class="score">{{ paper.total_score }}</span
                ><span class="muted"> 分</span>
              </td>
              <td>
                <StatusBadge
                  :label="paper.status === 'ACTIVE' ? '使用中' : '已归档'"
                  :tone="paper.status === 'ACTIVE' ? 'success' : 'neutral'"
                />
              </td>
              <td class="action-cell">
                <NButton size="small" @click="edit(paper.id)">编辑</NButton>
              </td>
            </tr>
            <tr v-if="!items.length">
              <td colspan="5" class="empty-state">
                {{ loading ? '正在加载试卷…' : '没有找到试卷，可调整搜索或新建试卷。' }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <ListPager
        label="试卷"
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
      :title="selected ? '编辑试卷' : '新建试卷'"
      class="responsive-modal responsive-modal--composer"
      :content-style="{ minHeight: '0', overflow: 'auto' }"
      :mask-closable="false"
      :closable="!saving"
      :close-on-esc="!saving"
    >
      <NAlert v-if="editorFailure" class="form-alert" type="error"
        >{{ editorFailure }}
        <NButton v-if="conflict && selected" @click="edit(selected.id)"
          >重新加载最新试卷</NButton
        ></NAlert
      >
      <NAlert v-if="archived" class="form-alert" type="info">此试卷已归档，保留内容供追溯。</NAlert>
      <form
        ref="formRoot"
        id="paper-editor-form"
        class="paper-form"
        novalidate
        @submit.prevent="savePaper"
      >
        <fieldset :disabled="saving || archived" class="paper-basics">
          <label class="field"
            >试卷名称<input
              v-model="title"
              aria-label="试卷名称"
              required
              maxlength="200"
              :aria-invalid="!!errors.title"
              :aria-describedby="errors.title ? `${errorPrefix}-title-error` : undefined"
              placeholder="为试卷取一个便于查找的名称"
            /><span
              v-if="errors.title"
              :id="`${errorPrefix}-title-error`"
              class="field-error"
              role="alert"
              >{{ errors.title }}</span
            ></label
          ><label class="field"
            >试卷说明<textarea
              v-model="description"
              aria-label="试卷说明"
              rows="2"
              maxlength="100000"
              :aria-invalid="!!errors.description"
              :aria-describedby="
                errors.description ? `${errorPrefix}-description-error` : undefined
              "
              placeholder="适用范围或使用说明（可选）"
            />
            <span
              v-if="errors.description"
              :id="`${errorPrefix}-description-error`"
              class="field-error"
              role="alert"
              >{{ errors.description }}</span
            >
          </label>
        </fieldset>
        <div class="composer-workspace" :class="{ 'composer-workspace--archived': archived }">
          <QuestionPicker
            v-if="!archived"
            :excluded-ids="questions.map((item) => item.question.id)"
            @add="questions.push({ question: $event, score: '1.0' })"
          />
          <section class="selected-column">
            <header class="selected-heading">
              <h3>已选题目</h3>
              <p role="status" aria-label="试卷分值汇总">
                {{ questions.length }} 道题 · 总分 {{ draftTotal }} 分
              </p>
            </header>
            <PaperQuestionList
              ref="questionList"
              v-model="questions"
              :disabled="archived || saving"
              @move="move"
            />
          </section>
        </div>
      </form>
      <template #footer
        ><div v-if="!archived" class="editor-actions editor-actions--split">
          <span class="muted">同一道题只能加入一次；分值支持一位小数。</span>
          <div class="action-buttons">
            <NButton v-if="selected" type="warning" :disabled="conflict || saving" @click="archive"
              >归档试卷</NButton
            ><NButton
              form="paper-editor-form"
              attr-type="submit"
              type="primary"
              :loading="saving"
              :disabled="conflict"
              >保存试卷</NButton
            >
          </div>
        </div></template
      >
    </NModal>
  </div>
</template>
<style scoped>
.field-error {
  color: #b42318;
  font-size: 12px;
}
.paper-search {
  flex: 1;
  min-width: 0;
  max-width: 420px;
}
.paper-table {
  width: 100%;
  min-width: 600px;
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
  padding: 16px;
  border-bottom: 1px solid var(--color-border);
}
td:first-child {
  width: 48%;
}
td:first-child strong {
  font-weight: 600;
}
.paper-description {
  margin: 6px 0 0;
  color: var(--color-muted);
  font-size: 12px;
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.score {
  font-weight: 650;
  font-variant-numeric: tabular-nums;
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
.paper-form {
  display: grid;
  gap: 24px;
}
.paper-basics {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 18px;
  padding: 0;
  border: 0;
}
.composer-workspace {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 26px;
  border-top: 1px solid var(--color-border);
  padding-top: 24px;
  align-items: start;
}
.selected-column {
  min-width: 0;
}
.composer-workspace--archived {
  grid-template-columns: 1fr;
}
.selected-heading {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 16px;
}
.selected-heading h3 {
  margin: 0;
  font-size: 15px;
}
.selected-heading p {
  margin: 0;
  color: var(--color-primary);
  font-size: 13px;
  font-weight: 600;
}
.editor-actions > span {
  font-size: 12px;
}
.action-buttons {
  display: flex;
  gap: 10px;
}
@media (max-width: 900px) {
  .composer-workspace {
    grid-template-columns: 1fr;
  }
  .selected-column {
    border-top: 1px solid var(--color-border);
    padding-top: 22px;
  }
}
@media (max-width: 600px) {
  .paper-basics {
    grid-template-columns: 1fr;
  }
  .paper-search {
    flex-basis: 100%;
    max-width: none;
  }
  .editor-actions {
    align-items: stretch;
  }
  .action-buttons {
    flex-wrap: wrap;
  }
}
</style>
