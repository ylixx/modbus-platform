<script setup lang="ts">
/**
 * SCADA 组态编辑器（maotu 引擎）
 * - 加载/保存 scada_pages.config_json（__engine=maotu 格式）
 * - 右栏 deviceBind 插槽 → 点位绑定面板
 * - 内置实时预览弹窗
 */
import { ref, onMounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElDialog } from 'element-plus'
import { getScadaPage, updateScadaPage, unwrap } from '@/api/modbus'
import { MtEdit, MtPreview, leftAsideStore } from '@/lib/maotu'
import BindPanel from './maotu/BindPanel.vue'
import { chemSymbols } from './maotu/chemicalSymbols'
import { defaultMtPageConfig, isMtPageConfig } from './maotu/types'
import type { MtExportJson } from './maotu/types'

defineOptions({ name: 'ScadaMaotuEditor' })

const route = useRoute()
const router = useRouter()
const id = route.params.id as string

const mtEditRef = ref<any>()
const page = ref<any>({ name: '', config_json: '{}', width: 1920, height: 1080 })
const loading = ref(false)

const previewVisible = ref(false)
const previewJson = ref<MtExportJson | null>(null)

const loadPage = async () => {
  loading.value = true
  try {
    const body = unwrap(await getScadaPage(Number(id)))
    page.value = body || {}
    let config: MtExportJson
    try {
      const json = typeof body?.config_json === 'string' ? JSON.parse(body.config_json) : body?.config_json
      config = isMtPageConfig(json)
        ? json
        : defaultMtPageConfig(body?.width || 1920, body?.height || 1080, body?.background || '#10141d')
    } catch {
      config = defaultMtPageConfig(body?.width || 1920, body?.height || 1080, body?.background || '#10141d')
    }
    await nextTick()
    await nextTick()
    mtEditRef.value?.setImportJson(config)
  } catch (e: any) {
    ElMessage.error(e?.message || '画面加载失败')
  } finally {
    loading.value = false
  }
}

const onSave = async (exportJson: MtExportJson) => {
  const cfg = { ...exportJson, __engine: 'maotu' as const }
  try {
    await updateScadaPage(Number(id), {
      config_json: JSON.stringify(cfg),
      width: Math.round(exportJson.canvasCfg.width),
      height: Math.round(exportJson.canvasCfg.height)
    })
    ElMessage.success('保存成功')
  } catch (e: any) {
    ElMessage.error(e?.message || '保存失败')
  }
}

const onPreview = (exportJson: MtExportJson) => {
  previewJson.value = exportJson
  previewVisible.value = true
}

const onReturn = () => {
  router.push('/scada/pages')
}

onMounted(() => {
  leftAsideStore.registerConfig('石化图元', chemSymbols)
  loadPage()
})
</script>

<template>
  <div class="maotu-editor" v-loading="loading">
    <MtEdit
      ref="mtEditRef"
      :use-thumbnail="true"
      @on-save-click="onSave"
      @on-preview-click="onPreview"
      @on-return-click="onReturn"
    >
      <template #deviceBind="{ item }">
        <BindPanel :item="item" />
      </template>
    </MtEdit>

    <ElDialog
      v-model="previewVisible"
      fullscreen
      title="实时预览"
      class="maotu-preview-dialog"
      append-to-body
    >
      <MtPreview v-if="previewJson" :export-json="previewJson" :can-drag="false" :can-zoom="true" />
    </ElDialog>
  </div>
</template>

<style scoped>
.maotu-editor {
  height: calc(100vh - 80px);
  overflow: hidden;
}
.maotu-editor :deep(.mt-edit-aside) {
  background: var(--el-bg-color, #1a1d27);
}
:deep(.maotu-preview-dialog) {
  padding: 0;
}
:deep(.maotu-preview-dialog .el-dialog__body) {
  height: calc(100vh - 120px);
  padding: 0;
  background: #15171e;
}
</style>