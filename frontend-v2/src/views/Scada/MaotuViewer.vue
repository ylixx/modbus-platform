<script setup lang="ts">
/**
 * SCADA 运行查看器（maotu 引擎）
 * - 渲染 mt-edit 保存的 exportJson
 * - WS 实时值 → item.device_bind → setItemAttrByID 注入
 * - 事件 custom_code 中可调用 window.$mtWriteSignal(signalId, value) 写值
 */
import { ref, onMounted, onUnmounted, watch, nextTick, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElButton, ElBadge, ElMessage, ElDrawer } from 'element-plus'
import { getScadaPage, getScadaPages, getDeviceTags, writeDevice, unwrap, unwrapList } from '@/api/modbus'
import { MtPreview, leftAsideStore } from '@/lib/maotu'
import { isMtPageConfig } from './maotu/types'
import { chemSymbols } from './maotu/chemicalSymbols'
import type { MtExportJson, MtItem } from './maotu/types'
import { useWsStore } from '@/store/modules/websocket'
import { wsManager } from '@/utils/websocket'
import type { WsLiveValue } from '@/utils/websocket'

defineOptions({ name: 'ScadaMaotuViewer' })

const route = useRoute()
const router = useRouter()
const wsStore = useWsStore()
const id = route.params.id as string

const previewRef = ref<any>()
const page = ref<any>({ name: '', config_json: '{}' })
const isFullscreen = ref(false)
const pagesList = ref<any[]>([])
const drawerVisible = ref(false)
let unsubFns: (() => void)[] = []

const wsConnected = computed(() => wsStore.connected)

/** signalId("device:tagName") → tagId */
const tagIdIndex = new Map<string, number>()
/** root item 列表（含 group children） */
let bindItems: MtItem[] = []

const collectBindItems = (items: MtItem[], acc: MtItem[]) => {
  for (const it of items) {
    acc.push(it)
    if (it.children?.length) collectBindItems(it.children, acc)
  }
}

const applyLiveValue = (signalId: string, value: number, tagId?: number) => {
  if (tagId !== undefined) tagIdIndex.set(signalId, tagId)
  const target = previewRef.value
  if (!target) return
  for (const it of bindItems) {
    const b = it.device_bind
    if (b?.signalId === signalId && b.attr) {
      let v: any = value
      if (b.attr === 'fill' || b.attr === 'stroke') v = value ? '#67C23A' : '#F56C6C'
      else if (b.attr === 'visibility') v = value ? 'visible' : 'hidden'
      target.setItemAttrByID(it.id, b.attr, v)
    }
  }
}

const onLiveValue = (msg: any) => {
  const d = msg.data as WsLiveValue
  if (!d) return
  applyLiveValue(`${d.device_id}:${d.tag_name}`, d.value, d.tag_id)
}

const loadPage = async (pid: number) => {
  const body = unwrap(await getScadaPage(pid))
  page.value = body || {}
  let config: MtExportJson | null = null
  try {
    const json =
      typeof body?.config_json === 'string' ? JSON.parse(body.config_json) : body?.config_json
    if (isMtPageConfig(json)) config = json
  } catch {
    config = null
  }
  await nextTick()
  bindItems = []
  if (config) {
    collectBindItems(config.json, bindItems)
    previewRef.value?.setImportJson(config)
  }
  // 回放 WS 缓存中的最近值
  for (const [signalId, v] of Object.entries(wsStore.liveData)) {
    applyLiveValue(signalId, v.value, v.tag_id)
  }
}

const resolveTagId = async (signalId: string): Promise<number> => {
  const cached = tagIdIndex.get(signalId)
  if (cached !== undefined) return cached
  const idx = signalId.indexOf(':')
  if (idx <= 0) throw new Error('signalId 格式错误')
  const deviceId = Number(signalId.slice(0, idx))
  const tagName = signalId.slice(idx + 1)
  const res: any = await getDeviceTags(deviceId, { page_size: 500 })
  const tags = unwrapList(res).list
  const tag = tags.find((t: any) => t.name === tagName)
  if (!tag) throw new Error(`点位 ${signalId} 不存在`)
  tagIdIndex.set(signalId, tag.id)
  return tag.id
}

const writeValue = async (signalId: string, value: number) => {
  const idx = signalId.indexOf(':')
  const deviceId = Number(signalId.slice(0, idx))
  const tagId = await resolveTagId(signalId)
  try {
    await writeDevice(deviceId, { tag_id: tagId, value })
    ElMessage.success(`${signalId} = ${value}`)
  } catch (e: any) {
    ElMessage.error(e?.message || '写入失败')
  }
}

