<script setup lang="ts">
import { ref } from 'vue'
import { NAlert } from 'naive-ui'
import { questionsApi, type QuestionInput } from '../api/questions'
import { errorMessage } from '../api/client'
import SafeMarkdown from './SafeMarkdown.vue'
import QuestionClassification from '../features/questions/QuestionClassification.vue'
import QuestionAnswerFields from '../features/questions/QuestionAnswerFields.vue'
import { changeQuestionType } from '../features/questions/questionDraft'
const model = defineModel<QuestionInput>({ required: true })
const emit = defineEmits<{ uploading: [value: boolean] }>()
const uploading = ref(false)
const uploadFailure = ref('')
async function upload(event: Event, field: 'content' | 'explanation'): Promise<void> {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  // 始终写回发起上传时的草稿，避免图片响应污染另一个题目。
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
</script>
<template>
  <div class="question-fields">
    <QuestionClassification v-model="model" @type-change="changeQuestionType(model)" />
    <NAlert v-if="uploadFailure" type="error">{{ uploadFailure }}</NAlert>
    <p v-if="uploading" role="status">正在上传图片，请等待完成后保存。</p>
    <div class="content-workspace">
      <section class="writing-column" aria-labelledby="content-title">
        <div class="section-heading">
          <h3 id="content-title">题目内容</h3>
          <p class="muted">支持 Markdown、公式和代码块。</p>
        </div>
        <label class="field"
          >题干<textarea
            v-model="model.content"
            aria-label="题干"
            required
            rows="7"
            placeholder="输入题干；行内公式使用 $…$，独立公式使用 $$…$$"
          />
        </label>
        <div class="upload-field">
          <label class="upload-trigger"
            ><span>选择题干图片</span
            ><input
              type="file"
              aria-label="上传题干图片"
              accept="image/png,image/jpeg,image/webp"
              :disabled="uploading"
              @change="upload($event, 'content')" /></label
          ><span class="muted">PNG / JPEG / WebP，最大 5 MiB</span>
        </div>
        <QuestionAnswerFields v-model="model" />
        <section aria-label="解题说明编辑区">
          <h3 id="explanation-title">答案解析</h3>
          <label class="field"
            >解析（可选）<textarea
              v-model="model.explanation"
              aria-label="解析"
              rows="4"
              placeholder="补充解题过程或评分说明"
            />
          </label>
          <div class="upload-field explanation-upload">
            <label class="upload-trigger"
              ><span>选择解析图片</span
              ><input
                type="file"
                aria-label="上传解析图片"
                accept="image/png,image/jpeg,image/webp"
                :disabled="uploading"
                @change="upload($event, 'explanation')"
            /></label>
          </div>
        </section>
      </section>
      <aside class="preview-column" aria-label="题目预览">
        <div class="preview-heading">
          <h3>题目预览</h3>
          <span class="muted">实时更新</span>
        </div>
        <SafeMarkdown :content="model.content" data-testid="question-preview" />
        <p v-if="!model.content" class="preview-empty">输入题干后，在这里检查公式、图片和排版。</p>
        <div v-if="model.options.length" class="preview-options">
          <p v-for="(option, index) in model.options" :key="option.id">
            <strong>{{ String.fromCharCode(65 + index) }}.</strong>
            {{ option.content || '尚未填写' }}
          </p>
        </div>
        <template v-if="model.explanation"
          ><h4>解析</h4>
          <SafeMarkdown :content="model.explanation"
        /></template>
      </aside>
    </div>
  </div>
</template>
<style scoped>
.question-fields {
  display: grid;
  gap: 24px;
  min-width: 0;
}
.content-workspace {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(0, 0.85fr);
  gap: 24px;
  align-items: start;
  border-top: 1px solid var(--color-border);
  padding-top: 24px;
}
.writing-column {
  display: grid;
  gap: 20px;
  min-width: 0;
}
.section-heading h3,
.section-heading p {
  margin: 0;
}
.section-heading p {
  font-size: 13px;
  margin-top: 4px;
}
h3 {
  font-size: 15px;
}
.upload-field {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  font-size: 12px;
  color: var(--color-muted);
}
.upload-trigger {
  position: relative;
  display: inline-flex;
  align-items: center;
  min-height: 32px;
  padding: 6px 12px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  color: var(--color-text);
  background: var(--color-surface);
  cursor: pointer;
}
.upload-trigger input {
  position: absolute;
  inset: 0;
  opacity: 0;
  cursor: pointer;
  width: 100%;
  height: 100%;
}
.upload-trigger:focus-within {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}
.upload-trigger:has(input:disabled) {
  opacity: 0.5;
  cursor: default;
}
.explanation-upload {
  margin-top: 12px;
}
.preview-column {
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  padding: 18px;
  min-width: 0;
  position: sticky;
  top: 0;
}
.preview-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  border-bottom: 1px solid var(--color-border);
  padding-bottom: 12px;
  margin-bottom: 14px;
}
.preview-heading h3 {
  margin: 0;
}
.preview-heading span,
.preview-empty {
  font-size: 12px;
}
.preview-empty {
  color: var(--color-muted);
  line-height: 1.8;
  padding: 16px 0;
}
.preview-options {
  display: grid;
  gap: 6px;
}
.preview-options p {
  margin: 0;
  font-size: 13px;
}
@media (max-width: 760px) {
  .content-workspace {
    grid-template-columns: 1fr;
  }
  .preview-column {
    position: static;
  }
}
</style>
