<template>
  <div class="property-panel">
    <div class="panel-title">属性面板</div>
    <div v-if="selectedObject" class="prop-content">
      <!-- Basic props -->
      <el-divider content-position="left">基本</el-divider>
      <el-form label-width="60px" size="small">
        <el-form-item label="X"><el-input-number :model-value="Math.round(selectedObject.left || 0)" @change="$emit('updateProp', 'left', $event)" controls-position="right" style="width:100%" /></el-form-item>
        <el-form-item label="Y"><el-input-number :model-value="Math.round(selectedObject.top || 0)" @change="$emit('updateProp', 'top', $event)" controls-position="right" style="width:100%" /></el-form-item>
        <el-form-item label="角度"><el-input-number :model-value="Math.round(selectedObject.angle || 0)" @change="$emit('updateProp', 'angle', $event)" :min="0" :max="360" controls-position="right" style="width:100%" /></el-form-item>
        <el-form-item label="不透明"><el-slider :model-value="selectedObject.opacity ?? 1" @change="$emit('updateProp', 'opacity', $event)" :min="0" :max="1" :step="0.05" /></el-form-item>
      </el-form>

      <!-- Text props -->
      <template v-if="selectedObject.type === 'textbox' || selectedObject.type === 'text'">
        <el-divider content-position="left">文本</el-divider>
        <el-form label-width="60px" size="small">
          <el-form-item label="内容"><el-input :model-value="selectedObject.text" @change="$emit('updateText', $event)" /></el-form-item>
          <el-form-item label="字号"><el-input-number :model-value="selectedObject.fontSize || 14" @change="$emit('updateProp', 'fontSize', $event)" :min="8" :max="120" /></el-form-item>
        </el-form>
      </template>

      <!-- Fill color -->
      <template v-if="hasPart('body') || hasPart('light')">
        <el-divider content-position="left">颜色</el-divider>
        <el-form label-width="60px" size="small">
          <el-form-item label="填充"><el-color-picker :model-value="partFill" @change="$emit('updatePartFill', $event)" /></el-form-item>
        </el-form>
      </template>

      <!-- Data Binding -->
      <el-divider content-position="left">数据绑定</el-divider>
      <el-form label-width="60px" size="small">
        <el-form-item label="设备">
          <el-select :model-value="binding.deviceId" placeholder="选择设备" clearable @change="$emit('bindingChange', 'deviceId', $event)" style="width:100%">
            <el-option v-for="d in devices" :key="d.id" :label="d.name" :value="d.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="点位" v-if="binding.deviceId">
          <el-select :model-value="binding.tagId" placeholder="选择点位" clearable @change="$emit('bindingChange', 'tagId', $event)" style="width:100%">
            <el-option v-for="t in tags" :key="t.id" :label="`${t.name} (${t.unit||'-'})`" :value="t.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="映射" v-if="binding.tagId && bindableFields.length">
          <el-select :model-value="binding.field" @change="$emit('bindingChange', 'field', $event)" style="width:100%">
            <el-option v-for="f in bindableFields" :key="f" :label="fieldLabel(f)" :value="f" />
          </el-select>
        </el-form-item>
      </el-form>
    </div>
    <div v-else style="padding:20px;color:#666;text-align:center">
      点击画布上的组件查看属性
    </div>
  </div>
</template>

<script setup>
const props = defineProps({
  selectedObject: { type: Object, default: null },
  devices: { type: Array, default: () => [] },
  tags: { type: Array, default: () => [] },
  binding: { type: Object, default: () => ({ deviceId: null, tagId: null, field: 'text' }) },
  bindableFields: { type: Array, default: () => [] },
  partFill: { type: String, default: '#2a4a6b' },
})
defineEmits(['updateProp', 'updateText', 'updatePartFill', 'bindingChange'])

const fieldLabel = (f) => ({ text: '文本', value: '数值', state: '状态', fill: '颜色', liquidLevel: '液位', speed: '转速', flow: '流量', action: '动作' }[f] || f)

function hasPart(partName) {
  if (!props.selectedObject?._objects) return false
  return props.selectedObject._objects.some(o => o.scadaPart === partName)
}
</script>

<style scoped>
.property-panel {
  width: 260px; background: #161b22; border-left: 1px solid #30363d;
  overflow-y: auto;
}
.panel-title { font-size: 13px; color: #8b949e; padding: 8px 12px; font-weight: 600; border-bottom: 1px solid #21262d; }
.prop-content { padding: 8px; }
</style>
