import { computed, onMounted, reactive, ref } from 'vue'
import { useDialog, useMessage } from 'naive-ui'
import { errorMessage } from '../../api/client'
import { teachingClassesApi } from '../../api/teachingClasses'
import { useAuthStore } from '../../stores/auth'
import type { TeachingClass, UserSummary } from '../../types'
import { useFormValidation } from '../../composables/useFormValidation'
import { textRule } from '../identity/formRules'

export function useTeachingClassDirectory() {
  const auth = useAuthStore()
  const message = useMessage()
  const dialog = useDialog()
  const items = ref<TeachingClass[]>([])
  const selectedTeachers = ref<UserSummary[]>([])
  const selected = ref<TeachingClass | null>(null)
  const selectedStudentIds = ref<string[]>([])
  const loading = ref(false)
  const saving = ref(false)
  const failure = ref('')
  const page = ref(1)
  const pageSize = 20
  const total = ref(0)
  const query = ref('')
  let loadVersion = 0
  const editorVisible = ref(false)
  const detailVisible = ref(false)
  const editingId = ref<string | null>(null)
  const form = reactive<{ name: string; description: string; teacher_ids: string[] }>({
    name: '',
    description: '',
    teacher_ids: [],
  })
  const isAdmin = computed(() => auth.user?.user_type === 'ADMIN')
  const editorFailure = ref('')
  const validation = useFormValidation(
    () => form,
    { name: textRule('教学班名称', 1, 200) },
    'class',
  )
  const editingClass = computed(() => items.value.find((item) => item.id === editingId.value))

  async function load(): Promise<void> {
    const version = ++loadVersion
    loading.value = true
    failure.value = ''
    try {
      const result = await teachingClassesApi.list({
        page: page.value,
        page_size: pageSize,
        q: query.value,
      })
      if (version !== loadVersion) return
      items.value = result.items
      total.value = result.total
    } catch (error) {
      if (version !== loadVersion) return
      items.value = []
      failure.value = errorMessage(error)
    } finally {
      if (version === loadVersion) loading.value = false
    }
  }
  function changePage(value: number): void {
    page.value = value
    void load()
  }
  function openCreate(): void {
    validation.clear()
    editorFailure.value = ''
    editingId.value = null
    selectedTeachers.value = []
    Object.assign(form, { name: '', description: '', teacher_ids: [] })
    editorVisible.value = true
  }
  function openEdit(row: TeachingClass): void {
    validation.clear()
    editorFailure.value = ''
    editingId.value = row.id
    // 已关联教师独立于当前候选页保留，搜索或翻页不会丢失选择。
    selectedTeachers.value = row.teachers
    Object.assign(form, {
      name: row.name,
      description: row.description ?? '',
      teacher_ids: row.teachers.map((teacher) => teacher.id),
    })
    editorVisible.value = true
  }
  async function saveClass(): Promise<void> {
    if (saving.value) return
    editorFailure.value = ''
    if (!validation.validate()) {
      editorFailure.value = '请检查标出的填写内容'
      return
    }
    saving.value = true
    try {
      if (editingId.value) await teachingClassesApi.update(editingId.value, form)
      else await teachingClassesApi.create(form)
      editorVisible.value = false
      message.success(editingId.value ? '教学班已更新' : '教学班已创建')
      await load()
    } catch (error) {
      validation.applyServerError(error)
      editorFailure.value = errorMessage(error)
    } finally {
      saving.value = false
    }
  }
  async function openDetail(row: TeachingClass): Promise<void> {
    try {
      selected.value = (await teachingClassesApi.detail(row.id)).class_info
      selectedStudentIds.value = []
      detailVisible.value = true
    } catch (error) {
      message.error(errorMessage(error))
    }
  }
  async function addStudent(): Promise<void> {
    if (!selected.value || !selectedStudentIds.value[0] || saving.value) return
    saving.value = true
    try {
      selected.value = (
        await teachingClassesApi.addStudent(selected.value.id, selectedStudentIds.value[0])
      ).class_info
      selectedStudentIds.value = []
      message.success('学生已加入教学班')
      await load()
    } catch (error) {
      message.error(errorMessage(error))
    } finally {
      saving.value = false
    }
  }
  function removeStudent(student: UserSummary): void {
    if (!selected.value) return
    const classInfo = selected.value
    dialog.warning({
      title: '移出学生',
      content: `确认将 ${student.real_name} 移出“${classInfo.name}”？已有考试名单不会随之变化。`,
      positiveText: '确认移出',
      negativeText: '取消',
      onPositiveClick: async () => {
        try {
          await teachingClassesApi.removeStudent(classInfo.id, student.id)
          await openDetail(classInfo)
          await load()
          message.success('学生已移出')
        } catch (error) {
          message.error(errorMessage(error))
        }
      },
    })
  }
  function archiveEditingClass(): void {
    if (!editingClass.value) return
    const classInfo = editingClass.value
    editorVisible.value = false
    dialog.warning({
      title: '归档教学班',
      content: '归档后将不能继续维护成员，历史关系仍会保留。',
      positiveText: '确认归档',
      negativeText: '取消',
      onPositiveClick: async () => {
        try {
          await teachingClassesApi.update(classInfo.id, { status: 'ARCHIVED' })
          message.success('教学班已归档')
          await load()
        } catch (error) {
          message.error(errorMessage(error))
        }
      },
    })
  }
  onMounted(load)
  return {
    items,
    selectedTeachers,
    selected,
    selectedStudentIds,
    loading,
    saving,
    failure,
    page,
    pageSize,
    total,
    query,
    editorVisible,
    detailVisible,
    editingId,
    editingClass,
    form,
    validation,
    editorFailure,
    isAdmin,
    load,
    changePage,
    openCreate,
    openEdit,
    saveClass,
    openDetail,
    addStudent,
    removeStudent,
    archiveEditingClass,
  }
}
