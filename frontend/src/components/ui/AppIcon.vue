<script setup lang="ts">
import { computed } from 'vue'
const props = withDefaults(defineProps<{ name: string; size?: number }>(), { size: 20 })

// 图标只传达视觉信息；可访问名称由所在按钮或链接提供。
const paths: Record<string, string[]> = {
  home: ['M3 10 12 3l9 7', 'M5 9v12h5v-7h4v7h5V9'],
  users: [
    'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2',
    'M16 3a4 4 0 0 1 0 8',
    'M22 21v-2a4 4 0 0 0-3-3.87',
    'M13 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0',
  ],
  user: ['M20 21v-2a7 7 0 0 0-14 0v2', 'M16 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0'],
  check: ['m5 12 4 4L19 6'],
  class: ['M3 3h18v13H3z', 'M8 21h8', 'M12 16v5', 'M7 7h10M7 11h6'],
  book: ['M12 5v16', 'M12 5C9 3 5 3 2 4v15c3-1 7-1 10 2 3-3 7-3 10-2V4c-3-1-7-1-10 1'],
  paper: ['M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z', 'M14 2v6h6M8 12h8M8 16h8'],
  exam: [
    'M8 4H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2h-3',
    'M8 2h8v4H8z',
    'm7 13 3 3 7-7',
  ],
  shield: ['M12 3 3 7v5c0 5 9 10 9 10s9-5 9-10V7z', 'm8 12 3 3 5-6'],
  contact: [
    'M4 3h16v18H4z',
    'M2 7h4M2 12h4M2 17h4',
    'M16 8a2 2 0 1 1-4 0 2 2 0 0 1 4 0',
    'M10 17v-1a4 4 0 0 1 8 0v1',
  ],
  menu: ['M3 6h18M3 12h18M3 18h18'],
  close: ['m6 6 12 12M6 18 18 6'],
  'arrow-right': ['M4 12h16m-6-6 6 6-6 6'],
  'arrow-left': ['M20 12H4m6-6-6 6 6 6'],
  plus: ['M12 5v14M5 12h14'],
  search: ['M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0', 'm16 16 6 6'],
  logout: ['M9 3H4v18h5M9 12h12m-5-5 5 5-5 5'],
  clock: ['M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0', 'M12 6v6l4 2'],
  edit: ['m16 3 5 5M3 21l4-1L21 6l-4-4L3 16z'],
  'check-circle': ['M22 11v1a10 10 0 1 1-6-9', 'm9 11 3 3L22 4'],
  alert: ['M12 3 2 21h20z', 'M12 9v5M12 18h.01'],
  info: ['M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0', 'M12 11v6M12 7h.01'],
}
const iconPaths = computed(() => paths[props.name] ?? paths.info)
</script>

<template>
  <svg
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.65"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
    focusable="false"
  >
    <path v-for="(path, index) in iconPaths" :key="index" :d="path" />
  </svg>
</template>
