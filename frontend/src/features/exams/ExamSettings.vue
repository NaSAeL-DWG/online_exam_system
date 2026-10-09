<script setup lang="ts">
import { ref, useId, watch } from 'vue'
import type { Exam } from '../../api/exams'
import MemberPicker from '../../components/MemberPicker.vue'
import SurfacePanel from '../../components/ui/SurfacePanel.vue'
import {
  numberError,
  textError,
  useContentValidation,
  type ContentFieldErrors,
} from '../contentValidation'
const model = defineModel<Exam>({ required: true })
const start = defineModel<string>('start', { required: true })
const end = defineModel<string>('end', { required: true })
const duration = defineModel<number | null>('duration', { required: true })
defineProps<{ disabled: boolean; savedExam: Exam }>()
const settingsRoot = ref<HTMLElement | null>(null)
const errorPrefix = useId()
const {
  errors,
  validate: validateFields,
  resetValidation,
} = useContentValidation(() => {
  const errors: ContentFieldErrors = {}
  const titleIssue = textError(model.value.title, '考试名称', 200, true)
  const descriptionIssue = textError(model.value.description, '考试说明', 100000)
  if (titleIssue) errors.title = titleIssue
  if (descriptionIssue) errors.description = descriptionIssue
  if (start.value && end.value && start.value >= end.value)
    errors.start = '开始时间须早于结束时间。'
  // 草稿允许暂不填写时间；有值的分钟数换算后须符合后端整秒契约。
  if (String(duration.value ?? '').trim()) {
    const minutes = Number(duration.value)
    const seconds = minutes * 60
    if (!Number.isFinite(minutes) || minutes <= 0) errors.duration = '作答时长须大于 0。'
    else if (minutes > 10080) errors.duration = '作答时长不能超过 10080 分钟。'
    else if (seconds < 1 || Math.abs(seconds - Math.round(seconds)) > 0.000001)
      errors.duration = '作答时长须为整秒，最少 1 秒。'
  }
  const attemptsIssue = numberError(model.value.max_attempts, '最多作答次数', {
    minimum: 1,
    maximum: 100,
    decimalPlaces: 0,
  })
  const passIssue = numberError(model.value.pass_percentage, '及格百分比', {
    minimum: 0,
    maximum: 100,
    decimalPlaces: 2,
  })
  if (attemptsIssue) errors.max_attempts = attemptsIssue
  if (passIssue) errors.pass_percentage = passIssue
  if (model.value.grader_ids.length > 100) errors.grader_ids = '最多指定 100 位阅卷教师。'
  return errors
})
function validate(focus = true): boolean {
  return validateFields(settingsRoot.value, focus)
}
watch(model, resetValidation)
defineExpose({ validate, resetValidation })
</script>

