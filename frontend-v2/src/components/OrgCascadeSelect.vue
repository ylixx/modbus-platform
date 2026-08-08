<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { ElButton, ElTag, ElSelect, ElOption } from 'element-plus'
import { getOrgTreeApi, OrgLevel, OrgNode, OrgDevice, OrgPath } from '@/api/hierarchy'
import { getDevices, unwrapList } from '@/api/modbus'

// 单选模式（single=true）：
//   v-model 为单个设备 ID (number | null)；设备框单选，选中即 emit 'change'(id, obj)
// 多选模式（默认）：
//   v-model 为设备 ID 列表 (number[])；配合 showDeviceActions / search 使用
// 两种模式都保留「组织架构级联 + 远程搜索」，与设备管理页一致。
// emit 'search': 用户点击「搜索」按钮，宿主页面据此刷新设备列表
const props = withDefaults(
  defineProps<{
    modelValue?: number | number[] | null
    path?: OrgPath | null
    // 单选模式：v-model 为单个设备 ID；选中即 emit change(id, obj)
    single?: boolean
    // 是否显示「设备名称」选择框（含级联范围内的远程搜索）；
    // 为 false 时（如设备管理页）不加载设备下拉，仅作组织层级筛选
    showDeviceSelect?: boolean
    // footer 是否显示「已选 N 台 / 全选当前 / 清空已选」操作；
    // 设备管理页在自身工具栏放置了这些按钮，故传 false 关闭，避免重复
    showDeviceActions?: boolean
    // 设备下拉/搜索是否只返回「含可写点位」的设备（批量控制等写值场景用）
    writableOnly?: boolean
    // 设备下拉选项是否仅含已启用设备
    enabledOnly?: boolean
    // 是否显示「搜索 / 重置」按钮（表格类宿主需要；表单单选场景可关闭）
    showActions?: boolean
  }>(),
  {
    modelValue: null,
    path: null,
    single: false,
    showDeviceSelect: true,
    showDeviceActions: true,
    writableOnly: false,
    enabledOnly: false,
    showActions: true
  }
)
const emit = defineEmits<{
  'update:modelValue': [number | number[] | null]
  'update:path': [OrgPath | null]
  search: []
  change: [number | null, any | null]
}>()

// 模块级共享缓存：多个实例（如批量控制表格每行）共用同一份组织树，避免重复请求
let sharedTreePromise: Promise<{ levels: OrgLevel[]; tree: OrgNode[] }> | null = null
function loadOrgTree() {
  if (!sharedTreePromise) {
    sharedTreePromise = getOrgTreeApi({ with_devices: false }).then((res) => ({
      levels: res.data.levels,
      tree: res.data.tree
    }))
  }
  return sharedTreePromise
}

const loading = ref(false)
const levels = ref<OrgLevel[]>([])
const tree = ref<OrgNode[]>([])
// 分组层级（厂/区/班/站/位置）的当前选中节点
const selections = ref<(OrgNode | null)[]>([])
// 设备下拉选项：仅在级联改变时按范围从 /devices 查询，默认不加载全部设备
const deviceOptions = ref<OrgDevice[]>([])
const loadingDevices = ref(false)

// OrgPath 类型已在 @/api/hierarchy.ts 中统一导出

const groupLevels = computed<OrgLevel[]>(() => levels.value.slice(0, -1))
// 单选时 modelValue 为单个 id，多选为数组；内部统一按数组处理
const selectedIds = computed<number[]>({
  get: () => (props.single ? (props.modelValue == null ? [] : [props.modelValue as number]) : (props.modelValue as number[]) || []),
  set: (v) => {
    if (props.single) {
      emit('update:modelValue', v.length ? v[v.length - 1] : null)
    } else {
      emit('update:modelValue', v)
    }
  }
})
// 是否已选择至少一个层级（决定设备框是否可用）
const hasCascade = computed(() => selections.value.some((s) => s != null))

function levelOptions(index: number): OrgNode[] {
  if (index === 0) return tree.value
  const parent = selections.value[index - 1]
  if (!parent || !parent.children) return []
  return parent.children
}

// 选中节点：返回最深节点的 org_node_id（子树筛选）+ 各级标签（展示）
function buildPath(): OrgPath | null {
  const selected = selections.value.filter((s): s is OrgNode => s != null)
  if (!selected.length) return null
  const labels = selected.map((s) => s.label)
  const deepest = selected[selected.length - 1]
  return { org_node_id: deepest.id ?? null, labels }
}

