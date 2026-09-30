<script setup lang="ts">
import { computed } from 'vue'
import { NButton } from 'naive-ui'
const props = defineProps<{
  page: number
  pageSize: number
  total: number
  loading: boolean
  label: string
}>()
const emit = defineEmits<{ change: [page: number] }>()
const pages = computed(() => Math.max(1, Math.ceil(props.total / props.pageSize)))
</script>
<template>
  <nav class="list-pager" :aria-label="`${label}分页`">
    <span class="muted">共 {{ total }} 条 · 第 {{ page }} / {{ pages }} 页</span>
    <div class="pager-buttons">
      <NButton
        size="small"
        :aria-label="`${label}上一页`"
        :disabled="loading || page <= 1"
        @click="emit('change', page - 1)"
        >上一页</NButton
      ><NButton
        size="small"
        :aria-label="`${label}下一页`"
        :disabled="loading || page >= pages"
        @click="emit('change', page + 1)"
        >下一页</NButton
      >
    </div>
  </nav>
</template>
<style scoped>
.list-pager {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  padding-top: 18px;
  font-size: 12px;
}
.pager-buttons {
  display: flex;
  gap: 8px;
}
@media (max-width: 420px) {
  .list-pager {
    gap: 10px;
  }
}
</style>
