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
  ElMessageBox,
  ElEmpty,
  ElTag,
  ElRadioGroup,
  ElRadio
} from 'element-plus'
import {
  getScadaPages,
  createScadaPage,
  deleteScadaPage,
  duplicateScadaPage,
  unwrapList
} from '@/api/modbus'
import { defaultMtPageConfig } from './maotu/types'

defineOptions({ name: 'ScadaPages' })

const router = useRouter()
const loading = ref(false)
const list = ref<any[]>([])
const fetchList = async () => {
  loading.value = true
  try {
    const pages = unwrapList(await getScadaPages()).list
    list.value = (pages || []).map((p: any) => {
      let engine = 'svg'
      try {
        const json = typeof p.config_json === 'string' ? JSON.parse(p.config_json) : p.config_json
        if (json?.__engine === 'maotu') engine = 'maotu'
      } catch {
        // ignore
      }
      return { ...p, engine }
    })
  } finally {
    loading.value = false
  }
}

const dialogVisible = ref(false)
const formRef = ref()
const form = reactive<any>({ name: '', description: '', engine: 'svg' })
const rules = { name: [{ required: true, message: '请输入画面名称', trigger: 'blur' }] }
const openCreate = () => {
  Object.assign(form, { name: '', description: '', engine: 'svg' })
  dialogVisible.value = true
}
const submit = async () => {
  await formRef.value?.validate()
  try {
    const config_json = form.engine === 'maotu'
      ? JSON.stringify(defaultMtPageConfig())
      : '[]'
    await createScadaPage({
      name: form.name,
      description: form.description,
      config_json
    })
    ElMessage.success('创建成功')
    dialogVisible.value = false
    fetchList()
  } catch (e: any) {
    ElMessage.error(e?.message || '创建失败')
  }
}
const remove = async (row: any) => {
  await ElMessageBox.confirm(`确认删除画面「${row.name}」？`, '提示', { type: 'warning' })
  try {
    await deleteScadaPage(row.id)
    ElMessage.success('删除成功')
    fetchList()
  } catch (e: any) {
    ElMessage.error(e?.message || '删除失败')
  }
}
const duplicate = async (row: any) => {
  try {
    await duplicateScadaPage(row.id)
    ElMessage.success('已复制')
    fetchList()
  } catch (e: any) {
    ElMessage.error(e?.message || '复制失败')
  }
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
      <template #empty><ElEmpty description="暂无数据" :image-size="80" /></template>
      <ElTableColumn sortable prop="id" label="ID" width="70" />
      <ElTableColumn sortable prop="name" label="画面名称" min-width="160" show-overflow-tooltip />
      <ElTableColumn sortable prop="description" label="描述" min-width="200" show-overflow-tooltip />
      <ElTableColumn label="引擎" width="90" align="center">
        <template #default="{ row }">
          <ElTag v-if="row.engine === 'maotu'" type="success" size="small">maotu</ElTag>
          <ElTag v-else size="small" type="info">经典</ElTag>
        </template>
      </ElTableColumn>
      <ElTableColumn sortable prop="updated_at" label="更新时间" width="180" />
      <ElTableColumn label="操作" width="300" fixed="right">
        <template #default="{ row }">
          <ElButton
            link
            type="primary"
            @click="router.push(row.engine === 'maotu' ? `/scada/m-view/${row.id}` : `/scada/view/${row.id}`)"
            >运行</ElButton
          >
          <ElButton
            v-hasPermi="['scada.write']"
            link
            type="primary"
            @click="router.push(row.engine === 'maotu' ? `/scada/m-editor/${row.id}` : `/scada/editor/${row.id}`)"
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

    <ElDialog v-model="dialogVisible" title="新建 SCADA 画面" width="460px" @close="formRef?.resetFields()">
      <ElForm ref="formRef" :model="form" :rules="rules" label-width="80px">
        <ElFormItem label="名称" prop="name">
          <ElInput v-model="form.name" placeholder="请输入画面名称" />
        </ElFormItem>
<ElFormItem label="描述">
        <ElInput v-model="form.description" type="textarea" :rows="2" />
      </ElFormItem>
      <ElFormItem label="引擎">
        <ElRadioGroup v-model="form.engine">
          <ElRadio value="maotu">maotu 组态</ElRadio>
          <ElRadio value="svg">经典 SVG</ElRadio>
        </ElRadioGroup>
      </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="dialogVisible = false">取消</ElButton>
        <ElButton type="primary" @click="submit">确定</ElButton>
      </template>
    </ElDialog>
  </ContentWrap>
</template>
