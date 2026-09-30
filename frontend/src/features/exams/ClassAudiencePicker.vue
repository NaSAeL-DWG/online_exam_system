<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { NAlert, NButton } from 'naive-ui'
import { examParticipantsApi } from '../../api/examParticipants'
import { errorMessage } from '../../api/client'
import type { TeachingClass } from '../../types'
import ListPager from '../../components/ListPager.vue'
import StatusBadge from '../../components/ui/StatusBadge.vue'

const selectedIds = defineModel<string[]>({ required: true })
defineProps<{ disabled: boolean }>()
const classes = ref<TeachingClass[]>([])
const query = ref('')
const page = ref(1)
const total = ref(0)
const loading = ref(false)
const failure = ref('')
let loadVersion = 0

async function load(value = 1): Promise<void> {
  const version = ++loadVersion
  page.value = value
  loading.value = true
  failure.value = ''
  try {
    const result = await examParticipantsApi.classes({ page: value, page_size: 10, q: query.value })
    // 候选分页独立于已选 ID；后发搜索结果优先，跨页选择始终保留。
    if (version === loadVersion) {
      classes.value = result.items
      total.value = result.total
    }
  } catch (error) {
    if (version === loadVersion) failure.value = errorMessage(error)
  } finally {
    if (version === loadVersion) loading.value = false
  }
}

onMounted(() => void load())
</script>

<template>
  <section class="class-audience-picker" aria-labelledby="class-audience-heading">
    <header class="picker-heading">
      <h3 id="class-audience-heading">按教学班补入</h3>
      <p class="muted">补入班级当前学生，跨班重叠会自动去重。</p>
    </header>
    <div class="class-search">
      <input
        v-model="query"
        class="form-control"
        aria-label="搜索补入班级"
        placeholder="搜索教学班"
        @keydown.enter.prevent="load()"
      />
      <NButton :loading="loading" @click="load()">查询补入班级</NButton>
    </div>
    <NAlert v-if="failure" type="error">{{ failure }}</NAlert>
    <div class="class-options" :aria-busy="loading">
      <label v-for="item in classes" :key="item.id" class="class-option">
        <input
          v-model="selectedIds"
          type="checkbox"
          :value="item.id"
          :aria-label="`选择班级 ${item.name}`"
          :disabled="item.status === 'ARCHIVED' || disabled"
        />
        <span class="class-option-copy"
          ><strong>{{ item.name }}</strong
          ><span>{{ item.student_count }} 名学生</span></span
        >
        <StatusBadge v-if="item.status === 'ARCHIVED'" label="已归档" />
      </label>
      <p v-if="!classes.length && !loading && !failure" class="picker-empty">
        未找到教学班，试试其他名称。
      </p>
      <p v-if="loading && !classes.length" class="picker-empty" role="status">正在加载教学班…</p>
    </div>
    <p class="selection-summary">
      已选 {{ selectedIds.length }} 个班级<span class="muted"> · 跨页保留</span>
    </p>
    <ListPager
      label="补入班级"
      :page="page"
      :page-size="10"
      :total="total"
      :loading="loading"
      @change="load"
    />
  </section>
</template>

<style scoped>
.class-audience-picker {
  min-width: 0;
}
.picker-heading h3 {
  margin: 0;
  font-size: 14px;
  font-weight: 650;
}
.picker-heading p {
  margin: 6px 0 16px;
  font-size: 12px;
}
.class-search {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 10px;
  margin-bottom: 14px;
  align-items: center;
}
.class-options {
  display: grid;
  max-height: 290px;
  overflow: auto;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
}
.class-option {
  display: flex;
  gap: 10px;
  align-items: center;
  padding: 12px 14px;
  cursor: pointer;
}
.class-option + .class-option {
  border-top: 1px solid var(--color-border);
}
.class-option:has(input:checked) {
  background: var(--color-primary-soft);
}
.class-option:has(input:disabled) {
  cursor: default;
  color: var(--color-muted);
}
.class-option input {
  width: 16px;
  height: 16px;
  accent-color: var(--color-primary);
  flex-shrink: 0;
}
.class-option-copy {
  display: grid;
  min-width: 0;
  flex: 1;
  gap: 4px;
}
.class-option-copy strong {
  font-size: 13px;
  font-weight: 550;
  overflow-wrap: anywhere;
}
.class-option-copy > span {
  color: var(--color-muted);
  font-size: 12px;
}
.picker-empty {
  color: var(--color-muted);
  margin: 0;
  padding: 24px 14px;
  font-size: 13px;
}
.selection-summary {
  margin: 14px 0 0;
  font-size: 12px;
}
@media (max-width: 480px) {
  .class-search {
    grid-template-columns: minmax(0, 1fr);
  }
  .class-search .n-button {
    justify-self: start;
  }
}
</style>
