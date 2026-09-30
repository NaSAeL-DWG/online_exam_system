import { computed, onMounted, reactive, ref } from 'vue'
import { useDialog, useMessage } from 'naive-ui'
import { errorMessage } from '../../api/client'
import { identityApi } from '../../api/identity'
import type { User, UserRole, UserStatus } from '../../types'

export function useAccountDirectory() {
  const users = ref<User[]>([])
  const loading = ref(false)
  const saving = ref(false)
  const failure = ref('')
  const page = ref(1)
  const pageSize = 20
  const total = ref(0)
  const query = ref('')
  const role = ref<UserRole | 'all'>('all')
  let loadVersion = 0
  const createVisible = ref(false)
  const editVisible = ref(false)
  const resetVisible = ref(false)
  const selected = ref<User | null>(null)
  const teacher = reactive({
    teacher_no: '',
    real_name: '',
    email: '',
    phone_number: '',
    temporary_password: '',
  })
  const edit = reactive<{ login_name: string; real_name: string; status: UserStatus }>({
    login_name: '',
    real_name: '',
    status: 'ACTIVATED',
  })
  const temporaryPassword = ref('')
  const message = useMessage()
  const dialog = useDialog()
  const statusOptions = computed(() =>
    selected.value?.status === 'WAITING_ACTIVATE'
      ? [
          { label: '待审核', value: 'WAITING_ACTIVATE', disabled: true },
          { label: '已停用', value: 'DEACTIVATED' },
        ]
      : [
          { label: '已激活', value: 'ACTIVATED' },
          { label: '已停用', value: 'DEACTIVATED' },
        ],
  )

  async function load(): Promise<void> {
    const version = ++loadVersion
    loading.value = true
    failure.value = ''
    try {
      const result = await identityApi.accounts(
        { page: page.value, page_size: pageSize, q: query.value },
        role.value === 'all' ? undefined : role.value,
      )
      // 搜索与翻页仅采用最新请求，防止较慢的旧结果覆盖当前目录。
      if (version !== loadVersion) return
      users.value = result.items
      total.value = result.total
    } catch (error) {
      if (version !== loadVersion) return
      users.value = []
      failure.value = errorMessage(error)
    } finally {
      if (version === loadVersion) loading.value = false
    }
  }
  function changePage(value: number): void {
    page.value = value
    void load()
  }
  function search(): void {
    changePage(1)
  }
  function changeRole(value: UserRole | 'all'): void {
    role.value = value
    search()
  }

  async function createTeacher(): Promise<void> {
    if (saving.value) return
    saving.value = true
    try {
      await identityApi.createTeacher(teacher)
      createVisible.value = false
      Object.assign(teacher, {
        teacher_no: '',
        real_name: '',
        email: '',
        phone_number: '',
        temporary_password: '',
      })
      message.success('教师账号已创建')
      await load()
    } catch (error) {
      message.error(errorMessage(error))
    } finally {
      saving.value = false
    }
  }
  function openEdit(row: User): void {
    selected.value = row
    Object.assign(edit, {
      login_name: row.login_name,
      real_name: row.real_name,
      status: row.status,
    })
    editVisible.value = true
  }
  async function saveEdit(): Promise<void> {
    if (!selected.value || saving.value) return
    saving.value = true
    try {
      const payload: {
        login_name: string
        real_name: string
        status?: 'ACTIVATED' | 'DEACTIVATED'
      } = { login_name: edit.login_name, real_name: edit.real_name }
      // 待审核由审核流程产生，不能以资料更正跳过身份审核。
      if (edit.status !== selected.value.status && edit.status !== 'WAITING_ACTIVATE')
        payload.status = edit.status
      const result = await identityApi.updateAccount(selected.value.id, payload)
      editVisible.value = false
      message.success(
        result.cleanupPending ? '账号资料已更新，旧登录状态正在清理' : '账号资料已更新',
      )
      await load()
    } catch (error) {
      message.error(errorMessage(error))
    } finally {
      saving.value = false
    }
  }
  function openReset(row: User): void {
    selected.value = row
    temporaryPassword.value = ''
    resetVisible.value = true
  }
  async function resetPassword(): Promise<void> {
    if (!selected.value || saving.value) return
    saving.value = true
    try {
      const result = await identityApi.resetPassword(selected.value.id, temporaryPassword.value)
      resetVisible.value = false
      message.success(
        result.cleanupPending ? '密码已重置，旧登录状态正在清理' : '已重置密码并撤销旧会话',
      )
    } catch (error) {
      message.error(errorMessage(error))
    } finally {
      saving.value = false
    }
  }
  function confirmStatus(): void {
    if (!selected.value) return
    const unchanged = edit.status === selected.value.status
    dialog.warning({
      title: unchanged
        ? '确认更正资料'
        : edit.status === 'DEACTIVATED'
          ? '确认停用账号'
          : '确认恢复账号',
      content: unchanged
        ? '保存账号和姓名更正。'
        : edit.status === 'DEACTIVATED'
          ? '停用会立即撤销该账号的所有登录会话。'
          : '学生账号会依据最近审核结果恢复状态。',
      positiveText: '确认保存',
      negativeText: '取消',
      onPositiveClick: saveEdit,
    })
  }
  onMounted(load)
  return {
    users,
    loading,
    saving,
    failure,
    page,
    pageSize,
    total,
    query,
    role,
    createVisible,
    editVisible,
    resetVisible,
    selected,
    teacher,
    edit,
    temporaryPassword,
    statusOptions,
    load,
    changePage,
    search,
    changeRole,
    createTeacher,
    openEdit,
    openReset,
    resetPassword,
    confirmStatus,
  }
}
