<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import AppIcon from '../components/ui/AppIcon.vue'

const route = useRoute()
const registering = computed(() => route.name === 'register')
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
    <main class="auth-workspace" :class="{ 'auth-workspace--register': registering }">
      <aside v-if="!registering" class="auth-intro" aria-label="知衡考试平台">
        <div>
          <div class="brand">
            <span class="brand-symbol"><AppIcon name="book" :size="21" /></span>
            <span class="brand-name">知衡</span>
          </div>
          <div class="page-eyebrow">FOCUS ON WHAT MATTERS</div>
          <h2>专注每一道题。<br />认真每一场考试。</h2>
          <p>从考试准备、限时作答到阅卷反馈，<br />让每一步都有清晰的秩序。</p>
        </div>
        <p class="auth-intro-note">学生使用学号，教师使用工号。教师账号由管理员创建。</p>
      </aside>
      <section class="auth-task"><RouterView /></section>
    </main>
    <footer class="auth-footer">知衡 · 在线限时考试系统</footer>
  </div>
</template>
