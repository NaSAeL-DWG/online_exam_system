<script setup lang="ts">
import { NFormItem } from 'naive-ui'
import type { FormValidation } from '../../composables/useFormValidation'

defineProps<{ validation: FormValidation; field: string; label: string }>()
</script>

<template>
  <NFormItem
    :label="label"
    :validation-status="validation.errors[field] ? 'error' : undefined"
    :feedback="validation.errors[field] || undefined"
  >
    <slot :input-props="validation.inputProps(field, label)" />
    <template v-if="validation.errors[field]" #feedback>
      <span :id="validation.errorId(field)" role="alert">{{ validation.errors[field] }}</span>
    </template>
  </NFormItem>
</template>
