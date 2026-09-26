<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { NAlert, NButton, NCard, NModal, NSpace, NTag, useDialog } from 'naive-ui'
import { ApiError, errorMessage } from '../api/client'
import { examsApi, examStatusLabels, type Exam, type SnapshotQuestion } from '../api/exams'
import type { Question, QuestionInput } from '../api/questions'
import QuestionFields from '../components/QuestionFields.vue'
import QuestionPicker from '../components/QuestionPicker.vue'
import SafeMarkdown from '../components/SafeMarkdown.vue'
import MemberPicker from '../components/MemberPicker.vue'
import ExamParticipants from '../components/ExamParticipants.vue'

const route = useRoute()
const router = useRouter()
const dialog = useDialog()
const exam = ref<Exam | null>(null)
const form = ref<Exam | null>(null)
const failure = ref('')
const success = ref('')
const conflict = ref(false)
const saving = ref(false)
const start = ref('')
const end = ref('')
const duration = ref<number | null>(null)
const questionVisible = ref(false)
const questionIndex = ref(0)
const editingQuestion = ref<QuestionInput | null>(null)
const uploading = ref(false)
const isDraft = computed(() => exam.value?.status === 'DRAFT')
const dirty = computed(
  () =>
    form.value &&
    exam.value &&
    (JSON.stringify(form.value) !== JSON.stringify(exam.value) ||
      start.value !== displayTime(exam.value.start_at) ||
      end.value !== displayTime(exam.value.end_at) ||
      duration.value !== (exam.value.duration_seconds ? exam.value.duration_seconds / 60 : null)),
)
function displayTime(value: string | null): string {
  if (!value) return ''
  return new Intl.DateTimeFormat('sv-SE', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
    .format(new Date(value))
    .replace(' ', 'T')
}
function assign(value: Exam): void {
  exam.value = value
  form.value = structuredClone(value)
  start.value = displayTime(value.start_at)
  end.value = displayTime(value.end_at)
  duration.value = value.duration_seconds ? value.duration_seconds / 60 : null
  conflict.value = false
}
async function load(): Promise<void> {
  failure.value = ''
  success.value = ''
  try {
    assign(await examsApi.get(String(route.params.id)))
  } catch (error) {
    failure.value = errorMessage(error)
  }
}
async function save(): Promise<void> {
  if (!form.value || !exam.value || saving.value) return
  saving.value = true
  failure.value = ''
  success.value = ''
  try {
    const value = form.value
    const result = await examsApi.update(exam.value.id, {
      title: value.title,
      description: value.description,
      audience_type: value.audience_type,
      start_at: start.value ? `${start.value}:00+08:00` : null,
      end_at: end.value ? `${end.value}:00+08:00` : null,
      duration_seconds: duration.value ? Number(duration.value) * 60 : null,
      max_attempts: Number(value.max_attempts),
      allow_review: value.allow_review,
      shuffle_questions: value.shuffle_questions,
      shuffle_options: value.shuffle_options,
      multiple_choice_mode: value.multiple_choice_mode,
      pass_percentage: String(value.pass_percentage),
      grader_ids: value.grader_ids,
      version: exam.value.version,
      questions: value.questions.map((question) => ({
        ...question,
        score: String(question.score),
      })),
    })
    assign(result)
    success.value = '考试草稿已保存'
  } catch (error) {
    failure.value = errorMessage(error)
    conflict.value = error instanceof ApiError && error.problem.code === 'VERSION_CONFLICT'
  } finally {
    saving.value = false
  }
}
function move(index: number, direction: number): void {
  const questions = form.value!.questions
  const item = questions.splice(index, 1)[0]
  if (item) questions.splice(index + direction, 0, item)
}
function addQuestion(question: Question): void {
  const {
    id,
    creator_id: _creator,
    status: _status,
    version: _version,
    created_at: _created,
    updated_at: _updated,
    ...content
  } = question
  form.value!.questions.push({
    ...(JSON.parse(JSON.stringify(content)) as QuestionInput),
    source_question_id: id,
    score: '1.0',
  })
}
function editQuestion(index: number): void {
  questionIndex.value = index
  editingQuestion.value = JSON.parse(
    JSON.stringify(form.value!.questions[index]),
  ) as SnapshotQuestion
  questionVisible.value = true
}
function applyQuestion(): void {
  Object.assign(form.value!.questions[questionIndex.value]!, editingQuestion.value)
  questionVisible.value = false
}
function transition(action: 'publish' | 'withdraw'): void {
  if (!exam.value) return
  dialog.warning({
    title: action === 'publish' ? '发布考试' : '撤回考试发布',
    content:
      action === 'publish'
        ? '发布后题目、时间、评分和乱序配置将锁定。请确认已保存全部修改。'
        : '仅尚无人开始作答的考试可以撤回。撤回后可继续编辑草稿。',
    positiveText: action === 'publish' ? '确认发布' : '确认撤回',
    negativeText: '取消',
    onPositiveClick: async () => {
      saving.value = true
      failure.value = ''
      success.value = ''
      try {
        assign(await examsApi[action](exam.value!.id, exam.value!.version))
      } catch (error) {
        failure.value = errorMessage(error)
        conflict.value = error instanceof ApiError && error.problem.code === 'VERSION_CONFLICT'
      } finally {
        saving.value = false
      }
    },
  })
}
onMounted(load)
</script>

<template>
  <div class="page-stack">
    <div class="page-title">
      <div>
        <p class="eyebrow accent">EXAM SNAPSHOT</p>
        <h1>{{ isDraft ? '考试草稿' : '考试详情' }}</h1>
        <p>{{ exam?.title }}</p>
      </div>
      <NSpace
        ><NTag v-if="exam">{{ examStatusLabels[exam.status] }}</NTag
        ><NButton @click="router.push('/staff/exams')">返回考试列表</NButton></NSpace
      >
    </div>
    <NAlert v-if="failure" type="error"
      >{{ failure }} <NButton v-if="conflict" @click="load">重新加载最新考试</NButton></NAlert
    >
    <NAlert v-if="success" type="success">{{ success }}</NAlert>
    <NAlert v-for="warning in exam?.warnings" :key="warning" type="warning">{{ warning }}</NAlert>
    <template v-if="form && exam">
      <NAlert v-if="!isDraft" type="info"
        >已发布配置和快照已锁定。尚无人开始时可撤回发布后修改。</NAlert
      >
      <form class="exam-form" @submit.prevent="save">
        <NCard title="考试配置"
          ><fieldset :disabled="!isDraft || saving" class="config-grid">
            <label>考试名称<input v-model="form.title" aria-label="考试名称" required /></label>
            <label
              >参考范围<select v-model="form.audience_type" aria-label="参考范围">
                <option value="RESTRICTED">限定名单</option>
                <option value="PUBLIC">全部激活学生</option>
              </select></label
            >
            <label class="full-width"
              >考试说明<textarea v-model="form.description" aria-label="考试说明" rows="3" />
            </label>
            <label
              >开始时间（上海）<input
                v-model="start"
                aria-label="开始时间（上海）"
                type="datetime-local"
            /></label>
            <label
              >结束时间（上海）<input
                v-model="end"
                aria-label="结束时间（上海）"
                type="datetime-local"
            /></label>
            <label
              >作答时长（分钟）<input
                v-model.number="duration"
                aria-label="作答时长（分钟）"
                type="number"
                min="1"
                step="1"
            /></label>
            <label
              >最多作答次数<input
                v-model.number="form.max_attempts"
                aria-label="最多作答次数"
                type="number"
                min="1"
                step="1"
                required
            /></label>
            <label
              >多选评分<select v-model="form.multiple_choice_mode" aria-label="多选评分">
                <option value="EXACT">完全一致得分</option>
                <option value="PARTIAL">无错选按比例得分</option>
              </select></label
            >
            <label
              >及格百分比<input
                v-model="form.pass_percentage"
                aria-label="及格百分比"
                type="number"
                min="0"
                max="100"
                step="0.01"
                required
            /></label>
            <div class="check-options full-width">
              <label
                ><input
                  v-model="form.shuffle_questions"
                  type="checkbox"
                  aria-label="题目乱序"
                />题目乱序</label
              ><label
                ><input
                  v-model="form.shuffle_options"
                  type="checkbox"
                  aria-label="选项乱序"
                />选项乱序</label
              ><label
                ><input
                  v-model="form.allow_review"
                  type="checkbox"
                  aria-label="公布后允许回看"
                />公布后允许回看答案与解析</label
              >
            </div>
          </fieldset>
          <div class="graders">
            <h3>指定阅卷教师</h3>
            <p class="muted">含简答题时，发布前至少指定一位激活教师。</p>
            <MemberPicker
              v-if="isDraft"
              v-model="form.grader_ids"
              kind="teacher"
              staff-teachers
              :selected-members="exam.graders"
            />
            <p v-else>
              已指定 {{ exam.graders.map((teacher) => teacher.real_name).join('、') || '无' }}
            </p>
          </div>
        </NCard>
        <NCard title="独立题目快照"
          ><p class="muted">
            来源题库和试卷的后续修改不会影响本场考试。当前已保存总分：{{ exam.total_score }}。
          </p>
          <section data-testid="exam-snapshot">
            <article
              v-for="(question, index) in form.questions"
              :key="question.id ?? question.source_question_id ?? index"
              class="snapshot-question"
            >
              <div class="question-toolbar">
                <strong>第 {{ index + 1 }} 题</strong
                ><label
                  >分值<input
                    v-model="question.score"
                    :aria-label="`快照第 ${index + 1} 题分值`"
                    type="number"
                    min="0.1"
                    step="0.1"
                    required
                    :disabled="!isDraft || saving" /></label
                ><template v-if="isDraft"
                  ><NButton :aria-label="`编辑快照第 ${index + 1} 题`" @click="editQuestion(index)"
                    >编辑题目</NButton
                  ><NButton :disabled="index === 0" @click="move(index, -1)">上移</NButton
                  ><NButton :disabled="index === form.questions.length - 1" @click="move(index, 1)"
                    >下移</NButton
                  ><NButton @click="form.questions.splice(index, 1)">移出</NButton></template
                >
              </div>
              <SafeMarkdown :content="question.content" />
            </article>
          </section>
          <QuestionPicker
            v-if="isDraft"
            :excluded-ids="
              form.questions.flatMap((question) =>
                question.source_question_id ? [question.source_question_id] : [],
              )
            "
            @add="addQuestion"
          />
        </NCard>
        <NSpace
          ><template v-if="isDraft"
            ><NButton attr-type="submit" type="primary" :loading="saving" :disabled="conflict"
              >保存考试草稿</NButton
            ><NButton :disabled="!!dirty || conflict || saving" @click="transition('publish')"
              >发布考试</NButton
            ><span v-if="dirty" class="muted">请先保存草稿再发布。</span></template
          ><NButton
            v-else-if="exam.status === 'RELEASED'"
            :loading="saving"
            @click="transition('withdraw')"
            >撤回考试发布</NButton
          ></NSpace
        >
      </form>
      <ExamParticipants :exam-id="exam.id" :audience="exam.audience_type" :status="exam.status" />
      <NAlert type="info">学生考试列表和作答功能尚未开放。</NAlert>
    </template>
    <NModal
      v-model:show="questionVisible"
      preset="card"
      title="编辑考试快照题目"
      style="width: 960px; max-height: 90vh; overflow-y: auto"
      :mask-closable="false"
      :closable="!uploading"
      :close-on-esc="!uploading"
      ><form v-if="editingQuestion" class="exam-form" @submit.prevent="applyQuestion">
        <QuestionFields v-model="editingQuestion" @uploading="uploading = $event" /><NButton
          attr-type="submit"
          type="primary"
          :disabled="uploading"
          >应用题目修改</NButton
        >
      </form></NModal
    >
  </div>
</template>

<style scoped>
.exam-form {
  display: grid;
  gap: 22px;
}
.config-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 18px;
  border: 0;
  padding: 0;
}
.full-width {
  grid-column: 1 / -1;
}
label {
  display: grid;
  gap: 7px;
}
input,
select,
textarea {
  border: 1px solid #d9dfe9;
  border-radius: 6px;
  padding: 9px 12px;
  font: inherit;
  width: 100%;
}
.check-options {
  display: flex;
  gap: 24px;
}
.check-options label {
  display: flex;
  align-items: center;
}
.check-options input {
  width: auto;
}
.graders {
  margin-top: 24px;
}
.snapshot-question {
  border: 1px solid #e5eaf2;
  border-radius: 8px;
  padding: 16px;
  margin: 16px 0;
}
.question-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
}
.question-toolbar label {
  display: flex;
  align-items: center;
  margin-left: auto;
}
.question-toolbar input {
  width: 90px;
}
</style>
