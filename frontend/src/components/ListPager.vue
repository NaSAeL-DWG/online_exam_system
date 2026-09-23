<script setup lang="ts">
import { computed } from 'vue'
import { NButton, NSpace } from 'naive-ui'

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
  <NSpace justify="end" align="center" class="list-pager">
    <span class="muted">共 {{ total }} 条 · 第 {{ page }} / {{ pages }} 页</span>
    <NButton
      :aria-label="`${label}上一页`"
      :disabled="loading || page <= 1"
      @click="emit('change', page - 1)"
      >上一页</NButton
    >
    <NButton
      :aria-label="`${label}下一页`"
      :disabled="loading || page >= pages"
      @click="emit('change', page + 1)"
      >下一页</NButton
    >
  </NSpace>
</template>

<style scoped>
.list-pager {
  margin-top: 18px;
}
</style>
