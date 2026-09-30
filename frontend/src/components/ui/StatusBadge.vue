<script setup lang="ts">
withDefaults(
  defineProps<{ label: string; tone?: 'neutral' | 'success' | 'warning' | 'danger' | 'info' }>(),
  { tone: 'neutral' },
)
</script>

<template>
  <span class="status-badge" :class="`status-badge--${tone}`"
    ><span aria-hidden="true" class="status-dot" />{{ label }}</span
  >
</template>
