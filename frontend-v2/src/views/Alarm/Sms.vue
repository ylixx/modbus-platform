<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ContentWrap } from '@/components/ContentWrap'
import {
  ElButton,
  ElTable,
  ElTableColumn,
  ElTag,
  ElTabs,
  ElTabPane,
  ElDialog,
  ElForm,
  ElFormItem,
  ElInput,
  ElSwitch,
  ElMessage,
  ElMessageBox
} from 'element-plus'
import {
  getSmsContacts,
  createSmsContact,
  updateSmsContact,
  deleteSmsContact,
  getSmsRecords,
  testSms,
  unwrapList
} from '@/api/modbus'

defineOptions({ name: 'Sms' })

const activeTab = ref('contacts')
const contacts = ref<any[]>([])
const records = ref<any[]>([])
const loading = ref(false)

const fetchContacts = async () => {
  loading.value = true
  try {
    contacts.value = unwrapList(await getSmsContacts()).list
  } finally {
    loading.value = false
  }
}
const fetchRecords = async () => {
  records.value = unwrapList(await getSmsRecords({ page: 1, page_size: 50 })).list
}

// 联系人表单
const dialogVisible = ref(false)
const dialogTitle = ref('新增联系人')
const formRef = ref()
const form = reactive<any>({ id: null, name: '', phone: '', enabled: true })
const rules = {
  name: [{ required: true, message: '请输入姓名', trigger: 'blur' }],
  phone: [{ required: true, message: '请输入手机号', trigger: 'blur' }]
}
const openCreate = () => {
  dialogTitle.value = '新增联系人'
  Object.assign(form, { id: null, name: '', phone: '', enabled: true })
  dialogVisible.value = true
}
const openEdit = (row: any) => {
  dialogTitle.value = '编辑联系人'
  Object.assign(form, {
    id: row.id,
    name: row.name,
    phone: row.phone,
    enabled: row.enabled !== false
  })
  dialogVisible.value = true
}
const submit = async () => {
  await formRef.value?.validate()
  const payload = { name: form.name, phone: form.phone, enabled: form.enabled }
  if (form.id) {
    await updateSmsContact(form.id, payload)
    ElMessage.success('更新成功')
  } else {
    await createSmsContact(payload)
    ElMessage.success('创建成功')
  }
  dialogVisible.value = false
  fetchContacts()
}
const remove = async (row: any) => {
  await ElMessageBox.confirm(`确认删除联系人「${row.name}」？`, '提示', { type: 'warning' })
  await deleteSmsContact(row.id)
  ElMessage.success('删除成功')
  fetchContacts()
}

// 测试发送
const testForm = reactive({ phone: '', content: '这是一条来自 Modbus 平台的测试短信' })
const testing = ref(false)
const doTest = async () => {
  if (!testForm.phone) {
    ElMessage.warning('请输入手机号')
    return
  }
  testing.value = true
  try {
    await testSms({ phone: testForm.phone, content: testForm.content })
    ElMessage.success('测试短信已发送（当前可能为 mock 模式）')
    fetchRecords()
  } catch (e: any) {
    ElMessage.error(e?.message || '发送失败')
  } finally {
    testing.value = false
  }
}

onMounted(() => {
  fetchContacts()
  fetchRecords()
})
</script>

<template>
  <ContentWrap title="短信管理">
    <ElTabs v-model="activeTab">
      <ElTabPane label="联系人" name="contacts">
        <div class="flex justify-end mb-12px">
          <ElButton v-hasPermi="['sms.write']" type="success" @click="openCreate"
            >新增联系人</ElButton
          >
        </div>
        <ElTable v-loading="loading" :data="contacts" border stripe>
          <ElTableColumn prop="id" label="ID" width="70" />
          <ElTableColumn prop="name" label="姓名" min-width="120" />
          <ElTableColumn prop="phone" label="手机号" min-width="140" />
          <ElTableColumn label="启用" width="90">
            <template #default="{ row }">
              <ElTag :type="row.enabled !== false ? 'success' : 'info'">{{
                row.enabled !== false ? '启用' : '停用'
              }}</ElTag>
            </template>
          </ElTableColumn>
          <ElTableColumn label="操作" width="150" fixed="right">
            <template #default="{ row }">
              <ElButton v-hasPermi="['sms.write']" link type="primary" @click="openEdit(row)"
                >编辑</ElButton
              >
              <ElButton v-hasPermi="['sms.write']" link type="danger" @click="remove(row)"
                >删除</ElButton
              >
            </template>
          </ElTableColumn>
        </ElTable>
      </ElTabPane>

      <ElTabPane label="发送测试" name="test">
        <ElForm label-width="80px" class="max-w-500px">
          <ElFormItem label="手机号">
            <ElInput v-model="testForm.phone" placeholder="请输入接收手机号" />
          </ElFormItem>
          <ElFormItem label="内容">
            <ElInput v-model="testForm.content" type="textarea" :rows="3" />
          </ElFormItem>
          <ElFormItem>
            <ElButton v-hasPermi="['sms.send']" type="primary" :loading="testing" @click="doTest"
              >发送测试</ElButton
            >
          </ElFormItem>
        </ElForm>
      </ElTabPane>

      <ElTabPane label="发送记录" name="records">
        <ElTable :data="records" border stripe>
          <ElTableColumn prop="id" label="ID" width="70" />
          <ElTableColumn prop="phone" label="手机号" min-width="140" />
          <ElTableColumn prop="content" label="内容" min-width="240" show-overflow-tooltip />
          <ElTableColumn prop="status" label="状态" width="100" />
          <ElTableColumn prop="created_at" label="发送时间" width="170" />
        </ElTable>
      </ElTabPane>
    </ElTabs>

    <ElDialog v-model="dialogVisible" :title="dialogTitle" width="440px">
      <ElForm ref="formRef" :model="form" :rules="rules" label-width="80px">
        <ElFormItem label="姓名" prop="name">
          <ElInput v-model="form.name" />
        </ElFormItem>
        <ElFormItem label="手机号" prop="phone">
          <ElInput v-model="form.phone" />
        </ElFormItem>
        <ElFormItem label="启用">
          <ElSwitch v-model="form.enabled" />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="dialogVisible = false">取消</ElButton>
        <ElButton type="primary" @click="submit">确定</ElButton>
      </template>
    </ElDialog>
  </ContentWrap>
</template>
