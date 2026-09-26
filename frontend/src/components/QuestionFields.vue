<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { NAlert, NButton } from 'naive-ui'
import { questionTypeLabels, questionsApi, type QuestionInput } from '../api/questions'
import { errorMessage } from '../api/client'
import SafeMarkdown from './SafeMarkdown.vue'

const model = defineModel<QuestionInput>({ required: true })
const tagText = ref(model.value.knowledge_tags.join(', '))
watch(
  () => model.value,
  (value) => {
    tagText.value = value.knowledge_tags.join(', ')
  },
)
const emit = defineEmits<{ uploading: [value: boolean] }>()
const uploading = ref(false)
const uploadFailure = ref('')
async function upload(event: Event, field: 'content' | 'explanation'): Promise<void> {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  // 上传始终写回启动时的题目，防止编辑器切换后污染另一个草稿。
  const target = model.value
  uploading.value = true
  emit('uploading', true)
  uploadFailure.value = ''
  try {
    const asset = await questionsApi.upload(file)
    target[field] = `${target[field] ?? ''}\n\n![图片](${asset.url})`
  } catch (error) {
    uploadFailure.value = errorMessage(error)
  } finally {
    uploading.value = false
    emit('uploading', false)
    input.value = ''
  }
}
const isChoice = computed(() => ['SINGLE_CHOICE', 'MULTIPLE_CHOICE'].includes(model.value.type))
function changeTags(event: Event): void {
  const value = (event.target as HTMLInputElement).value
  model.value.knowledge_tags = [
    ...new Set(
      value
        .split(/[,，]/)
        .map((tag) => tag.trim())
        .filter(Boolean),
    ),
  ]
}
function changeType(): void {
  if (isChoice.value) {
    if (model.value.options.length < 2)
      model.value.options = [
        { id: crypto.randomUUID(), content: '' },
        { id: crypto.randomUUID(), content: '' },
      ]
    model.value.standard_answer = []
  } else {
    model.value.options = []
    model.value.standard_answer = model.value.type === 'TRUE_FALSE' ? true : null
  }
}
function selectAnswer(id: string, checked: boolean): void {
  if (model.value.type === 'SINGLE_CHOICE') {
    model.value.standard_answer = [id]
    return
  }
  const answer = Array.isArray(model.value.standard_answer) ? model.value.standard_answer : []
  model.value.standard_answer = checked ? [...answer, id] : answer.filter((item) => item !== id)
}
function removeOption(id: string): void {
  model.value.options = model.value.options.filter((option) => option.id !== id)
  if (Array.isArray(model.value.standard_answer))
    model.value.standard_answer = model.value.standard_answer.filter((item) => item !== id)
}
function addOption(): void {
  model.value.options.push({ id: crypto.randomUUID(), content: '' })
}
</script>

<template>
  <div class="question-fields">
    <div class="field-grid">
      <label
        >题型<select v-model="model.type" aria-label="题型" @change="changeType">
          <option v-for="(label, type) in questionTypeLabels" :key="type" :value="type">
            {{ label }}
          </option>
        </select></label
      >
      <label
        >科目<input v-model="model.subject" aria-label="科目" required maxlength="100"
      /></label>
      <label
        >难度<select v-model="model.difficulty" aria-label="难度">
          <option value="EASY">简单</option>
          <option value="MEDIUM">中等</option>
          <option value="HARD">困难</option>
        </select></label
      >
      <label
        >知识点标签<input
          v-model="tagText"
          aria-label="知识点标签"
          placeholder="用逗号分隔"
          @input="changeTags"
      /></label>
    </div>
    <label
      >题干<textarea
        v-model="model.content"
        aria-label="题干"
        required
        rows="6"
        placeholder="支持 Markdown、$行内公式$ 与 $$独立公式$$"
      />
    </label>
    <label
      >上传题干图片（PNG / JPEG / WebP，最大 5 MiB）<input
        type="file"
        aria-label="上传题干图片"
        accept="image/png,image/jpeg,image/webp"
        :disabled="uploading"
        @change="upload($event, 'content')"
    /></label>
    <NAlert v-if="uploadFailure" type="error">{{ uploadFailure }}</NAlert>
    <p v-if="uploading" role="status">正在上传图片，请等待完成后保存。</p>
    <div v-if="isChoice" class="options-editor">
      <div v-for="(option, index) in model.options" :key="option.id" class="option-line">
        <label class="answer-check"
          ><input
            :type="model.type === 'SINGLE_CHOICE' ? 'radio' : 'checkbox'"
            name="correct-option"
            :aria-label="`正确选项 ${index + 1}`"
            :checked="
              Array.isArray(model.standard_answer) && model.standard_answer.includes(option.id)
            "
            @change="selectAnswer(option.id, ($event.target as HTMLInputElement).checked)"
          />正确</label
        >
        <label class="option-content"
          >选项 {{ index + 1
          }}<input v-model="option.content" :aria-label="`选项 ${index + 1}`" required
        /></label>
        <NButton :disabled="model.options.length <= 2" @click="removeOption(option.id)"
          >移除</NButton
        >
      </div>
      <NButton :disabled="model.options.length >= 8" @click="addOption">增加选项</NButton>
    </div>
    <label v-else-if="model.type === 'TRUE_FALSE'"
      >判断答案<select v-model="model.standard_answer" aria-label="判断答案">
        <option :value="true">真</option>
        <option :value="false">假</option>
      </select></label
    >
    <label v-else
      >参考答案（可选）<textarea
        :value="typeof model.standard_answer === 'string' ? model.standard_answer : ''"
        aria-label="参考答案"
        rows="3"
        @input="model.standard_answer = ($event.target as HTMLTextAreaElement).value || null"
      />
    </label>
    <label>解析（可选）<textarea v-model="model.explanation" aria-label="解析" rows="3" /></label>
    <label
      >上传解析图片<input
        type="file"
        aria-label="上传解析图片"
        accept="image/png,image/jpeg,image/webp"
        :disabled="uploading"
        @change="upload($event, 'explanation')"
    /></label>
    <section class="markdown-preview">
      <h3>题目预览</h3>
      <SafeMarkdown :content="model.content" data-testid="question-preview" /><template
        v-if="model.explanation"
        ><h4>解析</h4>
        <SafeMarkdown :content="model.explanation"
      /></template>
    </section>
  </div>
</template>

<style scoped>
.question-fields {
  display: grid;
  gap: 18px;
}
.field-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
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
.options-editor {
  display: grid;
  gap: 12px;
}
.option-line {
  display: flex;
  align-items: end;
  gap: 12px;
}
.option-content {
  flex: 1;
}
.answer-check {
  display: flex;
  align-items: center;
  padding-bottom: 10px;
}
.answer-check input {
  width: auto;
}
.markdown-preview {
  border: 1px solid #e5eaf2;
  padding: 18px;
  border-radius: 8px;
  background: #fafbfe;
}
.markdown-preview h3 {
  margin-top: 0;
}
</style>
