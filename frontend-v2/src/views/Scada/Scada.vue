<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ContentWrap } from '@/components/ContentWrap'
import {
  ElButton,
  ElTable,
  ElTableColumn,
  ElDialog,
  ElForm,
  ElFormItem,
  ElInput,
  ElMessage,
  ElMessageBox
} from 'element-plus'
import {
  getScadaPages,
  createScadaPage,
  deleteScadaPage,
  duplicateScadaPage,
  unwrapList
} from '@/api/modbus'

defineOptions({ name: 'ScadaPages' })

const router = useRouter()
const loading = ref(false)
const list = ref<any[]>([])
const fetchList = async () => {
  loading.value = true
  try {
    list.value = unwrapList(await getScadaPages()).list
  } finally {
    loading.value = false
  }
}

const dialogVisible = ref(false)
const formRef = ref()
const form = reactive<any>({ name: '', description: '' })
const rules = { name: [{ required: true, message: '请输入画面名称', trigger: 'blur' }] }
const openCreate = () => {
  Object.assign(form, { name: '', description: '' })
  dialogVisible.value = true
}
const submit = async () => {
  await formRef.value?.validate()
  await createScadaPage({ name: form.name, description: form.description, config: {} })
  ElMessage.success('创建成功')
  dialogVisible.value = false
  fetchList()
}
const remove = async (row: any) => {
  await ElMessageBox.confirm(`确认删除画面「${row.name}」？`, '提示', { type: 'warning' })
  await deleteScadaPage(row.id)
  ElMessage.success('删除成功')
  fetchList()
}
const duplicate = async (row: any) => {
  await duplicateScadaPage(row.id)
  ElMessage.success('已复制')
  fetchList()
}

onMounted(fetchList)
</script>

<template>
  <ContentWrap title="SCADA 画面">
    <template #header>
      <div class="flex-grow flex justify-end">
        <ElButton @click="router.push('/scada/widgets')">图元库</ElButton>
        <ElButton v-hasPermi="['scada.write']" type="success" @click="openCreate"
          >新建画面</ElButton
        >
      </div>
    </template>
    <ElTable v-loading="loading" :data="list" border stripe>
      <ElTableColumn prop="id" label="ID" width="70" />
      <ElTableColumn prop="name" label="画面名称" min-width="160" show-overflow-tooltip />
      <ElTableColumn prop="description" label="描述" min-width="200" show-overflow-tooltip />
      <ElTableColumn prop="updated_at" label="更新时间" width="180" />
      <ElTableColumn label="操作" width="280" fixed="right">
        <template #default="{ row }">
          <ElButton link type="primary" @click="router.push(`/scada/view/${row.id}`)"
            >运行</ElButton
          >
          <ElButton
            v-hasPermi="['scada.write']"
            link
            type="primary"
            @click="router.push(`/scada/editor/${row.id}`)"
            >编辑</ElButton
          >
          <ElButton v-hasPermi="['scada.write']" link type="primary" @click="duplicate(row)"
            >复制</ElButton
          >
          <ElButton v-hasPermi="['scada.write']" link type="danger" @click="remove(row)"
            >删除</ElButton
          >
        </template>
      </ElTableColumn>
    </ElTable>

    <ElDialog v-model="dialogVisible" title="新建 SCADA 画面" width="460px">
      <ElForm ref="formRef" :model="form" :rules="rules" label-width="80px">
        <ElFormItem label="名称" prop="name">
          <ElInput v-model="form.name" />
        </ElFormItem>
        <ElFormItem label="描述">
          <ElInput v-model="form.description" type="textarea" :rows="2" />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="dialogVisible = false">取消</ElButton>
        <ElButton type="primary" @click="submit">确定</ElButton>
      </template>
    </ElDialog>
  </ContentWrap>
</template>
