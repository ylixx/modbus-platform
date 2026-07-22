<template>
  <template v-for="item in options" :key="item.value">
    <el-tag
      v-if="String(item.value) === String(modelValue)"
      :type="item.type || 'info'"
      :size="size"
      :effect="effect"
    >
      {{ item.label }}
    </el-tag>
  </template>
  <span v-if="!matched && showFallback">{{ modelValue }}</span>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  modelValue: { type: [String, Number, Boolean], default: '' },
  options: { type: Array, default: () => [] },  // [{ value, label, type }]
  size: { type: String, default: 'small' },
  effect: { type: String, default: 'light' },
  showFallback: { type: Boolean, default: true },
})

const matched = computed(() =>
  props.options.some(item => String(item.value) === String(props.modelValue))
)
</script>
