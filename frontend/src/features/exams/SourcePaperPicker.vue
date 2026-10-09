<script setup lang="ts">
import { computed, ref, useId, watch } from 'vue'
import { NAlert, NButton } from 'naive-ui'
import { papersApi, type PaperSummary } from '../../api/papers'
import { usePagedList } from '../../composables/usePagedList'
import ListPager from '../../components/ListPager.vue'
const model = defineModel<string>({ required: true })
defineProps<{ error?: string }>()
const errorId = `${useId()}-source-error`
const { items, page, total, query, loading, failure, load, changePage } = usePagedList(
  papersApi.list,
)
const selected = ref<PaperSummary | null>(null)
watch(model, (id) => {
  selected.value = items.value.find((paper) => paper.id === id) ?? selected.value
})
const offPageSelection = computed(
  () => selected.value && !items.value.some((paper) => paper.id === selected.value!.id),
)
</script>
<template>
  <section class="source-picker" aria-label="试卷选择工作区">
    <h3>选择来源试卷</h3>
    <p class="muted">创建时复制题目与分值，形成这场考试的独立快照。</p>
    <div class="source-search">
      <input
        v-model="query"
        class="form-control"
        aria-label="搜索来源试卷"
        placeholder="搜索试卷名称"
        @keydown.enter.prevent="changePage(1)"
      /><NButton :loading="loading" @click="changePage(1)">查询来源试卷</NButton>
    </div>
    <NAlert v-if="failure" class="form-alert" type="error"
      >{{ failure }} <NButton size="small" @click="load">重试加载试卷</NButton></NAlert
    ><label class="field"
      >来源试卷<select
        v-model="model"
        aria-label="来源试卷"
        required
        :aria-invalid="!!error"
        :aria-describedby="error ? errorId : undefined"
      >
        <option value="" disabled>选择来源试卷</option>
        <option v-if="offPageSelection && selected" :value="selected.id">
          {{ selected.title }}
        </option>
        <option
          v-for="paper in items"
          :key="paper.id"
          :value="paper.id"
          :disabled="paper.status === 'ARCHIVED'"
        >
          {{ paper.title }}{{ paper.status === 'ARCHIVED' ? '（已归档）' : '' }}
        </option></select
      ><span v-if="error" :id="errorId" class="field-error" role="alert">{{ error }}</span></label
    >
    <p v-if="selected" class="source-summary">
      {{ selected.question_count }} 道题 · 总分 {{ selected.total_score }} 分
    </p>
    <ListPager
      label="来源试卷"
      :page="page"
      :page-size="20"
      :total="total"
      :loading="loading"
      @change="changePage"
    />
  </section>
</template>
<style scoped>
.field-error {
  color: #b42318;
  font-size: 12px;
}
.source-picker {
  border-top: 1px solid var(--color-border);
  padding-top: 22px;
}
h3 {
  font-size: 15px;
  margin: 0;
}
.source-picker > p.muted {
  font-size: 12px;
  margin: 5px 0 16px;
}
.source-search {
  display: flex;
  gap: 10px;
  margin-bottom: 16px;
}
.source-search input {
  flex: 1;
  min-width: 0;
}
.source-summary {
  color: var(--color-primary);
  font-size: 13px;
  margin: 10px 0 0;
}
@media (max-width: 480px) {
  .source-search {
    flex-wrap: wrap;
  }
  .source-search input {
    flex-basis: 100%;
  }
}
</style>