// 分组下拉框 change：更新层级路径 + 按范围加载设备下拉项（不触发列表刷新）
function onGroupChange(index: number, val: string | null) {
  const node = val ? (levelOptions(index).find((n) => n.label === val) ?? null) : null
  selections.value[index] = node
  for (let i = index + 1; i < selections.value.length; i++) selections.value[i] = null
  selections.value = [...selections.value]
  emit('update:path', buildPath())
  // 层级变化：清空已选设备与旧搜索结果；设备框改为「输入关键词才搜索」，不再预读全量
  if (props.showDeviceSelect) {
    selectedIds.value = []
    deviceOptions.value = []
    if (props.single) emit('change', null, null)
  }
}

// 设备框远程搜索：输入关键词时才按名称/主机查询（不预读全量，避免卡顿）
// 支持在当前层级范围内（org_node_id）过滤；关键词为空时返回范围内前 50 条作为提示
async function remoteSearch(query: string) {
  const p = buildPath()
  if (!p && !query) {
    deviceOptions.value = []
    return
  }
  loadingDevices.value = true
  try {
    const res = await getDevices({
      page: 1,
      page_size: 50,
      org_node_id: p?.org_node_id ?? undefined,
      search: query || undefined,
      writable: props.writableOnly || undefined,
      enabled: props.enabledOnly || undefined
    })
    const { list } = unwrapList(res)
    deviceOptions.value = list
  } finally {
    loadingDevices.value = false
  }
}

// 设备多选 change：支持手动输入（allow-create）与逗号分隔
// 选中值可能是 设备ID（number）或 用户输入的文本（string，可能逗号分隔多个设备名）
// 预置选中值回填：单选模式下，若外部已设定设备 ID（如编辑告警规则），
// 需要按 id 拉取设备对象以展示名称
watch(
  () => props.modelValue,
  async (v) => {
    if (!props.single) return
    const id = typeof v === 'number' ? v : null
    if (id == null) return
    if (deviceOptions.value.some((d) => d.id === id)) return
    try {
      const res = await getDevices({ page: 1, page_size: 50, ids: String(id) })
      const { list } = unwrapList(res)
      const known = new Set(deviceOptions.value.map((d) => d.id))
      deviceOptions.value = [...deviceOptions.value, ...list.filter((d) => !known.has(d.id))]
    } catch {
      /* ignore */
    }
  },
  { immediate: true }
)

function onDeviceChange(val: (number | string)[]) {
  const nameMap = new Map(deviceOptions.value.map((d) => [d.name.toLowerCase(), d.id]))
  const ids = new Set<number>()
  for (const v of val) {
    if (typeof v === 'number') {
      ids.add(v)
    } else {
      for (const part of String(v).split(',')) {
        const name = part.trim().toLowerCase()
        if (!name) continue
        const id = nameMap.get(name)
        if (id != null) ids.add(id)
      }
    }
  }
  selectedIds.value = Array.from(ids)
  // 单选模式：emit 完整设备对象供宿主（如加载点位）使用
  if (props.single) {
    const id = ids.size ? Array.from(ids)[0] : null
    emit('change', id, pickDevice(id))
  }
}

function pickDevice(id: number | null): any {
  if (id == null) return null
  return deviceOptions.value.find((d) => d.id === id) || null
}

function selectAllVisible() {
  if (props.single) return
  const set = new Set(selectedIds.value)
  deviceOptions.value.forEach((d) => set.add(d.id))
  selectedIds.value = Array.from(set)
}
function clearSelection() {
  selectedIds.value = []
}
function clearPath() {
  selections.value = selections.value.map(() => null)
  deviceOptions.value = []
  emit('update:path', null)
}
function resetAll() {
  selections.value = selections.value.map(() => null)
  deviceOptions.value = []
  selectedIds.value = []
  emit('update:path', null)
  if (props.single) emit('change', null, null)
  emit('search') // 重置后展示全部设备
}

const statusMap: Record<
  string,
  { label: string; type: 'success' | 'info' | 'danger' | 'warning' }
