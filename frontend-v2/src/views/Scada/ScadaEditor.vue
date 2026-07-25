<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ContentWrap } from '@/components/ContentWrap'
import { ElButton, ElInput, ElMessage, ElAlert } from 'element-plus'
import { getScadaPage, updateScadaPage, unwrap } from '@/api/modbus'

defineOptions({ name: 'ScadaEditor' })

const route = useRoute()
const router = useRouter()
const id = route.params.id as string
const page = ref<any>({ name: '', config: {} })
const configText = ref('{}')

const fetchPage = async () => {
  const body = unwrap(await getScadaPage(Number(id)))
  page.value = body || {}
  configText.value = JSON.stringify(body?.config ?? {}, null, 2)
}
const save = async () => {
  let config: any = {}
  try {
    config = JSON.parse(configText.value || '{}')
  } catch (e) {
    ElMessage.error('画面配置不是合法 JSON')
    return
  }
  await updateScadaPage(Number(id), {
    name: page.value.name,
    description: page.value.description,
    config
  })
  ElMessage.success('保存成功')
}

onMounted(fetchPage)
</script>

<template>
  <ContentWrap :title="`SCADA 编辑器 - ${page.name || ''}`">
    <template #header>
      <div class="flex-grow flex justify-end">
        <ElButton @click="router.push('/scada/pages')">返回</ElButton>
        <ElButton type="primary" @click="save">保存画面</ElButton>
      </div>
    </template>
    <ElAlert
      title="可视化拖拽画布为重型模块，此处提供画面配置（JSON）编辑能力，后续可接入图元拖拽画布。"
      type="info"
      :closable="false"
      class="mb-12px"
    />
    <div class="mb-12px">
      <span class="text-14px text-gray-500 mr-8px">画面名称：</span>
      <ElInput v-model="page.name" class="!w-260px" />
    </div>
    <ElInput v-model="configText" type="textarea" :rows="18" class="font-mono" />
  </ContentWrap>
</template>
