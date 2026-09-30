<script setup lang="ts">
defineProps<{ title?: string; description?: string }>()
</script>

<template>
  <section class="surface-panel">
    <header v-if="title || description || $slots.actions" class="surface-panel-header">
      <div>
        <h2 v-if="title">{{ title }}</h2>
        <p v-if="description">{{ description }}</p>
      </div>
      <div v-if="$slots.actions" class="surface-panel-actions"><slot name="actions" /></div>
    </header>
    <div class="surface-panel-body"><slot /></div>
  </section>
</template>
