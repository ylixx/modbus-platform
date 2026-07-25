<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ContentWrap } from '@/components/ContentWrap'
import { ElButton, ElEmpty } from 'element-plus'
import { getScadaPage, unwrap } from '@/api/modbus'

defineOptions({ name: 'ScadaViewer' })

const route = useRoute()
const router = useRouter()
const id = route.params.id as string
const page = ref<any>({ name: '', config: {} })
const widgets = ref<any[]>([])

const fetchPage = async () => {
  const body = unwrap(await getScadaPage(Number(id)))
  page.value = body || {}
  widgets.value = body?.config?.widgets || body?.widgets || []
}

onMounted(fetchPage)
</script>

<template>
  <ContentWrap :title="`SCADA 运行 - ${page.name || ''}`">
    <template #header>
      <div class="flex-grow flex justify-end">
        <ElButton @click="router.push('/scada/pages')">返回</ElButton>
        <ElButton
          v-hasPermi="['scada.write']"
          type="primary"
          @click="router.push(`/scada/editor/${id}`)"
        >
          编辑
        </ElButton>
      </div>
    </template>
    <div class="canvas">
      <ElEmpty v-if="!widgets.length" description="该画面尚未配置图元" />
      <div
        v-for="(w, i) in widgets"
        :key="i"
        class="widget"
        :style="{ left: (w.x || 0) + 'px', top: (w.y || 0) + 'px' }"
      >
        {{ w.label || w.type || '图元' }}
      </div>
    </div>
  </ContentWrap>
</template>

<style scoped>
.canvas {
  position: relative;
  min-height: 500px;
  background: var(--el-fill-color-lighter);
  border: 1px dashed var(--el-border-color);
  border-radius: 8px;
  overflow: auto;
}
.widget {
  position: absolute;
  padding: 8px 12px;
  background: var(--el-color-primary-light-9);
  border: 1px solid var(--el-color-primary);
  border-radius: 4px;
  font-size: 13px;
}
</style>
