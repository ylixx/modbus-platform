<template>
  <div class="widget-palette">
    <div class="palette-title" style="display:flex;justify-content:space-between;align-items:center">
      <span>组件库</span>
      <el-button text size="small" @click="$emit('manageWidgets')" style="color:#58a6ff">管理图元</el-button>
    </div>
    <el-collapse v-model="openCategories">
      <el-collapse-item v-for="cat in categories" :key="cat.key" :name="cat.key">
        <template #title><span>{{ cat.icon }} {{ cat.label }}</span></template>
        <div class="widget-grid">
          <div v-for="w in getWidgetsByCategory(cat.key)" :key="w.name"
               class="widget-item" draggable="true"
               @dragstart="$emit('dragStart', $event, w)">
            <div class="widget-icon">{{ w.icon }}</div>
            <div class="widget-label">{{ w.name }}</div>
          </div>
        </div>
      </el-collapse-item>
    </el-collapse>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { WIDGETS, WIDGET_CATEGORIES } from './widgets.js'

defineProps({
  customWidgets: { type: Array, default: () => [] },
})
defineEmits(['dragStart', 'manageWidgets'])

const openCategories = ref(['basic', 'tank', 'valve', 'motor'])
const categories = [...WIDGET_CATEGORIES, { key: 'custom', label: '自定义', icon: '⭐' }]

function getWidgetsByCategory(cat) {
  if (cat === 'custom') {
    return (defineProps().customWidgets || []).map(w => ({
      name: w.name, category: 'custom',
      icon: w.source_type === 'svg' ? '🖼️' : '📷',
      create: () => createCustomWidgetDef(w),
      bindable: w.bindable || ['text', 'value', 'state'],
      customId: w.id,
    }))
  }
  return WIDGETS.filter(w => w.category === cat)
}

function createCustomWidgetDef(w) {
  if (w.source_type === 'svg') {
    const match = w.source_data.match(/d=["']([^"']+)["']/)
    return {
      type: 'group', scadaType: 'custom_svg', customId: w.id,
      objects: [{ type: 'path', path: match ? match[1] : 'M 0 0 L 50 50', fill: '#5b8abf', stroke: '#5b8abf', strokeWidth: 1 }],
      bindable: w.bindable || ['text', 'value', 'state'],
    }
  }
  return {
    type: 'image', scadaType: 'custom_image', customId: w.id,
    src: w.source_data, width: w.default_width, height: w.default_height,
    bindable: w.bindable || ['text', 'value', 'state'],
  }
}
</script>

<style scoped>
.widget-palette {
  width: 200px; background: #161b22; border-right: 1px solid #30363d;
  overflow-y: auto; padding: 8px;
}
.palette-title { font-size: 13px; color: #8b949e; padding: 8px; font-weight: 600; }
.widget-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 4px; }
.widget-item {
  display: flex; flex-direction: column; align-items: center; padding: 8px 4px;
  border-radius: 6px; cursor: grab; background: #0d1117; border: 1px solid #21262d;
  transition: all 0.15s;
}
.widget-item:hover { border-color: #58a6ff; background: #1c2333; }
.widget-icon { font-size: 20px; }
.widget-label { font-size: 11px; color: #8b949e; margin-top: 2px; }
</style>
