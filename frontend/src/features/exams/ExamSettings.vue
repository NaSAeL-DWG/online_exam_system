<script setup lang="ts">
import type { Exam } from '../../api/exams'
import MemberPicker from '../../components/MemberPicker.vue'
import SurfacePanel from '../../components/ui/SurfacePanel.vue'
const model = defineModel<Exam>({ required: true })
const start = defineModel<string>('start', { required: true })
const end = defineModel<string>('end', { required: true })
const duration = defineModel<number | null>('duration', { required: true })
defineProps<{ disabled: boolean; savedExam: Exam }>()
</script>

<template>
  <div class="settings-grid">
    <SurfacePanel title="基本信息"
      ><fieldset :disabled="disabled" class="settings-fields">
        <label class="field"
          >考试名称<input v-model="model.title" aria-label="考试名称" required /></label
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
            placeholder="考试要求与作答说明（可选）"
          />
        </label></fieldset
    ></SurfacePanel>
    <SurfacePanel title="时间与作答"
      ><fieldset :disabled="disabled" class="settings-fields">
        <label class="field"
          >开始时间（上海）<input
            v-model="start"
            aria-label="开始时间（上海）"
            type="datetime-local" /></label
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
            min="1"
            step="1" /></label
        ><label class="field"
          >最多作答次数<input
            v-model.number="model.max_attempts"
            aria-label="最多作答次数"
            type="number"
            min="1"
            step="1"
            required
        /></label>
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
        /></label>
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
      ><MemberPicker
        v-if="savedExam.status === 'DRAFT'"
        v-model="model.grader_ids"
        kind="teacher"
        staff-teachers
        :disabled="disabled"
        :selected-members="savedExam.graders"
      />
      <p v-else class="grader-summary">
        {{ savedExam.graders.map((teacher) => teacher.real_name).join('、') || '未指定阅卷教师' }}
      </p></SurfacePanel
    >
  </div>
</template>
<style scoped>
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
