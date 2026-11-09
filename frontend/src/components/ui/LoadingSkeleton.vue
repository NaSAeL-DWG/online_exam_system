<script setup lang="ts">
withDefaults(
  defineProps<{
    rows?: number
    variant?: 'list' | 'table' | 'detail'
    label?: string
  }>(),
  { rows: 3, variant: 'list', label: '正在加载，请稍候' },
)
</script>

<template>
  <div
    class="loading-skeleton"
    :class="`loading-skeleton--${variant}`"
    role="status"
    aria-live="polite"
    aria-busy="true"
  >
    <span class="visually-hidden">{{ label }}</span>
    <div aria-hidden="true">
      <div v-for="row in rows" :key="row" class="loading-skeleton-row">
        <div class="loading-skeleton-copy">
          <span class="skeleton-line skeleton-line--title" />
          <span class="skeleton-line skeleton-line--detail" />
        </div>
        <span class="skeleton-line skeleton-line--meta" />
      </div>
    </div>
  </div>
</template>
