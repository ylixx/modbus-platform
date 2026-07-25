<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ContentWrap } from '@/components/ContentWrap'
import {
  ElRow,
  ElCol,
  ElCard,
  ElButton,
  ElTag,
  ElEmpty,
  ElMessage,
  ElMessageBox
} from 'element-plus'
import { getScadaWidgets, deleteScadaWidget, unwrapList } from '@/api/modbus'

defineOptions({ name: 'ScadaWidgets' })

const router = useRouter()
const loading = ref(false)
const list = ref<any[]>([])
const fetchList = async () => {
  loading.value = true
  try {
    list.value = unwrapList(await getScadaWidgets()).list
  } finally {
    loading.value = false
  }
}
const remove = async (row: any) => {
  await ElMessageBox.confirm(`确认删除图元「${row.name}」？`, '提示', { type: 'warning' })
  await deleteScadaWidget(row.id)
  ElMessage.success('删除成功')
  fetchList()
}

onMounted(fetchList)
</script>

<template>
  <ContentWrap title="自定义图元库">
    <template #header>
      <div class="flex-grow flex justify-end">
        <ElButton @click="router.push('/scada/pages')">返回画面</ElButton>
      </div>
    </template>
    <ElEmpty v-if="!loading && !list.length" description="暂无自定义图元" />
    <ElRow :gutter="16">
      <ElCol v-for="w in list" :key="w.id" :xs="12" :sm="8" :md="6" class="mb-16px">
        <ElCard shadow="hover" class="h-full">
          <div class="flex items-center justify-between mb-8px">
            <span class="font-600">{{ w.name }}</span>
            <ElTag size="small">{{ w.type || w.category || '图元' }}</ElTag>
          </div>
          <div class="text-12px text-gray-400 mb-12px">{{ w.description || '无描述' }}</div>
          <ElButton v-hasPermi="['scada.write']" link type="danger" size="small" @click="remove(w)"
            >删除</ElButton
          >
        </ElCard>
      </ElCol>
    </ElRow>
  </ContentWrap>
</template>
