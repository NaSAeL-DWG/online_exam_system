<script setup lang="ts">
import AppIcon from '../components/ui/AppIcon.vue'
</script>

<template>
  <div class="auth-shell">
    <header class="auth-topbar">
      <RouterLink class="brand" to="/login" aria-label="知衡首页">
        <span class="brand-symbol"><AppIcon name="book" :size="21" /></span>
        <span class="brand-name">知衡</span>
        <span class="brand-caption">在线考试系统</span>
      </RouterLink>
      <span class="auth-topbar-note">教学 · 考试 · 协作</span>
    </header>
    <main class="auth-workspace">
      <section class="auth-task"><RouterView /></section>
      <aside class="auth-support" aria-label="账号使用说明">
        <div>
          <p class="auth-support-label">账号使用说明</p>
          <h2>使用你的机构账号</h2>
          <ul class="auth-support-list">
            <li>
              <AppIcon name="user" :size="18" />
              <div><strong>学生</strong><span>使用学号登录，新账号需提交注册申请。</span></div>
            </li>
            <li>
              <AppIcon name="class" :size="18" />
              <div><strong>教师</strong><span>使用工号登录，由管理员创建账号。</span></div>
            </li>
            <li>
              <AppIcon name="shield" :size="18" />
              <div><strong>管理员</strong><span>使用预置管理账号维护系统。</span></div>
            </li>
          </ul>
        </div>
        <div class="auth-help">
          <strong>无法登录？</strong>
          <p>请联系系统管理员核验身份或重置密码。</p>
        </div>
      </aside>
    </main>
    <footer class="auth-footer">知衡 · 在线限时考试系统</footer>
  </div>
</template>
