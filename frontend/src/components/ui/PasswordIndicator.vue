<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    password: string
    confirmation?: string
    mode?: 'strength' | 'match'
  }>(),
  { mode: 'strength', confirmation: '' },
)

const indicator = computed(() => {
  if (props.mode === 'match') {
    if (!props.confirmation) return { label: '请再次输入密码', tone: 'neutral', width: 0 }
    return props.password === props.confirmation
      ? { label: '密码已匹配', tone: 'strong', width: 100 }
      : { label: '密码不匹配', tone: 'weak', width: 100 }
  }
  if (!props.password) return { label: '密码强度：尚未填写', tone: 'neutral', width: 0 }
  const length = Array.from(props.password).length
  const categories = [/[a-z]/, /[A-Z]/, /\d/, /[^a-zA-Z0-9]/].filter((category) =>
    category.test(props.password),
  ).length
  // 强度仅辅助选密码；不增加后端没有要求的字符种类或组合限制。
  if (length >= 12 && categories >= 3) return { label: '密码强度：强', tone: 'strong', width: 100 }
  if (length >= 10 && categories >= 2) return { label: '密码强度：中', tone: 'medium', width: 66 }
  return { label: '密码强度：弱', tone: 'weak', width: 33 }
})
</script>

<template>
  <div
    class="password-feedback"
    :class="`password-feedback--${indicator.tone}`"
    role="status"
    aria-live="polite"
  >
    <div class="password-meter" aria-hidden="true">
      <span :style="{ width: `${indicator.width}%` }" />
    </div>
    <span>{{ indicator.label }}</span>
    <small v-if="mode === 'strength'">仅作参考，密码需10—256个字符</small>
  </div>
</template>

<style scoped>
.password-feedback {
  width: 100%;
  margin-top: 9px;
  color: var(--color-muted);
  font-size: 12px;
  line-height: 1.5;
}
.password-meter {
  height: 4px;
  background: #e7ebe8;
  border-radius: 2px;
  overflow: hidden;
  margin-bottom: 5px;
}
.password-meter span {
  display: block;
  height: 100%;
  background: #86958c;
  transition: width 160ms ease;
}
.password-feedback--weak .password-meter span {
  background: #b8514b;
}
.password-feedback--medium .password-meter span {
  background: #a47a28;
}
.password-feedback--strong .password-meter span {
  background: #4b8672;
}
.password-feedback small {
  display: block;
  margin-top: 2px;
}
</style>
