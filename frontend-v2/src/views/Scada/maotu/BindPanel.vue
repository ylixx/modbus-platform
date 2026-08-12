<script setup lang="ts">
/**
 * maotu 编辑器右栏「点位绑定」面板（deviceBind 插槽）
 * 绑定信息存 item.device_bind = { signalId, attr }，maotu 序列化时保留
 */
import { ref, watch, computed, onMounted } from 'vue'
import { ElSelect, ElOption, ElInput, ElButton, ElMessage } from 'element-plus'
import { getDevices, getDeviceTags, unwrapList } from '@/api/modbus'
import { useWsStore } from '@/store/modules/websocket'
import type { MtItem } from './types'

defineOptions({ name: 'MaotuBindPanel' })

const props = defineProps<{ item: MtItem }>()

const wsStore = useWsStore()
const devices = ref<any[]>([])
const deviceId = ref<any>(null)
const tags = ref<any[]>([])
const tagName = ref('')
const attr = ref('text')

const bound = computed(() => props.item?.device_bind)
const boundSignal = computed(() => bound.value?.signalId || '')
const liveText = computed(() => {
  const sid = bound.value?.signalId
  if (!sid) return ''
  const v = wsStore.liveData[sid]
  return v ? `${sid} = ${v.value}` : `${sid}（无实时值）`
})

const fetchDevices = async () => {
  try {
    const res: any = await getDevices({ page_size: 100, enabled: true })
    devices.value = unwrapList(res).list
  } catch {
    devices.value = []
  }
}

const loadTags = async () => {
  tags.value = []
  if (!deviceId.value) return
  try {
    const res: any = await getDeviceTags(deviceId.value, { page_size: 500 })
    tags.value = unwrapList(res).list
  } catch {
    tags.value = []
  }
}

watch(deviceId, loadTags)

const save = () => {
  if (!props.item) return
  if (!deviceId.value || !tagName.value) {
    ElMessage.warning('请选择设备和点位')
    return
  }
  const signalId = `${deviceId.value}:${tagName.value}`
  props.item.device_bind = { signalId, attr: attr.value || 'text' }
  ElMessage.success(`已绑定 ${signalId} → ${attr.value}`)
}

const clear = () => {
  if (!props.item) return
  delete props.item.device_bind
  ElMessage.info('已解除绑定')
}

onMounted(fetchDevices)

watch(
  () => props.item,
  () => {
    if (!props.item) return
    const b = props.item.device_bind
    if (b?.signalId) {
      const [d, t] = b.signalId.split(':')
      deviceId.value = Number(d) || null
      tagName.value = t || ''
      attr.value = b.attr || 'text'
    }
  },
  { immediate: true, deep: false }
)
</script>

<template>
  <div class="mt-bind-panel">
    <div class="mt-bind-title">
      <span>点位绑定</span>
      <span v-if="boundSignal" class="mt-bind-badge">已绑定</span>
    </div>

    <div v-if="item?.id" class="mt-bind-form">
      <div class="mt-bind-row">
        <span class="mt-bind-label">设备</span>
        <ElSelect v-model="deviceId" size="small" placeholder="选择设备" filterable clearable>
          <ElOption v-for="d in devices" :key="d.id" :label="`${d.name} (${d.id})`" :value="d.id" />
        </ElSelect>
      </div>
      <div class="mt-bind-row">
        <span class="mt-bind-label">点位</span>
        <ElSelect v-model="tagName" size="small" placeholder="选择点位" filterable clearable>
          <ElOption v-for="t in tags" :key="t.id" :label="t.name" :value="t.name" />
        </ElSelect>
      </div>
      <div class="mt-bind-row">
        <span class="mt-bind-label">属性</span>
        <ElInput v-model="attr" size="small" placeholder="如 text / fill / visibility" />
      </div>
      <div v-if="liveText" class="mt-bind-live">{{ liveText }}</div>
      <div class="mt-bind-actions">
        <ElButton type="primary" size="small" @click="save">保存绑定</ElButton>
        <ElButton v-if="boundSignal" size="small" @click="clear">解除</ElButton>
      </div>
    </div>
    <div v-else class="mt-bind-empty">在画布中选中图元后进行绑定</div>
  </div>
</template>

<style scoped>
.mt-bind-panel {
  padding: 8px;
  font-size: 12px;
  color: var(--el-text-color-primary, #e0e6f0);
}
.mt-bind-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-weight: 600;
  margin-bottom: 8px;
}
.mt-bind-badge {
  color: #67c23a;
}
.mt-bind-form :deep(.el-select) {
  width: 100%;
}
.mt-bind-row {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
}
.mt-bind-label {
  width: 34px;
  flex-shrink: 0;
  opacity: 0.8;
}
.mt-bind-live {
  margin: 4px 0;
  color: #e6a23c;
}
.mt-bind-actions {
  display: flex;
  gap: 8px;
  margin-top: 4px;
}
.mt-bind-empty {
  opacity: 0.5;
  padding: 6px 0;
}
</style>