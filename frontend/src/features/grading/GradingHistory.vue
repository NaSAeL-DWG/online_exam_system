<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { NAlert, NButton, NModal } from 'naive-ui'
import { gradingApi, type GradingHistoryEntry } from '../../api/grading'
import { errorMessage } from '../../api/client'
import { examTime } from '../attempts/examAvailability'
const props = defineProps<{ answerId: string }>()
const emit = defineEmits<{ close: [] }>()
const items = ref<GradingHistoryEntry[]>([])
const loading = ref(false)
const failure = ref('')
async function load(): Promise<void> {
  loading.value = true
  failure.value = ''
  try {
    items.value = (await gradingApi.history(props.answerId)).items
  } catch (error) {
    failure.value = errorMessage(error)
  } finally {
    loading.value = false
  }
}
onMounted(load)
</script>
<template>
  <NModal
    :show="true"
    preset="card"
    title="本题评分历史"
    class="responsive-modal responsive-modal--wide history-modal"
    @update:show="emit('close')"
  >
    <NAlert v-if="failure" class="form-alert" type="error"
      >{{ failure }} <NButton size="small" @click="load">重试读取历史</NButton></NAlert
    >
    <p v-if="loading" class="muted" role="status">正在读取评分历史…</p>
    <div v-else-if="items.length" class="history-list">
      <article v-for="entry in items" :key="entry.id">
        <header>
          <strong>{{ entry.actor?.real_name || '系统自动判分' }}</strong
          ><time :datetime="entry.created_at">{{ examTime(entry.created_at) }}（上海）</time>
        </header>
        <div class="history-score">
          {{ entry.old_score === null ? '未评分' : entry.old_score }} →
          {{ entry.new_score === null ? '待重判' : `${entry.new_score} 分` }}
        </div>
        <p class="history-reason">
          {{
            entry.reason ||
            (entry.method === 'AUTO' ? '按当前评分依据自动判分。' : '首次人工评分。')
          }}
        </p>
        <dl v-if="entry.old_comment || entry.new_comment">
          <div v-if="entry.old_comment">
            <dt>此前评语</dt>
            <dd>{{ entry.old_comment }}</dd>
          </div>
          <div v-if="entry.new_comment">
            <dt>本次评语</dt>
            <dd>{{ entry.new_comment }}</dd>
          </div>
        </dl>
        <span class="history-version"
          >{{ entry.method === 'AUTO' ? '自动判分' : '人工评分' }} · 评分依据版本
          {{ entry.grading_revision }}</span
        >
      </article>
    </div>
    <p v-else-if="!failure" class="muted">本题暂无评分历史。</p>
  </NModal>
</template>
<style scoped>
.history-list {
  display: grid;
  gap: 16px;
}
.history-list article {
  border: 1px solid var(--color-border);
  padding: 18px;
  border-radius: var(--radius-sm);
}
.history-list header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 10px;
  flex-wrap: wrap;
}
.history-list strong {
  font-size: 14px;
  font-weight: 600;
}
.history-list time,
.history-version {
  color: var(--color-muted);
  font-size: 12px;
}
.history-score {
  margin: 16px 0 10px;
  font-size: 21px;
  color: var(--color-primary);
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}
.history-reason {
  margin: 0 0 12px;
  white-space: pre-wrap;
}
dl {
  margin: 0 0 14px;
  display: grid;
  gap: 10px;
}
dt {
  color: var(--color-muted);
  font-size: 12px;
}
dd {
  margin: 4px 0 0;
  white-space: pre-wrap;
}
</style>