> = {
  online: { label: '在线', type: 'success' },
  offline: { label: '离线', type: 'info' },
  error: { label: '异常', type: 'danger' },
  maintenance: { label: '维护', type: 'warning' }
}
function statusOf(s: string) {
  return statusMap[s] || { label: s || '未知', type: 'info' as const }
}

onMounted(async () => {
  loading.value = true
  try {
    // 仅拉取层级结构（不带设备），降低负载；多实例共享同一份缓存
    const data = await loadOrgTree()
    levels.value = data.levels
    tree.value = data.tree
    selections.value = levels.value.slice(0, -1).map(() => null)
  } finally {
    loading.value = false
  }
})

// 暴露给宿主页面调用
defineExpose({ clearPath, clearSelection, resetAll, selectAllVisible, deviceOptionCount: computed(() => deviceOptions.value.length) })
</script>

<template>
  <div class="org-cascade" v-loading="loading">
    <!-- 一行级联下拉框：厂/区/班/站/位置 + 设备名称(可输入/检索/多选/逗号分隔) -->
    <div class="oc-bar">
      <ElSelect
        v-for="(lv, i) in groupLevels"
        :key="lv.key"
        :model-value="selections[i]?.label ?? undefined"
        :placeholder="lv.label"
        clearable
        class="oc-select"
        @change="(v) => onGroupChange(i, v)"
      >
        <ElOption
          v-for="node in levelOptions(i)"
          :key="node.label"
          :label="node.label"
          :value="node.label"
        />
      </ElSelect>

      <ElSelect
        v-if="showDeviceSelect"
        :model-value="selectedIds"
        :loading="loadingDevices"
        remote
        :remote-method="remoteSearch"
        remote-show-suffix
        :placeholder="hasCascade ? '输入设备名/主机搜索' : '输入设备名/主机搜索（不限层级）'"
        :multiple="!single"
        filterable
        collapse-tags
        collapse-tags-tooltip
        clearable
        class="oc-select oc-dev"
        @change="onDeviceChange"
      >
        <ElOption v-for="d in deviceOptions" :key="d.id" :label="d.name" :value="d.id">
          <span class="oc-opt">
            <span class="dot" :class="d.status"></span>
            {{ d.name }}
            <ElTag :type="statusOf(d.status).type || 'info'" size="small" effect="plain" class="oc-opt-tag">
              {{ statusOf(d.status).label }}
            </ElTag>
          </span>
        </ElOption>
      </ElSelect>

      <ElButton v-if="showActions" type="primary" @click="emit('search')">搜索</ElButton>
      <ElButton v-if="showActions" @click="resetAll">重置</ElButton>
    </div>

    <!-- 底部摘要 + 批量快捷操作（showDeviceActions 控制，设备管理页关闭；单选模式隐藏） -->
    <div v-if="showDeviceActions && showDeviceSelect && !single" class="oc-footer">
      <span v-if="selectedIds.length" class="oc-sel"
        >已选 <b>{{ selectedIds.length }}</b> 台设备</span
      >
      <span v-else class="oc-sel muted">未选择设备（显示全部）</span>
      <span class="oc-actions">
        <ElButton link type="primary" :disabled="!deviceOptions.length" @click="selectAllVisible"
          >全选当前</ElButton
        >
        <ElButton link type="primary" :disabled="!selectedIds.length" @click="clearSelection"
          >清空已选</ElButton
        >
      </span>
    </div>
  </div>
</template>

<style scoped>
.org-cascade {
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  background: var(--el-fill-color-blank);
  padding: 12px;
}
.oc-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.oc-select {
  width: 150px;
}
.oc-dev {
  width: 280px;
}
.oc-opt {
  display: flex;
  align-items: center;
  gap: 6px;
}
.oc-opt-tag {
  margin-left: auto;
}
.oc-footer {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-top: 10px;
  font-size: 13px;
  flex-wrap: wrap;
}
.oc-sel b {
  color: var(--el-color-primary);
}
.oc-sel.muted {
  color: var(--el-text-color-secondary);
}
.oc-path {
  color: var(--el-text-color-secondary);
}
.oc-actions {
  margin-left: auto;
  display: flex;
  gap: 4px;
}
.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
.dot.online {
  background: #67c23a;
}
.dot.offline {
  background: #909399;
}
.dot.error {
  background: #f56c6c;
}
.dot.maintenance {
  background: #e6a23c;
}
</style>
