import { NButton, NConfigProvider, NInput } from 'naive-ui'
import { createApp, h, ref } from 'vue'
import type { QuestionInput } from '../../src/api/questions'
import QuestionFields from '../../src/components/QuestionFields.vue'
import AppSelect from '../../src/components/ui/AppSelect.vue'
import LoadingSkeleton from '../../src/components/ui/LoadingSkeleton.vue'
import { appTheme } from '../../src/design/theme'

/** 在真实组件库中隔离检查共享控件，测试不依赖业务账号或后端数据。 */
export function mountFoundationHarness(): void {
  const original = document.querySelector<HTMLElement>('#app')
  if (original) original.style.display = 'none'
  const host = document.createElement('div')
  document.body.append(host)
  const options = [
    { label: '全部状态', value: 'all' },
    { label: '进行中', value: 'active' },
    { label: '已结束', value: 'ended' },
    { label: '不可选择', value: 'disabled', disabled: true },
  ]
  const selected = ref<string | number | null>('all')
  const multiple = ref<Array<string | number>>(['all'])
  const searchableMultiple = ref<Array<string | number>>([])
  const invalid = ref(true)
  const disabled = ref(true)

  createApp({
    render: () =>
      h(
        NConfigProvider,
        { themeOverrides: appTheme },
        {
          default: () =>
            h(
              'main',
              {
                style: 'padding:24px;display:grid;gap:24px;width:100%;max-width:900px;min-width:0;',
              },
              [
                h('div', { class: 'field' }, [h('input', { 'aria-label': '原生输入框' })]),
                h(NInput, { inputProps: { 'aria-label': '主题输入框' } }),
                h('label', { for: 'state-focus' }, '状态标签'),
                h(AppSelect, {
                  'aria-label': '状态',
                  ...(invalid.value
                    ? { 'aria-invalid': 'true', 'aria-describedby': 'state-hint' }
                    : {}),
                  inputProps: { id: 'state-focus' },
                  options,
                  value: selected.value,
                  'onUpdate:value': (value: string | number | null) => {
                    selected.value = value
                  },
                }),
                h('p', { id: 'state-hint' }, '请选择有效状态'),
                h(AppSelect, {
                  'aria-label': '搜索状态',
                  inputProps: { id: 'search-focus' },
                  filterable: true,
                  options,
                }),
                h(AppSelect, {
                  'aria-label': '多选状态',
                  multiple: true,
                  clearable: true,
                  options,
                  value: multiple.value,
                  'onUpdate:value': (value: Array<string | number>) => {
                    multiple.value = value
                  },
                }),
                h('output', { 'data-testid': 'selected-values' }, JSON.stringify(multiple.value)),
                h(AppSelect, { 'aria-label': '禁用状态', disabled: disabled.value, options }),
                h(
                  NButton,
                  {
                    onClick: () => {
                      invalid.value = false
                    },
                  },
                  { default: () => '清除校验' },
                ),
                h(
                  NButton,
                  {
                    onClick: () => {
                      disabled.value = !disabled.value
                    },
                  },
                  { default: () => '切换禁用' },
                ),
                h(NButton, { type: 'primary' }, { default: () => '主要操作' }),
                h(LoadingSkeleton, { rows: 2 }),
                h('section', { 'aria-label': '搜索多选测试' }, [
                  h(NButton, {}, { default: () => '搜索多选之前' }),
                  h('label', { class: 'field' }, [
                    h('span', {}, '搜索多选标签'),
                    h(AppSelect, {
                      'aria-label': '搜索多选状态',
                      inputProps: { id: 'search-multiple-focus' },
                      multiple: true,
                      filterable: true,
                      options,
                      value: searchableMultiple.value,
                      'onUpdate:value': (value: Array<string | number>) => {
                        searchableMultiple.value = value
                      },
                    }),
                  ]),
                  h(
                    'output',
                    { 'data-testid': 'searchable-values' },
                    JSON.stringify(searchableMultiple.value),
                  ),
                  h(NButton, {}, { default: () => '搜索多选之后' }),
                ]),
              ],
            ),
        },
      ),
  }).mount(host)
}

/** 保留完整题目编辑联动，验证组件更新不会误触发题型切换的重置逻辑。 */
export function mountQuestionEditorHarness(): void {
  const original = document.querySelector<HTMLElement>('#app')
  if (original) original.style.display = 'none'
  const host = document.createElement('div')
  document.body.append(host)
  const model = ref<QuestionInput>({
    type: 'TRUE_FALSE',
    content: '待编辑题目',
    options: [],
    standard_answer: false,
    explanation: null,
    subject: '数学',
    knowledge_tags: [],
    difficulty: 'MEDIUM',
  })
  createApp({
    render: () =>
      h(
        NConfigProvider,
        { themeOverrides: appTheme },
        {
          default: () =>
            h('main', { style: 'padding:24px;' }, [
              h(QuestionFields, {
                modelValue: model.value,
                'onUpdate:modelValue': (value: QuestionInput) => {
                  model.value = value
                },
              }),
              h('output', { 'data-testid': 'question-model' }, JSON.stringify(model.value)),
              h(
                NButton,
                {
                  onClick: () => {
                    model.value = {
                      ...model.value,
                      type: 'SHORT_ANSWER',
                      standard_answer: '保留原参考答案',
                    }
                  },
                },
                { default: () => '载入简答草稿' },
              ),
            ]),
        },
      ),
  }).mount(host)
}
