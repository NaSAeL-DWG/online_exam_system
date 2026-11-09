<template>
  <section class="password-requirements" aria-label="密码要求">
    <h3>密码要求</h3>
    <p>请输入 10—256 个字符。</p>
    <p>密码强度提示仅供参考，不限制字符种类或组合。</p>
  </section>
</template>

<style scoped>
.password-requirements {
  margin-bottom: 24px;
  padding: 16px 18px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--neutral-50);
  font-size: 13px;
  line-height: 1.7;
}
.password-requirements h3 {
  margin: 0 0 6px;
  font-size: 13px;
  font-weight: 600;
}
.password-requirements p {
  margin: 0;
  color: var(--color-muted);
}
</style>
