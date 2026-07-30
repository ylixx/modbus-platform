<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ContentWrap } from '@/components/ContentWrap'
import {
  ElButton,
  ElTable,
  ElTableColumn,
  ElTag,
  ElDialog,
  ElForm,
  ElFormItem,
  ElInput,
  ElSelect,
  ElOption,
  ElSwitch,
  ElMessage,
  ElMessageBox
} from 'element-plus'
import { CodeEditor } from '@/components/CodeEditor'
import {
  getScripts,
  createScript,
  updateScript,
  deleteScript,
  testScript,
  getScriptTemplates,
  unwrapList
} from '@/api/modbus'

defineOptions({ name: 'Scripts' })

const loading = ref(false)
const list = ref<any[]>([])
const templates = ref<any[]>([])
const fetchList = async () => {
  loading.value = true
  try {
    list.value = unwrapList(await getScripts()).list
  } finally {
    loading.value = false
  }
}

const fetchTemplates = async () => {
  try {
    const res = await getScriptTemplates()
    templates.value = unwrapList(res).list
  } catch {
    templates.value = []
  }
}

const dialogVisible = ref(false)
const dialogTitle = ref('新增脚本')
const formRef = ref()
const form = reactive<any>({
  id: null,
  name: '',
  language: 'python',
  code: '',
  description: '',
  enabled: true
})
const rules = {
  name: [{ required: true, message: '请输入脚本名称', trigger: 'blur' }],
  code: [{ required: true, message: '请输入脚本内容', trigger: 'blur' }]
}

const openCreate = () => {
  dialogTitle.value = '新增脚本'
  Object.assign(form, {
    id: null, name: '', language: 'python',
    code: '# result = value * 2\n', description: '', enabled: true
  })
  dialogVisible.value = true
}
const openEdit = (row: any) => {
  dialogTitle.value = '编辑脚本'
  Object.assign(form, {
    id: row.id, name: row.name, language: row.language || 'python',
    code: row.code || '', description: row.description || '',
    enabled: row.enabled !== false
  })
  dialogVisible.value = true
}
const openFromTemplate = (tpl: any) => {
  dialogTitle.value = '从模板创建'
  Object.assign(form, {
    id: null, name: tpl.name || '', language: tpl.language || 'python',
    code: tpl.code || '', description: tpl.description || '', enabled: true
  })
  dialogVisible.value = true
}
const submit = async () => {
  await formRef.value?.validate()
  const payload = { ...form }
  delete payload.id
  try {
    if (form.id) {
      await updateScript(form.id, payload)
      ElMessage.success('更新成功')
    } else {
      await createScript(payload)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    fetchList()
  } catch (e: any) {
    ElMessage.error(e?.message || '操作失败')
  }
}
const remove = async (row: any) => {
  await ElMessageBox.confirm(`确认删除脚本「${row.name}」？`, '提示', { type: 'warning' })
  try {
    await deleteScript(row.id)
    ElMessage.success('删除成功')
    fetchList()
  } catch (e: any) {
    ElMessage.error(e?.message || '删除失败')
  }
}

const testing = ref(false)
const doTest = async () => {
  testing.value = true
  try {
    const res = await testScript({ language: form.language, code: form.code, raw_value: 1 })
    const body = (res as any)?.data
    ElMessage.success('测试执行完成：' + JSON.stringify(body?.result ?? body))
  } catch (e: any) {
    ElMessage.error(e?.message || '测试失败')
  } finally {
    testing.value = false
  }
}

onMounted(() => {
  fetchList()
  fetchTemplates()
})
</script>

<template>
  <ContentWrap title="脚本算法">
    <template #header>
      <div class="flex-grow flex justify-end gap-8px">
        <ElSelect
          v-if="templates.length"
          placeholder="从模板创建"
          class="!w-180px"
          filterable
          @change="openFromTemplate"
        >
          <ElOption
            v-for="tpl in templates"
            :key="tpl.id || tpl.name"
            :label="tpl.name"
            :value="tpl"
          />
        </ElSelect>
        <ElButton v-hasPermi="['script.write']" type="success" @click="openCreate">新增脚本</ElButton>
      </div>
    </template>
    <ElTable v-loading="loading" :data="list" border stripe>
      <template #empty>
        <div class="py-20px text-center text-gray-400">暂无脚本</div>
      </template>
      <ElTableColumn prop="id" label="ID" width="70" />
      <ElTableColumn prop="name" label="脚本名称" min-width="160" show-overflow-tooltip />
      <ElTableColumn prop="language" label="语言" width="110" />
      <ElTableColumn prop="description" label="描述" min-width="200" show-overflow-tooltip />
      <ElTableColumn label="启用" width="90">
        <template #default="{ row }">
          <ElTag :type="row.enabled !== false ? 'success' : 'info'">
            {{ row.enabled !== false ? '启用' : '停用' }}
          </ElTag>
        </template>
      </ElTableColumn>
      <ElTableColumn label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <ElButton v-hasPermi="['script.write']" link type="primary" @click="openEdit(row)">编辑</ElButton>
          <ElButton v-hasPermi="['script.write']" link type="danger" @click="remove(row)">删除</ElButton>
        </template>
      </ElTableColumn>
    </ElTable>

    <ElDialog v-model="dialogVisible" :title="dialogTitle" width="800px" top="5vh" @close="formRef?.resetFields()">
      <ElForm ref="formRef" :model="form" :rules="rules" label-width="80px">
        <ElFormItem label="名称" prop="name">
          <ElInput v-model="form.name" placeholder="请输入脚本名称" />
        </ElFormItem>
        <ElFormItem label="语言">
          <ElSelect v-model="form.language" class="!w-160px">
            <ElOption label="Python" value="python" />
            <ElOption label="JavaScript" value="javascript" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="描述">
          <ElInput v-model="form.description" type="textarea" :rows="2" />
        </ElFormItem>
        <ElFormItem label="脚本内容" prop="code">
          <div class="w-full border border-solid border-gray-200 rounded">
            <CodeEditor
              v-model="form.code"
              :language="form.language === 'python' ? 'python' : 'javascript'"
              theme="vs-dark"
              :height="400"
              :language-selector="false"
              :theme-selector="false"
            />
          </div>
        </ElFormItem>
        <ElFormItem label="启用">
          <ElSwitch v-model="form.enabled" />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton :loading="testing" @click="doTest">测试运行</ElButton>
        <ElButton @click="dialogVisible = false">取消</ElButton>
        <ElButton type="primary" @click="submit">确定</ElButton>
      </template>
    </ElDialog>
  </ContentWrap>
</template>
