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
  ElInputNumber,
  ElSwitch,
  ElMessage,
  ElMessageBox,
  ElPagination,
  ElEmpty
} from 'element-plus'
import {
  getSmsContacts,
  createSmsContact,
  updateSmsContact,
  deleteSmsContact,
  getSmsRecords,
  getSmsRules,
  createSmsRule,
  updateSmsRule,
  deleteSmsRule,
  testSms,
  unwrapList
} from '@/api/modbus'
import { formatTime } from '@/utils/modbus'

defineOptions({ name: 'Sms' })

const activeTab = ref('contacts')
const contacts = ref<any[]>([])
const records = ref<any[]>([])
const loading = ref(false)

// ── 记录分页 ──
const recordsPage = ref(1)
const recordsPageSize = ref(20)
const recordsTotal = ref(0)

const fetchContacts = async () => {
  loading.value = true
  try {
    contacts.value = unwrapList(await getSmsContacts()).list
  } finally {
    loading.value = false
  }
}
const recordsLoading = ref(false)

const fetchRecords = async () => {
  recordsLoading.value = true
  try {
    const res = unwrapList(await getSmsRecords({ page: recordsPage.value, page_size: recordsPageSize.value }))
    records.value = res.list
    recordsTotal.value = res.total
  } catch (e: any) {
    ElMessage.error(e?.message || '获取发送记录失败')
  } finally {
    recordsLoading.value = false
  }
}
const onRecordsPageChange = (p: number) => {
  recordsPage.value = p
  fetchRecords()
}
const onRecordsSizeChange = (s: number) => {
  recordsPageSize.value = s
  recordsPage.value = 1
  fetchRecords()
}

