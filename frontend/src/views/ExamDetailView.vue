<script setup lang="ts">
import { nextTick, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { NAlert, NButton, NModal, useDialog } from 'naive-ui'
import { examStatusLabels } from '../api/exams'
import QuestionFields from '../components/QuestionFields.vue'
import ExamParticipants from '../components/ExamParticipants.vue'
import PageHeader from '../components/ui/PageHeader.vue'
import SurfacePanel from '../components/ui/SurfacePanel.vue'
import StatusBadge from '../components/ui/StatusBadge.vue'
import AppIcon from '../components/ui/AppIcon.vue'
import ExamSettings from '../features/exams/ExamSettings.vue'
import SnapshotQuestions from '../features/exams/SnapshotQuestions.vue'
import { useExamDraft } from '../features/exams/useExamDraft'
import ExamGradingPanel from '../features/grading/ExamGradingPanel.vue'
import StandardCorrection from '../features/grading/StandardCorrection.vue'
import WithdrawResults from '../features/grading/WithdrawResults.vue'
const route = useRoute()
const router = useRouter()
const dialog = useDialog()
const {
  exam,
  form,
  failure,
  success,
  conflict,
  loading,
  saving,
  start,
  end,
  duration,
  questionVisible,
  editingQuestion,
  uploading,
  isDraft,
  dirty,
  draftTotal,
  load,
  save,
  transition,
  cancel,
  move,
  addQuestion,
  editQuestion,
  applyQuestion,
} = useExamDraft(() => String(route.params.id))
const activeTab = ref(0)
const cancelVisible = ref(false)
const cancelReason = ref('')
const correctionIndex = ref<number | null>(null)
const correctionSuccess = ref('')
const withdrawResultsVisible = ref(false)
function standardSaved(): void {
  correctionSuccess.value = '评分依据已更新，受影响的答卷将按当前依据重判。'
  void load()
}
function resultsWithdrawn(): void {
  correctionSuccess.value = '已撤回公布结果，可继续更正评分。'
  void load()
}
function openCancel(): void {
  cancelReason.value = ''
  cancelVisible.value = true
}
async function confirmCancel(): Promise<void> {
  if (await cancel(cancelReason.value)) cancelVisible.value = false
}
const tabs = [
  { label: '考试设置', icon: 'clock', id: 'exam-settings' },
  { label: '题目快照', icon: 'paper', id: 'exam-questions' },
  { label: '参考资格', icon: 'users', id: 'exam-eligibility' },
  { label: '答卷与成绩', icon: 'check-circle', id: 'exam-grading' },
]
const tabButtons = ref<HTMLButtonElement[]>([])
function activateTab(index: number): void {
  activeTab.value = (index + tabs.length) % tabs.length
  tabButtons.value[activeTab.value]?.focus()
}
function revealInvalidField(event: Event): void {
  const field = event.target as HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement
  const panelId = field.closest('[role="tabpanel"]')?.id
  const index = tabs.findIndex((tab) => tab.id === panelId)
  if (index < 0 || index === activeTab.value) return
  // 隐藏分区仍参与整份草稿校验；先显示字段，再由浏览器提供就近的必填提示。
  event.preventDefault()
  activeTab.value = index
  void nextTick(() => {
    field.focus()
    field.reportValidity()
  })
}
function confirmTransition(action: 'publish' | 'withdraw'): void {
  dialog.warning({
    title: action === 'publish' ? '发布考试' : '撤回考试发布',
    content:
      action === 'publish'
        ? '发布后题目、时间、评分和乱序配置将锁定。请确认已保存全部修改。'
        : '仅尚无人开始作答的考试可以撤回。撤回后可继续编辑草稿。',
    positiveText: action === 'publish' ? '确认发布' : '确认撤回',
    negativeText: '取消',
    onPositiveClick: () => transition(action),
  })
}
</script>
<template>
  <div class="page-stack">
    <div class="detail-back">
      <NButton text @click="router.push('/staff/exams')"
        ><template #icon><AppIcon name="arrow-left" :size="16" /></template>返回考试列表</NButton
      >
    </div>
    <PageHeader :title="exam?.title || '考试详情'">
      <template #actions
        ><StatusBadge
          v-if="exam"
          :label="examStatusLabels[exam.status]"
          :tone="isDraft ? 'warning' : exam.status === 'CANCELLED' ? 'danger' : 'success'"
        /><template v-if="isDraft"
          ><NButton
            form="exam-draft-form"
            attr-type="submit"
            :type="dirty ? 'primary' : 'default'"
            :loading="saving"
            :disabled="conflict"
            >保存考试草稿</NButton
          ><NButton
            :type="dirty ? 'default' : 'primary'"
            :disabled="dirty || conflict || saving"
            @click="confirmTransition('publish')"
            >发布考试</NButton
          ></template
        ><NButton
          v-else-if="exam?.status === 'RELEASED'"
          :loading="saving"
          @click="confirmTransition('withdraw')"
          >撤回考试发布</NButton
        ><NButton
          v-if="exam?.status === 'RESULTS_PUBLISHED'"
          :disabled="saving"
          @click="withdrawResultsVisible = true"
          >撤回已公布结果</NButton
        ><NButton
          v-if="exam && exam.status !== 'CANCELLED'"
          type="error"
          secondary
          :disabled="saving || conflict"
          @click="openCancel"
          >取消整场考试</NButton
        ></template
      >
    </PageHeader>
    <NAlert v-if="failure" type="error"
      >{{ failure }}
      <NButton v-if="conflict || !exam" size="small" @click="load">{{
        conflict ? '重新加载最新考试' : '重新加载考试'
      }}</NButton></NAlert
    >
    <NAlert v-if="success" type="success">{{ success }}</NAlert>
    <NAlert v-if="correctionSuccess" type="success">{{ correctionSuccess }}</NAlert>
    <NAlert v-if="exam?.status === 'CANCELLED'" type="error"
      ><strong>本场考试已取消，无法恢复。</strong>
      <p v-if="exam.cancelled_reason">{{ exam.cancelled_reason }}</p></NAlert
    >
    <NAlert v-for="warning in exam?.warnings" :key="warning" type="warning">{{ warning }}</NAlert>
    <p v-if="loading && !exam" class="muted" role="status">正在加载考试…</p>
    <template v-if="form && exam">
      <div class="exam-overview">
        <div>
          <span class="muted">题目</span
          ><strong>{{ form.questions.length }} <small>道</small></strong>
        </div>
        <div>
          <span class="muted">总分</span><strong>{{ draftTotal }} <small>分</small></strong>
        </div>
        <div>
          <span class="muted">参考范围</span
          ><strong>{{ form.audience_type === 'PUBLIC' ? '全部激活学生' : '限定名单' }}</strong>
        </div>
        <div class="overview-state">
          <span v-if="dirty" class="unsaved">有未保存修改</span
          ><span v-else class="muted">{{
            isDraft ? '发布前请完成配置与名单' : '题目与配置已锁定'
          }}</span>
          <p v-if="dirty" class="muted">先保存草稿，再发布考试。</p>
        </div>
      </div>
      <div class="exam-tabs" role="tablist" aria-label="考试管理区域">
        <button
          v-for="(tab, index) in tabs"
          :id="`${tab.id}-tab`"
          :key="tab.id"
          :ref="
            (el) => {
              if (el) tabButtons[index] = el as HTMLButtonElement
            }
          "
          role="tab"
          :aria-selected="activeTab === index"
          :aria-controls="tab.id"
          :tabindex="activeTab === index ? 0 : -1"
          @click="activeTab = index"
          @keydown.right.prevent="activateTab(index + 1)"
          @keydown.left.prevent="activateTab(index - 1)"
          @keydown.home.prevent="activateTab(0)"
          @keydown.end.prevent="activateTab(tabs.length - 1)"
        >
          <AppIcon :name="tab.icon" :size="17" />{{ tab.label }}
        </button>
      </div>
      <form
        id="exam-draft-form"
        class="exam-form"
        @submit.prevent="save"
        @invalid.capture="revealInvalidField"
      >
        <section
          v-show="activeTab === 0"
          id="exam-settings"
          role="tabpanel"
          aria-labelledby="exam-settings-tab"
        >
          <NAlert v-if="!isDraft && exam.status !== 'CANCELLED'" class="form-alert" type="info"
            >已发布配置已锁定。尚无人开始时可撤回发布后修改。</NAlert
          ><ExamSettings
            v-model="form"
            v-model:start="start"
            v-model:end="end"
            v-model:duration="duration"
            :disabled="!isDraft || saving"
            :saved-exam="exam"
          />
        </section>
        <section
          v-show="activeTab === 1"
          id="exam-questions"
          role="tabpanel"
          aria-labelledby="exam-questions-tab"
        >
          <SurfacePanel
            title="独立题目快照"
            description="调整只影响本场考试；来源题库和试卷的后续修改不会改变此快照。"
            ><SnapshotQuestions
              v-model="form.questions"
              :disabled="!isDraft || saving"
              :allow-correction="exam.status === 'RELEASED' || exam.status === 'RESULTS_PUBLISHED'"
              @move="move"
              @edit="editQuestion"
              @add="addQuestion"
              @correct="correctionIndex = $event"
          /></SurfacePanel>
        </section>
      </form>
      <section
        v-show="activeTab === 2"
        id="exam-eligibility"
        role="tabpanel"
        aria-labelledby="exam-eligibility-tab"
      >
        <ExamParticipants :exam-id="exam.id" :audience="exam.audience_type" :status="exam.status" />
      </section>
      <section
        v-if="activeTab === 3"
        id="exam-grading"
        role="tabpanel"
        aria-labelledby="exam-grading-tab"
      >
        <ExamGradingPanel :exam-id="exam.id" :cancelled="exam.status === 'CANCELLED'" />
      </section>
    </template>
    <StandardCorrection
      v-if="exam && correctionIndex !== null"
      :exam="exam"
      :question-index="correctionIndex"
      @close="correctionIndex = null"
      @saved="standardSaved"
      @refreshed="load"
    />
    <WithdrawResults
      v-if="exam && withdrawResultsVisible"
      :exam="exam"
      @close="withdrawResultsVisible = false"
      @saved="resultsWithdrawn"
      @refresh="load"
    />
    <NModal
      v-model:show="questionVisible"
      preset="card"
      title="编辑考试快照题目"
      class="responsive-modal responsive-modal--editor"
      :mask-closable="false"
      :closable="!uploading"
      :close-on-esc="!uploading"
      ><form v-if="editingQuestion" class="snapshot-editor" @submit.prevent="applyQuestion">
        <QuestionFields v-model="editingQuestion" @uploading="uploading = $event" />
        <div class="editor-actions">
          <span class="muted">应用后还需保存考试草稿。</span
          ><NButton attr-type="submit" type="primary" :disabled="uploading">应用题目修改</NButton>
        </div>
      </form></NModal
    >
    <NModal
      v-model:show="cancelVisible"
      preset="card"
      title="取消整场考试"
      class="responsive-modal"
      :mask-closable="false"
      :closable="!saving"
      :close-on-esc="!saving"
    >
      <NAlert type="error">取消后全部作答将废弃，考试无法恢复。</NAlert>
      <form class="cancel-exam-form" @submit.prevent="confirmCancel">
        <label class="field"
          >取消考试原因<textarea
            v-model="cancelReason"
            aria-label="取消考试原因"
            required
            maxlength="2000"
            rows="3"
            :disabled="saving"
          />
        </label>
        <div class="editor-actions">
          <NButton :disabled="saving" @click="cancelVisible = false">保留考试</NButton
          ><NButton
            attr-type="submit"
            type="error"
            :disabled="!cancelReason.trim() || conflict"
            :loading="saving"
            >确认取消整场考试</NButton
          >
        </div>
      </form>
    </NModal>
  </div>
</template>
<style scoped>
.cancel-exam-form {
  display: grid;
  gap: 20px;
  margin-top: 20px;
}
.detail-back {
  margin-bottom: -12px;
}
.exam-overview {
  display: grid;
  grid-template-columns: 120px 140px minmax(160px, 1fr) minmax(200px, 1fr);
  gap: 24px;
  align-items: center;
  padding: 20px 24px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
}
.exam-overview > div {
  display: grid;
  gap: 8px;
}
.exam-overview > div > span {
  font-size: 12px;
}
.exam-overview strong {
  font-size: 20px;
  font-weight: 650;
}
.exam-overview small {
  font-size: 12px;
  color: var(--color-muted);
  font-weight: 400;
}
.exam-overview > div:nth-child(3) strong {
  font-size: 14px;
}
.exam-overview .overview-state {
  padding-left: 24px;
  border-left: 1px solid var(--color-border);
}
.overview-state p {
  margin: 0;
  font-size: 12px;
}
.unsaved {
  color: var(--color-primary);
  font-weight: 600;
}
.exam-tabs {
  display: flex;
  gap: 30px;
  border-bottom: 1px solid var(--color-border);
}
.exam-tabs button {
  display: flex;
  gap: 8px;
  align-items: center;
  background: transparent;
  border: 0;
  border-bottom: 2px solid transparent;
  padding: 12px 2px;
  color: var(--color-muted);
  font-size: 14px;
}
.exam-tabs button[aria-selected='true'] {
  color: var(--color-primary);
  border-bottom-color: var(--color-primary);
  font-weight: 600;
}
.exam-form,
.snapshot-editor {
  display: grid;
  gap: 22px;
  min-width: 0;
}
.delivery-note {
  display: flex;
  gap: 7px;
  align-items: center;
  font-size: 12px;
  margin: 0;
}
.snapshot-editor .editor-actions {
  justify-content: space-between;
}
.snapshot-editor .editor-actions span {
  font-size: 12px;
}
@media (max-width: 900px) {
  .exam-overview {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 20px;
  }
  .exam-overview .overview-state {
    padding-left: 0;
    border-left: 0;
  }
}
@media (max-width: 480px) {
  .exam-overview {
    padding: 18px;
    gap: 16px;
  }
  .exam-tabs {
    gap: 18px;
    overflow-x: auto;
  }
  .exam-tabs button {
    font-size: 13px;
    gap: 6px;
    flex-shrink: 0;
  }
  .exam-overview strong {
    font-size: 18px;
  }
}
</style>
