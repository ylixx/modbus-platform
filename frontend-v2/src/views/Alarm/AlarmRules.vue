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
  ElInputNumber,
  ElSwitch,
  ElMessage,
  ElMessageBox
} from 'element-plus'
import {
  getAlarmRules,
  createAlarmRule,
  updateAlarmRule,
  deleteAlarmRule,
  getAllDevices,
  unwrapList
} from '@/api/modbus'

defineOptions({ name: 'AlarmRules' })

const loading = ref(false)
const list = ref<any[]>([])
const devices = ref<any[]>([])

const fetchList = async () => {
  loading.value = true
  try {
    list.value = unwrapList(await getAlarmRules({ page: 1, page_size: 100 })).list
  } finally {
    loading.value = false
  }
}
const fetchDevices = async () => {
  devices.value = unwrapList(await getAllDevices()).list
}

const dialogVisible = ref(false)
const dialogTitle = ref('新增规则')
const formRef = ref()
const form = reactive<any>({
  id: null,
  name: '',
  device_id: null,
  condition: '>',
  threshold: 0,
  level: 'warning',
  enabled: true
})
const rules = { name: [{ required: true, message: '请输入规则名称', trigger: 'blur' }] }

const openCreate = () => {
  dialogTitle.value = '新增规则'
  Object.assign(form, {
    id: null,
    name: '',
    device_id: null,
    condition: '>',
    threshold: 0,
    level: 'warning',
    enabled: true
  })
  dialogVisible.value = true
}
const openEdit = (row: any) => {
  dialogTitle.value = '编辑规则'
  Object.assign(form, {
    id: row.id,
    name: row.name,
    device_id: row.device_id ?? null,
    condition: row.condition || '>',
    threshold: row.threshold ?? 0,
    level: row.level || 'warning',
    enabled: row.enabled !== false
  })
  dialogVisible.value = true
}
const submit = async () => {
  await formRef.value?.validate()
  const payload = { ...form }
  delete payload.id
  if (form.id) {
    await updateAlarmRule(form.id, payload)
    ElMessage.success('更新成功')
  } else {
    await createAlarmRule(payload)
    ElMessage.success('创建成功')
  }
  dialogVisible.value = false
  fetchList()
}
const remove = async (row: any) => {
  await ElMessageBox.confirm(`确认删除规则「${row.name}」？`, '提示', { type: 'warning' })
  await deleteAlarmRule(row.id)
  ElMessage.success('删除成功')
  fetchList()
}

onMounted(() => {
  fetchList()
  fetchDevices()
})
</script>

<template>
  <ContentWrap title="报警规则">
    <template #header>
      <div class="flex-grow flex justify-end">
        <ElButton v-hasPermi="['alarm.write']" type="success" @click="openCreate"
          >新增规则</ElButton
        >
      </div>
    </template>
    <ElTable v-loading="loading" :data="list" border stripe>
      <ElTableColumn prop="id" label="ID" width="70" />
      <ElTableColumn prop="name" label="规则名称" min-width="160" show-overflow-tooltip />
      <ElTableColumn label="条件" min-width="140">
        <template #default="{ row }">{{ row.condition }} {{ row.threshold }}</template>
      </ElTableColumn>
      <ElTableColumn label="级别" width="100">
        <template #default="{ row }"
          ><ElTag>{{ row.level || '—' }}</ElTag></template
        >
      </ElTableColumn>
      <ElTableColumn label="启用" width="90">
        <template #default="{ row }">
          <ElTag :type="row.enabled !== false ? 'success' : 'info'">{{
            row.enabled !== false ? '启用' : '停用'
          }}</ElTag>
        </template>
      </ElTableColumn>
      <ElTableColumn label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <ElButton v-hasPermi="['alarm.write']" link type="primary" @click="openEdit(row)"
            >编辑</ElButton
          >
          <ElButton v-hasPermi="['alarm.write']" link type="danger" @click="remove(row)"
            >删除</ElButton
          >
        </template>
      </ElTableColumn>
    </ElTable>

    <ElDialog v-model="dialogVisible" :title="dialogTitle" width="500px">
      <ElForm ref="formRef" :model="form" :rules="rules" label-width="90px">
        <ElFormItem label="规则名称" prop="name">
          <ElInput v-model="form.name" />
        </ElFormItem>
        <ElFormItem label="设备">
          <ElSelect v-model="form.device_id" clearable class="w-full" placeholder="全部设备">
            <ElOption v-for="d in devices" :key="d.id" :label="d.name" :value="d.id" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="条件">
          <ElSelect v-model="form.condition" class="!w-140px">
            <ElOption label="大于 >" value=">" />
            <ElOption label="大于等于 >=" value=">=" />
            <ElOption label="小于 <" value="<" />
            <ElOption label="小于等于 <=" value="<=" />
            <ElOption label="等于 ==" value="==" />
            <ElOption label="不等于 !=" value="!=" />
          </ElSelect>
          <ElInputNumber v-model="form.threshold" class="ml-10px" />
        </ElFormItem>
        <ElFormItem label="级别">
          <ElSelect v-model="form.level" class="w-full">
            <ElOption label="提示 info" value="info" />
            <ElOption label="警告 warning" value="warning" />
            <ElOption label="严重 critical" value="critical" />
          </ElSelect>
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
