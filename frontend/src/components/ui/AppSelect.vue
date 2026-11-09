<script setup lang="ts">
import { NSelect, type SelectProps } from 'naive-ui'
import { nextTick, onBeforeUnmount, onMounted, onUpdated, ref, useAttrs, useId } from 'vue'

defineOptions({ inheritAttrs: false })

// 复用库的完整属性定义，保持 v-model、校验、筛选和多选的类型与行为。
const props = defineProps(NSelect.props)
const attrs = useAttrs()
const selectRef = ref<InstanceType<typeof NSelect> | null>(null)
const listboxId = `select-${useId()}-listbox`
const open = ref(false)
let rootObserver: MutationObserver | undefined
let menuObserver: MutationObserver | undefined
let observedMenu: HTMLElement | null = null
let managedTrigger: HTMLElement | null = null
const managedAria = new Set<string>()
const keyboardClearButtons = new WeakSet<HTMLElement>()

function setAttribute(element: HTMLElement, name: string, value: unknown) {
  if (value === undefined || value === null || value === false) {
    element.removeAttribute(name)
    return
  }
  const nextValue = String(value)
  if (element.getAttribute(name) !== nextValue) element.setAttribute(name, nextValue)
}

function nodeProps(option: Parameters<NonNullable<SelectProps['nodeProps']>>[0]) {
  const original = props.nodeProps?.(option) ?? {}
  if (option.type === 'group' || option.type === 'ignored') return original
  const value = option[props.valueField]
  return {
    ...original,
    id: original.id ?? `${listboxId}-${typeof value}-${encodeURIComponent(String(value))}`,
    role: 'option',
    'aria-disabled': option.disabled ? 'true' : 'false',
  }
}

function forwardedProps() {
  // 标签和校验属性交给真实焦点元素，避免根 div 与输入框被读成两个控件。
  const rootAttrs = Object.fromEntries(
    Object.entries(attrs).filter(
      ([name]) => !name.startsWith('aria-') && !['id', 'role', 'tabindex'].includes(name),
    ),
  )
  return {
    ...props,
    ...rootAttrs,
    nodeProps,
    menuProps: { ...props.menuProps, id: listboxId, role: 'listbox' },
    'onUpdate:show': handleUpdateShow,
    onUpdateShow: undefined,
  }
}

function handleUpdateShow(value: boolean) {
  open.value = value
  const handlers = [props['onUpdate:show'], props.onUpdateShow].flat()
  handlers.forEach((handler) => handler?.(value))
  void nextTick(syncAccessibility)
}

function focusSelection() {
  const root = selectRef.value?.$el as HTMLElement | undefined
  if (root?.querySelector('.n-base-selection--disabled')) return
  selectRef.value?.focus()
  syncAccessibility()
}

function handleLabelClick(event: MouseEvent) {
  const root = selectRef.value?.$el as HTMLElement | undefined
  if (!root || !(event.target instanceof Element) || root.contains(event.target)) return
  const label = event.target.closest('label')
  if (!label || label.control || props.disabled) return
  const id = attrs.id ?? props.inputProps?.id
  // 非搜索触发器是 div，原生 label 不会自动聚焦，补齐显式和包裹标签的激活行为。
  if (label.contains(root) || (id && label.htmlFor === id)) focusSelection()
}

