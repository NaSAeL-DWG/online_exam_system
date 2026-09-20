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
const guide = computed(
  () =>
    ({
      STUDENT: {
        title: '开始使用',
        description: '考试开放后可从工作台查看可参加的考试，并按考试说明开始作答。',
      },
      TEACHER: {
        title: '从哪里开始',
        description: '从左侧进入学生审核或教学班；如需更新密码，可进入账号安全。',
      },
      ADMIN: {
        title: '从哪里开始',
        description: '从左侧进入账号管理创建教师，或进入教学班配置负责教师和学生成员。',
      },
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
      <NCard><span class="metric-label">登录状态</span><strong>已登录</strong></NCard>
    </div>
    <NCard :title="guide.title"
      ><p class="muted">{{ guide.description }}</p></NCard
    >
  </div>
</template>
