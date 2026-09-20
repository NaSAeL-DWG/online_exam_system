<script setup lang="ts">
import { computed } from 'vue'
import { NCard, NTag } from 'naive-ui'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const copy = computed(
  () =>
    ({
      STUDENT: ['学生工作台', '审核通过后，考试将在这里集中展示。'],
      TEACHER: ['教师工作台', '处理学生审核，维护所负责的教学班。'],
      ADMIN: ['管理工作台', '创建教师、维护账号状态并配置教学班。'],
    })[auth.user?.user_type ?? 'STUDENT'],
)
</script>

<template>
  <div class="page-stack">
    <header class="page-title">
      <div>
        <p class="eyebrow accent">工作台</p>
        <h1>{{ copy[0] }}</h1>
        <p>{{ copy[1] }}</p>
      </div>
      <NTag type="success" round>账号已激活</NTag>
    </header>
    <div class="metric-grid">
      <NCard
        ><span class="metric-label">当前身份</span
        ><strong>{{
          auth.user?.user_type === 'STUDENT'
            ? '学生'
            : auth.user?.user_type === 'TEACHER'
              ? '教师'
              : '管理员'
        }}</strong></NCard
      >
      <NCard
        ><span class="metric-label">登录账号</span
        ><strong>{{ auth.user?.login_name }}</strong></NCard
      >
      <NCard><span class="metric-label">系统状态</span><strong>运行正常</strong></NCard>
    </div>
    <NCard title="迭代 1 已开放能力"
      ><p class="muted">
        身份认证、学生注册审核、账号管理与教学班维护已经接入。题库与考试能力将在后续迭代开放。
      </p></NCard
    >
  </div>
</template>
