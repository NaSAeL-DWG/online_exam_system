<script setup lang="ts">
import { computed } from 'vue'
import { NCard, NTag } from 'naive-ui'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const copy = computed(
  () =>
    ({
      STUDENT: ['学生工作台', '账号已激活，考试列表和作答功能尚未开放。'],
      TEACHER: ['教师工作台', '维护共享题库、组卷与考试，处理学生审核和教学班。'],
      ADMIN: ['管理工作台', '管理账号和教学班，协作维护题库、试卷与考试。'],
    })[auth.user?.user_type ?? 'STUDENT'],
)
const guide = computed(
  () =>
    ({
      STUDENT: {
        title: '开始使用',
        description: '当前可维护联系方式与账号安全；考试列表、主动开始和作答尚未开放。',
      },
      TEACHER: {
        title: '从哪里开始',
        description: '从共享题库准备题目，在共享试卷组卷，再进入考试管理建立独立快照并发布。',
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