function syncAccessibility() {
  const root = selectRef.value?.$el as HTMLElement | undefined
  if (!root) return
  const selection = root.querySelector<HTMLElement>('.n-base-selection')
  if (!selection) return
  const input = selection.querySelector<HTMLInputElement>('input')
  const wrapper = selection.querySelector<HTMLElement>(
    '.n-base-selection-label, .n-base-selection-tags',
  )
  const disabled = selection.classList.contains('n-base-selection--disabled')
  // 可搜索多选的输入框收起时 display:none，先保留可见包裹层供 Tab 进入。
  if (input && wrapper === document.activeElement && !disabled) {
    selectRef.value?.focusInput()
  }
  const inputTag = input?.closest<HTMLElement>('.n-base-selection-input-tag')
  const inputVisible = input && (!inputTag || getComputedStyle(inputTag).display !== 'none')
  const trigger = inputVisible ? input : wrapper
  if (!trigger) return

  if (managedTrigger && managedTrigger !== trigger) {
    // 焦点在包裹层与搜索输入间切换时，只有当前节点保留控件语义和唯一 ID。
    const triggerAttributes = [
      'id',
      'role',
      'aria-haspopup',
      'aria-controls',
      'aria-expanded',
      'aria-disabled',
      'aria-autocomplete',
      'aria-activedescendant',
      ...managedAria,
    ]
    triggerAttributes.forEach((name) => managedTrigger?.removeAttribute(name))
  }
  managedTrigger = trigger
  if (input && input !== trigger) input.removeAttribute('id')

  // Naive UI 暂未公开非搜索模式的触发器属性，只在此处补齐原焦点的语义。
  // 搜索模式直接以原输入框作为唯一 tab 停靠点，库仍处理方向键和选项选择。
  if (input) {
    selection.querySelectorAll<HTMLElement>('[tabindex]').forEach((element) => {
      if (element !== trigger && !element.matches('[data-clear]')) {
        setAttribute(element, 'tabindex', '-1')
      }
    })
  }
  setAttribute(trigger, 'tabindex', disabled ? '-1' : '0')
  setAttribute(trigger, 'role', 'combobox')
  setAttribute(trigger, 'id', attrs.id ?? props.inputProps?.id)
  setAttribute(trigger, 'aria-haspopup', 'listbox')
  setAttribute(trigger, 'aria-controls', listboxId)
  setAttribute(trigger, 'aria-expanded', String(props.show ?? open.value))
  setAttribute(trigger, 'aria-disabled', String(disabled))
  setAttribute(trigger, 'aria-autocomplete', props.filterable ? 'list' : 'none')
  const inputAttrs = props.inputProps ?? {}
  const accessibleAttrs = { ...inputAttrs, ...attrs }
  managedAria.forEach((name) => {
    if (!(name in accessibleAttrs)) {
      trigger.removeAttribute(name)
      managedAria.delete(name)
    }
  })
  Object.entries(accessibleAttrs).forEach(([name, value]) => {
    if (
      name.startsWith('aria-') &&
      !['aria-expanded', 'aria-controls', 'aria-disabled'].includes(name)
    ) {
      setAttribute(trigger, name, value)
      managedAria.add(name)
    }
  })

  // 默认箭头容器继承了库的 loading 图片标签，清除按钮不应藏在图片角色内。
  const suffix = selection.querySelector<HTMLElement>('.n-base-suffix')
  if (suffix) {
    setAttribute(suffix, 'role', props.loading ? 'status' : undefined)
    setAttribute(suffix, 'aria-label', props.loading ? '正在加载选项' : undefined)
  }

  // 库的清除图标只有鼠标事件，给原节点补充键盘操作并在清除后回到控件。
  const clear = selection.querySelector<HTMLElement>('[data-clear]')
  if (clear) {
    const canClear = !disabled && selection.classList.contains('n-base-selection--selected')
    setAttribute(clear, 'role', 'button')
    setAttribute(clear, 'aria-label', `清除${accessibleAttrs['aria-label'] ?? '选择'}`)
    // 清空后的图标会保留短暂退场动画，此时须立即退出键盘与无障碍树。
    setAttribute(clear, 'aria-hidden', String(!canClear))
    setAttribute(clear, 'tabindex', canClear ? '0' : '-1')
    if (!keyboardClearButtons.has(clear)) {
      keyboardClearButtons.add(clear)
      clear.addEventListener('keydown', (event) => {
        if (event.key !== 'Enter' && event.key !== ' ') return
        event.preventDefault()
        event.stopPropagation()
        clear.click()
        void nextTick(focusSelection)
      })
    }
  }

  const menu = document.getElementById(listboxId)
  if (menu !== observedMenu) {
    menuObserver?.disconnect()
    observedMenu = menu
    if (menu) {
      menuObserver = new MutationObserver(syncAccessibility)
      menuObserver.observe(menu, {
        subtree: true,
        childList: true,
        attributes: true,
        attributeFilter: ['class'],
      })
    }
  }
  if (!menu) return
  setAttribute(menu, 'tabindex', '-1')
  setAttribute(menu, 'aria-hidden', String(!(props.show ?? open.value)))
  setAttribute(menu, 'aria-multiselectable', props.multiple ? 'true' : undefined)
  setAttribute(menu, 'aria-label', accessibleAttrs['aria-label'])
  setAttribute(menu, 'aria-labelledby', accessibleAttrs['aria-labelledby'])
  menu.querySelectorAll<HTMLElement>('[role="option"]').forEach((option) => {
    setAttribute(
      option,
      'aria-selected',
      String(option.classList.contains('n-base-select-option--selected')),
    )
  })
  const pending = menu.querySelector<HTMLElement>('.n-base-select-option--pending')
  setAttribute(
    trigger,
    'aria-activedescendant',
    (props.show ?? open.value) ? pending?.id : undefined,
  )
}

onMounted(() => {
  syncAccessibility()
  document.addEventListener('click', handleLabelClick)
  const root = selectRef.value?.$el as HTMLElement | undefined
  if (root) {
    rootObserver = new MutationObserver(syncAccessibility)
    rootObserver.observe(root, {
      subtree: true,
      childList: true,
      attributes: true,
      attributeFilter: ['class', 'tabindex'],
    })
  }
})
onUpdated(syncAccessibility)
onBeforeUnmount(() => {
  rootObserver?.disconnect()
  menuObserver?.disconnect()
  document.removeEventListener('click', handleLabelClick)
})

defineExpose({
  focus: focusSelection,
  blur: () => selectRef.value?.blur(),
})
</script>

<template>
  <NSelect ref="selectRef" v-bind="forwardedProps()">
    <template v-for="(_, name) in $slots" #[name]="slotProps">
      <slot :name="name" v-bind="slotProps ?? {}" />
    </template>
  </NSelect>
</template>
