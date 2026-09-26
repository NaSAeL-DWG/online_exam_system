<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { NAlert, NButton, NInput, NSelect, NSpace } from 'naive-ui'
import { identityApi } from '../api/identity'
import { errorMessage } from '../api/client'
import type { UserSummary } from '../types'
import ListPager from './ListPager.vue'

const props = withDefaults(
  defineProps<{
    modelValue: string[]
    kind: 'teacher' | 'student'
    selectedMembers?: UserSummary[]
    excludedIds?: string[]
    staffTeachers?: boolean
  }>(),
  { selectedMembers: () => [], excludedIds: () => [] },
)
const emit = defineEmits<{ 'update:modelValue': [value: string[]] }>()
const query = ref('')
const page = ref(1)
const pageSize = 20
const total = ref(0)
const loading = ref(false)
const failure = ref('')
const candidates = ref<UserSummary[]>([])
const selectedCache = ref<UserSummary[]>([...props.selectedMembers])
const label = computed(() => (props.kind === 'teacher' ? '教师' : '学生'))
let loadVersion = 0

// 只保留当前页与已选成员，翻页和搜索均不会丢失已有教师关联及其姓名。
const options = computed(() => {
  const users = new Map<string, UserSummary>()
  for (const user of [...selectedCache.value, ...props.selectedMembers, ...candidates.value]) {
    if (!props.excludedIds.includes(user.id)) users.set(user.id, user)
  }
  return [...users.values()]
    .filter(
      (user) =>
        candidates.value.some((candidate) => candidate.id === user.id) ||
        props.modelValue.includes(user.id),
    )
    .map((user) => ({ label: `${user.real_name}（${user.login_name}）`, value: user.id }))
})

function select(value: string[] | string | null): void {
  const ids = Array.isArray(value) ? value : value ? [value] : []
  const known = [...selectedCache.value, ...props.selectedMembers, ...candidates.value]
  selectedCache.value = known.filter(
    (user, index) =>
      ids.includes(user.id) && known.findIndex((item) => item.id === user.id) === index,
  )
  emit('update:modelValue', ids)
}

async function load(): Promise<void> {
  const version = ++loadVersion
  loading.value = true
  failure.value = ''
  try {
    const queryValue = { page: page.value, page_size: pageSize, q: query.value }
    const result = await (props.kind === 'teacher'
      ? props.staffTeachers
        ? identityApi.staffTeachers(queryValue)
        : identityApi.teachers(queryValue)
      : identityApi.students(queryValue))
    if (version !== loadVersion) return
    candidates.value = result.items
    total.value = result.total
  } catch (error) {
    if (version !== loadVersion) return
    candidates.value = []
    failure.value = errorMessage(error)
  } finally {
    if (version === loadVersion) loading.value = false
  }
}

function changePage(value: number): void {
  page.value = value
  void load()
}
onMounted(load)
</script>

<template>
  <div class="member-picker">
    <NSpace class="picker-search">
      <NInput
        v-model:value="query"
        :input-props="{ 'aria-label': `搜索${label}` }"
        :placeholder="`按姓名或${kind === 'teacher' ? '工号' : '学号'}搜索`"
        @keyup.enter="changePage(1)"
      />
      <NButton :loading="loading" @click="changePage(1)">查询{{ label }}</NButton>
    </NSpace>
    <NAlert v-if="failure" type="error"
      >{{ failure }} <NButton size="small" @click="load">重试加载候选</NButton></NAlert
    >
    <NSelect
      :value="kind === 'teacher' ? modelValue : (modelValue[0] ?? null)"
      :multiple="kind === 'teacher'"
      :aria-label="kind === 'teacher' ? '负责教师' : '选择学生'"
      :placeholder="`选择当前页${label}`"
      :options="options"
      :loading="loading"
      clearable
      @update:value="select"
    />
    <ListPager
      :label="`${label}候选`"
      :page="page"
      :page-size="pageSize"
      :total="total"
      :loading="loading"
      @change="changePage"
    />
  </div>
</template>

<style scoped>
.member-picker {
  width: 100%;
}
.picker-search {
  margin-bottom: 12px;
}
</style>
