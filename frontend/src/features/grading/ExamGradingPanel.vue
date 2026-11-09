<script setup lang="ts">
import { computed, ref } from 'vue'
import { NAlert, NButton } from 'naive-ui'
import { gradingApi } from '../../api/grading'
import { errorMessage } from '../../api/client'
import { useAuthStore } from '../../stores/auth'
import SurfacePanel from '../../components/ui/SurfacePanel.vue'
import ExamAttemptList from './ExamAttemptList.vue'
import ExamFinalResults from './ExamFinalResults.vue'
const props = defineProps<{ examId: string; cancelled: boolean }>()
const auth = useAuthStore()
const canGrade = computed(() => auth.user?.user_type === 'TEACHER')
const mode = ref<'attempts' | 'results'>('attempts')
const refreshKey = ref(0)
const syncing = ref(false)
const failure = ref('')
const success = ref('')
async function synchronize(): Promise<void> {
  if (syncing.value) return
  syncing.value = true
  failure.value = ''
  success.value = ''
  try {
    const result = await gradingApi.refresh(props.examId)
    success.value = `已同步判分与任务：处理 ${result.graded_attempts} 份答卷，分配 ${result.assigned_tasks} 份任务。`
    refreshKey.value += 1
  } catch (error) {
    failure.value = errorMessage(error)
  } finally {
    syncing.value = false
  }
}
</script>
<template>
  <SurfacePanel
    :title="canGrade ? '答卷与成绩' : '阅卷进度与成绩'"
    :description="
      canGrade
        ? '查看有效答卷，进入教师评分或核对最终成绩。'
        : '查看判分状态、指定教师与最终成绩，跟进考试阅卷进度。'
    "
  >
    <template #actions
      ><NButton :disabled="cancelled" :loading="syncing" @click="synchronize"
        >同步判分与任务</NButton
      ></template
    >
    <NAlert v-if="failure" class="form-alert" type="error">{{ failure }}</NAlert>
    <NAlert v-if="success" class="form-alert" type="success">{{ success }}</NAlert>
    <div class="list-filter" aria-label="答卷成绩范围">
      <NButton
        :type="mode === 'attempts' ? 'primary' : 'default'"
        :aria-pressed="mode === 'attempts'"
        @click="mode = 'attempts'"
        >全部答卷</NButton
      ><NButton
        :type="mode === 'results' ? 'primary' : 'default'"
        :aria-pressed="mode === 'results'"
        @click="mode = 'results'"
        >最终成绩</NButton
      >
    </div>
    <ExamAttemptList v-if="mode === 'attempts'" :key="refreshKey" :exam-id="examId" />
    <ExamFinalResults v-else :key="refreshKey" :exam-id="examId" />
  </SurfacePanel>
</template>
