<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElButton, ElTag, ElSelect, ElOption, ElEmpty } from 'element-plus'
import { getOrgTreeApi, OrgLevel, OrgNode, OrgDevice } from '@/api/hierarchy'
import { getDevices, unwrapList } from '@/api/modbus'

// v-model: 选中的设备 ID 列表；v-model:path: 选中的层级路径（用于表格筛选）
// emit 'search': 用户点击「搜索」按钮，宿主页面据此刷新设备列表
const props = withDefaults(
  defineProps<{
    modelValue?: number[]
    path?: OrgPath | null
  }>(),
  { modelValue: () => [], path: null }
)
const emit = defineEmits<{
  'update:modelValue': [number[]]
  'update:path': [OrgPath | null]
  search: []
}>()

const loading = ref(false)
const levels = ref<OrgLevel[]>([])
const tree = ref<OrgNode[]>([])
// 分组层级（厂区/班/站/位置）的当前选中节点
const selections = ref<(OrgNode | null)[]>([])
// 设备下拉选项：仅在级联改变时按范围从 /devices 查询，默认不加载全部设备
const deviceOptions = ref<OrgDevice[]>([])
const loadingDevices = ref(false)

interface Leaf {
  device: OrgDevice
  path: string[]
}
// 级联选择结果：最深选中节点的 org_node_id（用于按子树筛选设备）+ 展示标签
interface OrgPath {
  org_node_id: number | null
  labels: string[]
}

const groupLevels = computed<OrgLevel[]>(() => levels.value.slice(0, -1))
const deviceLevel = computed<OrgLevel | undefined>(() => levels.value[levels.value.length - 1])
const selectedIds = computed<number[]>({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v)
})
// 是否已选择至少一个层级（决定设备框是否可用）
const hasCascade = computed(() => selections.value.some((s) => s != null))

function collectLeaves(nodes: OrgNode[], prefix: string[], acc: Leaf[]) {
  for (const n of nodes) {
    if (n.type === 'device' && n.device) {
      acc.push({ device: n.device, path: [...prefix, n.label] })
    } else if (n.children) {
      collectLeaves(n.children, [...prefix, n.label], acc)
    }
  }
}

const allLeaves = computed<Leaf[]>(() => {
  const acc: Leaf[] = []
  collectLeaves(tree.value, [], acc)
  return acc
})

// 第 i 个分组下拉框的可选项（随上层联动）
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
  // 层级变化：清空已选设备，并按新范围查询设备下拉项
  selectedIds.value = []
  fetchDeviceOptions()
}

// 按当前层级范围查询设备（用于填充设备下拉框）
// 注意：后端 page_size 上限为 100（Query(..., le=100)），超过会返回 422。
// 故用 page_size=100 且分页循环拉取，确保范围设备超过 100 台时也能全部载入。
async function fetchDeviceOptions() {
  const p = buildPath()
  if (!p) {
    deviceOptions.value = []
    return
  }
  loadingDevices.value = true
  try {
    const all: any[] = []
    let page = 1
    const PAGE_SIZE = 100
    while (true) {
      const res = await getDevices({
        page,
        page_size: PAGE_SIZE,
        org_node_id: p.org_node_id ?? undefined
      })
      const { list, total } = unwrapList(res)
      all.push(...list)
      if (all.length >= total || list.length < PAGE_SIZE) break
      page += 1
    }
    deviceOptions.value = all
  } finally {
    loadingDevices.value = false
  }
}

// 设备多选 change：支持手动输入（allow-create）与逗号分隔
// 选中值可能是 设备ID（number）或 用户输入的文本（string，可能逗号分隔多个设备名）
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
}

function selectAllVisible() {
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
    // 仅拉取层级结构（不带设备），降低负载
    const res = await getOrgTreeApi({ with_devices: false })
    levels.value = res.data.levels
    tree.value = res.data.tree
    selections.value = levels.value.slice(0, -1).map(() => null)
  } finally {
    loading.value = false
  }
})

// 暴露给宿主页面调用
defineExpose({ clearPath, clearSelection, resetAll })
</script>

<template>
  <div class="org-cascade" v-loading="loading">
    <!-- 一行级联下拉框：厂区/班/站/位置 + 设备名称(可输入/检索/多选/逗号分隔) -->
    <div class="oc-bar">
      <ElSelect
        v-for="(lv, i) in groupLevels"
        :key="lv.key"
        :model-value="selections[i]?.label ?? null"
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
        :model-value="selectedIds"
        :disabled="!hasCascade"
        :loading="loadingDevices"
        :placeholder="hasCascade ? deviceLevel?.label || '设备名称' : '请先选择上级层级'"
        multiple
        filterable
        allow-create
        default-first-option
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
            <ElTag :type="statusOf(d.status).type" size="small" effect="plain" class="oc-opt-tag">
              {{ statusOf(d.status).label }}
            </ElTag>
          </span>
        </ElOption>
      </ElSelect>

      <ElButton type="primary" @click="emit('search')">搜索</ElButton>
      <ElButton @click="resetAll">重置</ElButton>
    </div>

    <!-- 底部摘要 + 批量快捷操作 -->
    <div class="oc-footer">
      <span v-if="selectedIds.length" class="oc-sel"
        >已选 <b>{{ selectedIds.length }}</b> 台设备</span
      >
      <span v-else class="oc-sel muted">未选择设备（显示全部）</span>
      <span v-if="path" class="oc-path"> 层级筛选：{{ path.labels.join(' / ') }} </span>
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
