<script setup lang="ts">
import { computed } from 'vue'
import MarkdownIt from 'markdown-it'
import DOMPurify from 'dompurify'
import { katex } from '@mdit/plugin-katex'
import 'katex/dist/katex.min.css'

const props = defineProps<{ content: string }>()
const markdown = new MarkdownIt({ html: false, linkify: false, breaks: true }).use(katex, {
  trust: false,
  throwOnError: false,
  maxExpand: 1000,
  maxSize: 10,
})
// 只展示经授权接口读取的不可变图片，禁用外部跟踪资源和内嵌 SVG。
markdown.renderer.rules.image = (tokens, index, options, env, renderer) => {
  const source = String(tokens[index]?.attrGet('src') ?? '')
  if (
    !/^\/api\/assets\/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(source)
  )
    return ''
  return renderer.renderToken(tokens, index, options)
}
// KaTeX 的根号与伸展括号需要 SVG；其输入受 trust:false 约束，再由 DOMPurify 清理。
const rendered = computed(() =>
  DOMPurify.sanitize(markdown.render(props.content), {
    FORBID_TAGS: ['style', 'iframe', 'object', 'embed'],
    FORBID_ATTR: ['srcset'],
  }),
)
</script>

<template><div class="safe-markdown" v-html="rendered" /></template>

<style scoped>
.safe-markdown {
  overflow-wrap: anywhere;
  line-height: 1.8;
}
.safe-markdown :deep(img) {
  max-width: 100%;
  max-height: 420px;
}
.safe-markdown :deep(pre) {
  padding: 14px;
  background: #f3f5f8;
  overflow: auto;
  border-radius: 8px;
}
.safe-markdown :deep(table) {
  border-collapse: collapse;
}
.safe-markdown :deep(td),
.safe-markdown :deep(th) {
  border: 1px solid #d9dfe9;
  padding: 8px;
}
</style>