// 联系人表单
const dialogVisible = ref(false)
const dialogTitle = ref('新增联系人')
const formRef = ref()
const form = reactive<any>({ id: null, name: '', phone: '', enabled: true })
const rules = {
  name: [{ required: true, message: '请输入姓名', trigger: 'blur' }],
  phone: [
    { required: true, message: '请输入手机号', trigger: 'blur' },
    { pattern: /^1[3-9]\d{9}$/, message: '请输入正确的手机号', trigger: 'blur' }
  ]
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
  try {
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
  } catch (e: any) {
    ElMessage.error(e?.message || '操作失败')
  }
}
const remove = async (row: any) => {
  try {
    await ElMessageBox.confirm(`确认删除联系人「${row.name}」？`, '提示', { type: 'warning' })
    await deleteSmsContact(row.id)
    ElMessage.success('删除成功')
    fetchContacts()
  } catch (e: any) {
    if (e !== 'cancel' && e?.message !== 'cancel') {
      ElMessage.error(e?.message || '删除失败')
    }
  }
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

const maskPhone = (phone?: string) => {
  if (!phone || phone.length < 7) return phone || '\u2014'
  return phone.slice(0, 3) + '****' + phone.slice(-4)
}

// ── 推送规则 ──
const pushRules = ref<any[]>([])
const pushLoading = ref(false)
const fetchPushRules = async () => {
  pushLoading.value = true
  try {
    pushRules.value = unwrapList(await getSmsRules()).list
  } finally {
    pushLoading.value = false
  }
}
const pushDialogVisible = ref(false)
const pushDialogTitle = ref('新增推送规则')
const pushFormRef = ref()
const pushForm = reactive<any>({
  id: null, name: '', alarm_levels: '[]', device_ids: '[]',
  contact_ids: '[]', time_start: '00:00', time_end: '23:59',
  cooldown_minutes: 30, enabled: true
})
const pushRules_rules = {
  name: [{ required: true, message: '请输入规则名称', trigger: 'blur' }]
}
const openPushCreate = () => {
  pushDialogTitle.value = '新增推送规则'
  Object.assign(pushForm, {
    id: null, name: '', alarm_levels: '[]', device_ids: '[]',
    contact_ids: '[]', time_start: '00:00', time_end: '23:59',
    cooldown_minutes: 30, enabled: true
  })
  pushDialogVisible.value = true
}
const openPushEdit = (row: any) => {
  pushDialogTitle.value = '编辑推送规则'
  Object.assign(pushForm, {
    id: row.id, name: row.name,
    alarm_levels: row.alarm_levels || '[]',
    device_ids: row.device_ids || '[]',
    contact_ids: row.contact_ids || '[]',
    time_start: row.time_start || '00:00',
    time_end: row.time_end || '23:59',
    cooldown_minutes: row.cooldown_minutes ?? 30,
    enabled: row.enabled !== false
  })
  pushDialogVisible.value = true
}
const submitPush = async () => {
  try {
    await pushFormRef.value?.validate()
    const payload = { ...pushForm }
    delete payload.id
    if (pushForm.id) {
      await updateSmsRule(pushForm.id, payload)
      ElMessage.success('更新成功')
    } else {
      await createSmsRule(payload)
      ElMessage.success('创建成功')
    }
    pushDialogVisible.value = false
    fetchPushRules()
  } catch (e: any) {
    ElMessage.error(e?.message || '操作失败')
  }
}
const removePush = async (row: any) => {
  try {
    await ElMessageBox.confirm(`确认删除推送规则「${row.name}」？`, '提示', { type: 'warning' })
    await deleteSmsRule(row.id)
    ElMessage.success('删除成功')
    fetchPushRules()
  } catch (e: any) {
    if (e !== 'cancel' && e?.message !== 'cancel') {
      ElMessage.error(e?.message || '删除失败')
    }
  }
}

onMounted(() => {
  fetchContacts()
  fetchRecords()
  fetchPushRules()
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
          <template #empty><ElEmpty description="暂无数据" :image-size="80" /></template>
          <ElTableColumn prop="id" label="ID" width="70" />
          <ElTableColumn prop="name" label="姓名" min-width="120" />
          <ElTableColumn label="手机号" min-width="140">
            <template #default="{ row }">{{ maskPhone(row.phone) }}</template>
          </ElTableColumn>
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

      <ElTabPane label="推送规则" name="rules">
        <div class="flex justify-end mb-12px">
          <ElButton v-hasPermi="['sms.write']" type="success" @click="openPushCreate"
            >新增推送规则</ElButton
          >
        </div>
        <ElTable v-loading="pushLoading" :data="pushRules" border stripe>
          <template #empty><ElEmpty description="暂无数据" :image-size="80" /></template>
          <ElTableColumn prop="id" label="ID" width="70" />
          <ElTableColumn prop="name" label="规则名称" min-width="140" show-overflow-tooltip />
          <ElTableColumn label="时间窗口" min-width="120">
            <template #default="{ row }">{{ row.time_start || '00:00' }} ~ {{ row.time_end || '23:59' }}</template>
          </ElTableColumn>
          <ElTableColumn label="冷却(分)" width="100">
            <template #default="{ row }">{{ row.cooldown_minutes ?? 30 }}</template>
          </ElTableColumn>
          <ElTableColumn label="启用" width="90">
            <template #default="{ row }">
              <ElTag :type="row.enabled !== false ? 'success' : 'info'">{{
                row.enabled !== false ? '启用' : '停用'
              }}</ElTag>
            </template>
          </ElTableColumn>
          <ElTableColumn label="操作" width="150" fixed="right">
            <template #default="{ row }">
              <ElButton v-hasPermi="['sms.write']" link type="primary" @click="openPushEdit(row)">编辑</ElButton>
              <ElButton v-hasPermi="['sms.write']" link type="danger" @click="removePush(row)">删除</ElButton>
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
        <ElTable v-loading="recordsLoading" :data="records" border stripe>
          <template #empty><ElEmpty description="暂无数据" :image-size="80" /></template>
          <ElTableColumn prop="id" label="ID" width="70" />
          <ElTableColumn label="手机号" min-width="140">
            <template #default="{ row }">{{ maskPhone(row.phone) }}</template>
          </ElTableColumn>
          <ElTableColumn prop="content" label="内容" min-width="240" show-overflow-tooltip />
          <ElTableColumn prop="status" label="状态" width="100" />
          <ElTableColumn label="发送时间" width="170">
            <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
          </ElTableColumn>
        </ElTable>
        <div class="flex justify-end mt-12px">
          <ElPagination
            v-model:current-page="recordsPage"
            v-model:page-size="recordsPageSize"
            :total="recordsTotal"
            layout="total, sizes, prev, pager, next, jumper"
            :page-sizes="[10, 20, 50, 100]"
            @current-change="onRecordsPageChange"
            @size-change="onRecordsSizeChange"
          />
        </div>
      </ElTabPane>
    </ElTabs>

    <ElDialog v-model="dialogVisible" :title="dialogTitle" width="440px" @close="formRef?.resetFields()">
      <ElForm ref="formRef" :model="form" :rules="rules" label-width="80px">
        <ElFormItem label="姓名" prop="name">
          <ElInput v-model="form.name" placeholder="请输入联系人名称" />
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

    <ElDialog v-model="pushDialogVisible" :title="pushDialogTitle" width="560px" @close="pushFormRef?.resetFields()">
      <ElForm ref="pushFormRef" :model="pushForm" :rules="pushRules_rules" label-width="100px">
        <ElFormItem label="规则名称" prop="name">
          <ElInput v-model="pushForm.name" placeholder="如：紧急报警推送规则" />
        </ElFormItem>
        <ElFormItem label="时间窗口">
          <div class="flex items-center gap-8px">
            <ElInput v-model="pushForm.time_start" placeholder="00:00" class="!w-100px" />
            <span>~</span>
            <ElInput v-model="pushForm.time_end" placeholder="23:59" class="!w-100px" />
          </div>
          <div class="text-12px text-gray-400 mt-4px">格式 HH:MM，如 22:00 ~ 06:00 表示夜间时段</div>
        </ElFormItem>
        <ElFormItem label="冷却时间">
          <ElInputNumber v-model="pushForm.cooldown_minutes" :min="1" :max="1440" />
          <span class="ml-8px text-gray-400">分钟</span>
        </ElFormItem>
        <ElFormItem label="启用">
          <ElSwitch v-model="pushForm.enabled" />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="pushDialogVisible = false">取消</ElButton>
        <ElButton type="primary" @click="submitPush">确定</ElButton>
      </template>
    </ElDialog>
  </ContentWrap>
</template>
