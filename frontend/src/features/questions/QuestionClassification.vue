<script setup lang="ts">
import { ref, useId, watch } from 'vue'
import { questionTypeLabels, type QuestionInput } from '../../api/questions'
import type { ContentFieldErrors } from '../contentValidation'
const model = defineModel<QuestionInput>({ required: true })
defineProps<{ errors?: ContentFieldErrors }>()
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
</script>

<template>
  <section class="classification" aria-labelledby="classification-title">
    <div class="section-heading">
      <h3 id="classification-title">分类信息</h3>
      <p class="muted">便于共享检索与后续组卷。</p>
    </div>
    <div class="form-grid two-columns">
      <label class="field"
        >题型<select v-model="model.type" aria-label="题型" @change="emit('typeChange')">
          <option v-for="(label, type) in questionTypeLabels" :key="type" :value="type">
            {{ label }}
          </option>
        </select></label
      >
      <label class="field"
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
      <label class="field"
        >难度<select v-model="model.difficulty" aria-label="难度">
          <option value="EASY">简单</option>
          <option value="MEDIUM">中等</option>
          <option value="HARD">困难</option>
        </select></label
      >
      <label class="field"
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
  color: #b42318;
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
@media (max-width: 760px) {
  .form-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
