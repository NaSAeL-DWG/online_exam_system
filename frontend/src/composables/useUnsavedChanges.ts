import { onBeforeUnmount, watchEffect } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { useDialog } from 'naive-ui'
import { useAuthStore } from '../stores/auth'

/** 统一保护手动保存的表单；确认放弃只允许当前动作，不提前清空编辑内容。 */
export function useUnsavedChanges(hasChanges: () => boolean) {
  const dialog = useDialog()
  const auth = useAuthStore()
  let decision: Promise<boolean> | null = null

  function confirmDiscard(action = '离开'): Promise<boolean> {
    // 会话失效必须正常跳回登录，不能被已失去权限的表单拦截。
    if (!auth.user || !hasChanges()) return Promise.resolve(true)
    if (decision) return decision
    decision = new Promise<boolean>((resolve) => {
      dialog.warning({
        title: '放弃未保存修改？',
        content: `${action}将放弃本次尚未保存的内容。你可以继续编辑并保存。`,
        positiveText: `放弃修改并${action}`,
        negativeText: '继续编辑',
        onPositiveClick: () => resolve(true),
        onNegativeClick: () => resolve(false),
        onClose: () => resolve(false),
        onMaskClick: () => resolve(false),
        onEsc: () => resolve(false),
      })
    }).finally(() => {
      decision = null
    })
    return decision
  }

  function beforeUnload(event: BeforeUnloadEvent): void {
    event.preventDefault()
    event.returnValue = ''
  }
  // 只在需要保护时注册原生关闭／刷新提示，干净页面不阻碍正常导航。
  watchEffect(() => {
    window.removeEventListener('beforeunload', beforeUnload)
    if (auth.user && hasChanges()) window.addEventListener('beforeunload', beforeUnload)
  })
  onBeforeUnmount(() => window.removeEventListener('beforeunload', beforeUnload))
  onBeforeRouteLeave(() => confirmDiscard())

  return { confirmDiscard }
}