<template>
  <div ref="settingsRoot" class="settings-grid">
    <SurfacePanel title="基本信息"
      ><fieldset :disabled="disabled" class="settings-fields">
        <label class="field"
          >考试名称<input
            v-model="model.title"
            aria-label="考试名称"
            required
            maxlength="200"
            :aria-invalid="!!errors.title"
            :aria-describedby="errors.title ? `${errorPrefix}-title-error` : undefined"
          /><span
            v-if="errors.title"
            :id="`${errorPrefix}-title-error`"
            class="field-error"
            role="alert"
            >{{ errors.title }}</span
          ></label
        ><label class="field"
          >参考范围<select v-model="model.audience_type" aria-label="参考范围">
            <option value="RESTRICTED">限定名单</option>
            <option value="PUBLIC">全部激活学生</option>
          </select></label
        ><label class="field full-width"
          >考试说明<textarea
            v-model="model.description"
            aria-label="考试说明"
            rows="3"
            maxlength="100000"
            :aria-invalid="!!errors.description"
            :aria-describedby="errors.description ? `${errorPrefix}-description-error` : undefined"
            placeholder="考试要求与作答说明（可选）"
          />
          <span
            v-if="errors.description"
            :id="`${errorPrefix}-description-error`"
            class="field-error"
            role="alert"
            >{{ errors.description }}</span
          >
        </label>
      </fieldset></SurfacePanel
    >
    <SurfacePanel title="时间与作答"
      ><fieldset :disabled="disabled" class="settings-fields">
        <label class="field"
          >开始时间（上海）<input
            v-model="start"
            aria-label="开始时间（上海）"
            type="datetime-local"
            :aria-invalid="!!errors.start"
            :aria-describedby="errors.start ? `${errorPrefix}-start-error` : undefined"
          /><span
            v-if="errors.start"
            :id="`${errorPrefix}-start-error`"
            class="field-error"
            role="alert"
            >{{ errors.start }}</span
          ></label
        ><label class="field"
          >结束时间（上海）<input
            v-model="end"
            aria-label="结束时间（上海）"
            type="datetime-local" /></label
        ><label class="field"
          >作答时长（分钟）<input
            v-model.number="duration"
            aria-label="作答时长（分钟）"
            type="number"
            min="0.016666666666666666"
            max="10080"
            step="0.016666666666666666"
            :aria-invalid="!!errors.duration"
            :aria-describedby="
              errors.duration ? `${errorPrefix}-duration-error` : `${errorPrefix}-duration-hint`
            "
          /><span :id="`${errorPrefix}-duration-hint`" class="muted"
            >可暂不填写；有值时须为整秒，最多 10080 分钟。</span
          ><span
            v-if="errors.duration"
            :id="`${errorPrefix}-duration-error`"
            class="field-error"
            role="alert"
            >{{ errors.duration }}</span
          ></label
        ><label class="field"
          >最多作答次数<input
            v-model.number="model.max_attempts"
            aria-label="最多作答次数"
            type="number"
            min="1"
            max="100"
            step="1"
            required
            :aria-invalid="!!errors.max_attempts"
            :aria-describedby="errors.max_attempts ? `${errorPrefix}-attempts-error` : undefined"
          /><span
            v-if="errors.max_attempts"
            :id="`${errorPrefix}-attempts-error`"
            class="field-error"
            role="alert"
            >{{ errors.max_attempts }}</span
          ></label
        >
      </fieldset>
      <p class="settings-note muted">每次作答的截止时间不晚于全场结束时间。</p></SurfacePanel
    >
    <SurfacePanel title="评分与展示"
      ><fieldset :disabled="disabled" class="settings-fields">
        <label class="field"
          >多选评分<select v-model="model.multiple_choice_mode" aria-label="多选评分">
            <option value="EXACT">完全一致得分</option>
            <option value="PARTIAL">无错选按比例得分</option>
          </select></label
        ><label class="field"
          >及格百分比<input
            v-model="model.pass_percentage"
            aria-label="及格百分比"
            type="number"
            min="0"
            max="100"
            step="0.01"
            required
            :aria-invalid="!!errors.pass_percentage"
            :aria-describedby="errors.pass_percentage ? `${errorPrefix}-pass-error` : undefined"
          /><span
            v-if="errors.pass_percentage"
            :id="`${errorPrefix}-pass-error`"
            class="field-error"
            role="alert"
            >{{ errors.pass_percentage }}</span
          ></label
        >
        <div class="check-options full-width">
          <label
            ><input v-model="model.shuffle_questions" type="checkbox" aria-label="题目乱序" /><span
              >题目乱序</span
            ></label
          ><label
            ><input v-model="model.shuffle_options" type="checkbox" aria-label="选项乱序" /><span
              >选项乱序</span
            ></label
          ><label
            ><input v-model="model.allow_review" type="checkbox" aria-label="公布后允许回看" /><span
              >公布后允许回看答案与解析</span
            ></label
          >
        </div>
      </fieldset></SurfacePanel
    >
    <SurfacePanel title="指定阅卷教师" description="含简答题时，发布前至少指定一位激活教师。"
      ><div
        v-if="savedExam.status === 'DRAFT'"
        tabindex="-1"
        :aria-invalid="!!errors.grader_ids"
        :aria-describedby="errors.grader_ids ? `${errorPrefix}-graders-error` : undefined"
      >
        <MemberPicker
          v-if="savedExam.status === 'DRAFT'"
          v-model="model.grader_ids"
          kind="teacher"
          staff-teachers
          :disabled="disabled"
          :selected-members="savedExam.graders"
        />
        <p
          v-if="errors.grader_ids"
          :id="`${errorPrefix}-graders-error`"
          class="field-error"
          role="alert"
        >
          {{ errors.grader_ids }}
        </p>
      </div>
      <p v-else class="grader-summary">
        {{ savedExam.graders.map((teacher) => teacher.real_name).join('、') || '未指定阅卷教师' }}
      </p></SurfacePanel
    >
  </div>
</template>
<style scoped>
.field-error {
  color: #b42318;
  font-size: 12px;
}
.settings-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 20px;
  align-items: start;
}
.settings-fields {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
  padding: 0;
  border: 0;
  min-width: 0;
}
.full-width {
  grid-column: 1 / -1;
}
.settings-note {
  font-size: 12px;
  margin-bottom: 0;
}
.check-options {
  display: grid;
  gap: 14px;
  border-top: 1px solid var(--color-border);
  padding-top: 18px;
}
.check-options label {
  display: flex;
  gap: 10px;
  align-items: center;
  font-size: 13px;
}
.check-options input {
  width: 16px;
  height: 16px;
  accent-color: var(--color-primary);
}
.grader-summary {
  margin: 0;
  color: var(--color-muted);
}
@media (max-width: 1050px) {
  .settings-grid {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 600px) {
  .settings-fields {
    grid-template-columns: 1fr;
  }
}
</style>
