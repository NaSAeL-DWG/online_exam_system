<script setup lang="ts">
import { ref, useId, watch } from 'vue'
import NSelect from '../../components/ui/AppSelect.vue'
import { questionTypeLabels, type QuestionInput } from '../../api/questions'
import type { ContentFieldErrors } from '../contentValidation'
const model = defineModel<QuestionInput>({ required: true })
withDefaults(
  defineProps<{ errors?: ContentFieldErrors; section?: 'all' | 'basics' | 'properties' }>(),
  { section: 'all' },
)
const tagErrorId = `${useId()}-tags-error`
const tagHintId = `${useId()}-tags-hint`
const subjectErrorId = `${useId()}-subject-error`
const emit = defineEmits<{ typeChange: [] }>()
const tagText = ref(model.value.knowledge_tags.join(', '))
watch(
  () => model.value,
  (value) => {
    tagText.value = value.knowledge_tags.join(', ')
  },
)
function changeTags(): void {
  model.value.knowledge_tags = [
    ...new Set(
      tagText.value
        .split(/[,，]/)
        .map((tag) => tag.trim())
        .filter(Boolean),
    ),
  ]
}
function changeType(value: QuestionInput['type']): void {
  // 组件库重选当前项仍会发送更新，只有实际切换题型才重置评分依据。
  if (value === model.value.type) return
  model.value.type = value
  emit('typeChange')
}
</script>

<template>
  <section
    class="classification"
    :class="`classification--${section}`"
    :aria-label="section === 'properties' ? '题目属性' : '分类信息'"
  >
    <div class="section-heading">
      <h3>{{ section === 'properties' ? '题目属性' : '分类信息' }}</h3>
      <p class="muted">便于共享检索与后续组卷。</p>
    </div>
    <div class="form-grid two-columns">
      <label v-if="section !== 'properties'" class="field"
        >题型<NSelect
          :value="model.type"
          aria-label="题型"
          :options="Object.entries(questionTypeLabels).map(([value, label]) => ({ value, label }))"
          @update:value="changeType"
      /></label>
      <label v-if="section !== 'properties'" class="field"
        >科目<input
          v-model="model.subject"
          aria-label="科目"
          required
          maxlength="100"
          :aria-invalid="!!errors?.subject"
          :aria-describedby="errors?.subject ? subjectErrorId : undefined"
          placeholder="例如：高等数学"
        /><span v-if="errors?.subject" :id="subjectErrorId" class="field-error" role="alert">{{
          errors.subject
        }}</span></label
      >
      <label v-if="section !== 'basics'" class="field"
        >难度<NSelect
          v-model:value="model.difficulty"
          aria-label="难度"
          :options="[
            { value: 'EASY', label: '简单' },
            { value: 'MEDIUM', label: '中等' },
            { value: 'HARD', label: '困难' },
          ]"
      /></label>
      <label v-if="section !== 'basics'" class="field"
        >知识点标签<input
          v-model="tagText"
          aria-label="知识点标签"
          placeholder="用逗号分隔"
          :aria-invalid="!!errors?.knowledge_tags"
          :aria-describedby="`${tagHintId}${errors?.knowledge_tags ? ` ${tagErrorId}` : ''}`"
          @input="changeTags"
        /><span :id="tagHintId" class="muted">最多 30 个，每个 1—100 个字符。</span>
        <span v-if="errors?.knowledge_tags" :id="tagErrorId" class="field-error" role="alert">{{
          errors.knowledge_tags
        }}</span>
      </label>
    </div>
  </section>
</template>

<style scoped>
.section-heading {
  margin-bottom: 14px;
}
.field-error {
  color: var(--red-600);
  font-size: 12px;
}
h3,
p {
  margin: 0;
}
p {
  margin-top: 4px;
  font-size: 13px;
}
.form-grid {
  grid-template-columns: 0.85fr 1fr 0.75fr 1.5fr;
  gap: 16px;
}
.classification--basics .form-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}
.classification--basics .field:first-child {
  order: 2;
}
.classification--properties .field:first-child {
  order: 2;
}
.classification--basics .section-heading {
  display: none;
}
.classification--properties .form-grid {
  grid-template-columns: 1fr;
}
.classification--properties .section-heading p {
  display: none;
}
@media (max-width: 760px) {
  .form-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