const installWriteBridge = () => {
  ;(window as any).$mtWriteSignal = (signalId: string, value: any) => {
    const v = Number(value)
    if (Number.isNaN(v)) {
      ElMessage.warning('请输入有效的数值')
      return Promise.resolve(false)
    }
    return writeValue(signalId, v)
  }
}

const fetchPagesList = async () => {
  try {
    const body = unwrap(await getScadaPages())
    pagesList.value = Array.isArray(body) ? body : []
  } catch {
    pagesList.value = []
  }
}

const switchPage = (pid: number) => {
  drawerVisible.value = false
  if (Number(pid) !== Number(route.params.id)) router.push(`/scada/m-view/${pid}`)
}

const viewerContainer = ref<HTMLElement>()
const toggleFullscreen = async () => {
  const el = viewerContainer.value
  if (!el) return
  try {
    if (!document.fullscreenElement) {
      await el.requestFullscreen()
      isFullscreen.value = true
    } else {
      await document.exitFullscreen()
      isFullscreen.value = false
    }
  } catch {
    isFullscreen.value = !isFullscreen.value
  }
}
const onFullscreenChange = () => {
  isFullscreen.value = !!document.fullscreenElement
}

watch(
  () => route.params.id,
  (n) => {
    if (n) loadPage(Number(n))
  }
)

onMounted(async () => {
  leftAsideStore.registerConfig('石化图元', chemSymbols)
  installWriteBridge()
  fetchPagesList()
  unsubFns.push(wsManager.on('live_value', onLiveValue))
  document.addEventListener('fullscreenchange', onFullscreenChange)
  await loadPage(Number(route.params.id))
})

onUnmounted(() => {
  unsubFns.forEach((fn) => fn())
  document.removeEventListener('fullscreenchange', onFullscreenChange)
  delete (window as any).$mtWriteSignal
})
</script>

<template>
  <div
    ref="viewerContainer"
    :class="['maotu-viewer', { fullscreen: isFullscreen }]"
  >
    <div class="maotu-viewer-toolbar">
      <div class="flex items-center">
        <span class="text-16px font-600 mr-12px">{{ page.name || 'SCADA 运行' }}</span>
        <ElBadge :type="wsConnected ? 'success' : 'danger'" is-dot>
          <span class="text-12px text-gray-400">
            {{ wsConnected ? '实时数据' : '离线' }}
          </span>
        </ElBadge>
      </div>
      <div class="flex items-center gap-8px">
        <ElButton size="small" @click="drawerVisible = true">画面列表</ElButton>
        <ElButton size="small" @click="toggleFullscreen">
          {{ isFullscreen ? '退出全屏' : '全屏' }}
        </ElButton>
        <ElButton size="small" type="primary" @click="router.push(`/scada/m-editor/${id}`)">
          编辑
        </ElButton>
        <ElButton size="small" @click="router.push('/scada/pages')">返回</ElButton>
      </div>
    </div>

    <ElDrawer v-model="drawerVisible" title="画面列表" size="280px">
      <div
        v-for="p in pagesList"
        :key="p.id"
        class="maotu-page-item"
        :class="{ active: Number(p.id) === Number(route.params.id) }"
        @click="switchPage(p.id)"
      >
        <div class="page-name">{{ p.name }}</div>
        <div class="page-meta">{{ p.id }} · {{ p.width }}×{{ p.height }}</div>
      </div>
      <div v-if="pagesList.length === 0" class="text-12px text-gray-400">暂无其他画面</div>
    </ElDrawer>

    <div class="maotu-viewer-canvas">
      <MtPreview ref="previewRef" :can-drag="true" :can-zoom="true" :show-popover="true" />
    </div>
  </div>
</template>

<style scoped>
.maotu-viewer {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 80px);
  background: #10141d;
  overflow: hidden;
}
.maotu-viewer.fullscreen {
  height: 100vh;
}
.maotu-viewer-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 12px;
  background: #1a1d27;
  border-bottom: 1px solid #2a2f3a;
  flex-shrink: 0;
}
.maotu-viewer-canvas {
  flex: 1;
  overflow: hidden;
}
.maotu-viewer-canvas :deep(.canvasArea) {
  max-width: 100%;
}
.maotu-page-item {
  padding: 8px 10px;
  border-radius: 6px;
  cursor: pointer;
  margin-bottom: 4px;
}
.maotu-page-item:hover {
  background: #2a2f3a;
}
.maotu-page-item.active {
  background: #26384f;
}
.maotu-page-item .page-name {
  font-size: 13px;
}
.maotu-page-item .page-meta {
  font-size: 11px;
  opacity: 0.6;
}
</style>