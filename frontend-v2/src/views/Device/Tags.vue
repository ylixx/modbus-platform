<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ContentWrap } from '@/components/ContentWrap'
import {
  ElButton,
  ElTable,
  ElTableColumn,
  ElSelect,
  ElOption,
  ElTag,
  ElDialog,
  ElForm,
  ElFormItem,
  ElInput,
  ElInputNumber,
  ElSwitch,
  ElMessage,
  ElMessageBox,
  ElEmpty
} from 'element-plus'
import {
  getAllDevices,
  getDeviceTags,
  createTag,
  updateTag,
  deleteTag,
  unwrap,
  unwrapList
} from '@/api/modbus'

defineOptions({ name: 'Tags' })

const devices = ref<any[]>([])
const currentDevice = ref<number | undefined>(undefined)
const loading = ref(false)
const list = ref<any[]>([])

const fetchDevices = async () => {
  devices.value = unwrapList(await getAllDevices()).list
  if (devices.value.length && currentDevice.value == null) {
    currentDevice.value = devices.value[0].id
    fetchTags()
  }
}
const fetchTags = async () => {
  if (currentDevice.value == null) return
  loading.value = true
  try {
    const res = await getDeviceTags(currentDevice.value)
    const body = unwrap(res)
    list.value = Array.isArray(body) ? body : unwrapList(res).list
  } finally {
    loading.value = false
  }
}

const dialogVisible = ref(false)
const dialogTitle = ref('新增点位')
const formRef = ref()
const form = reactive<any>({
  id: null,
  name: '',
  address: 0,
  data_type: 'int16',
  register_type: 'holding',
  unit: '',
  scale: 1,
  writable: false
})
const rules = {
  name: [{ required: true, message: '请输入点位名称', trigger: 'blur' }]
}
const openCreate = () => {
  dialogTitle.value = '新增点位'
  Object.assign(form, {
    id: null,
    name: '',
    address: 0,
    data_type: 'int16',
    register_type: 'holding',
    unit: '',
    scale: 1,
    writable: false
  })
  dialogVisible.value = true
}
const openEdit = (row: any) => {
  dialogTitle.value = '编辑点位'
  Object.assign(form, {
    id: row.id,
    name: row.name,
    address: row.address ?? 0,
    data_type: row.data_type || 'int16',
    register_type: row.register_type || 'holding',
    unit: row.unit || '',
    scale: row.scale ?? 1,
    writable: !!row.writable
  })
  dialogVisible.value = true
}
const submit = async () => {
  await formRef.value?.validate()
  const payload = { ...form, device_id: currentDevice.value }
  delete payload.id
  if (form.id) {
    await updateTag(form.id, payload)
    ElMessage.success('更新成功')
  } else {
    await createTag(payload)
    ElMessage.success('创建成功')
  }
  dialogVisible.value = false
  fetchTags()
}
const remove = async (row: any) => {
  await ElMessageBox.confirm(`确认删除点位「${row.name}」？`, '提示', { type: 'warning' })
  await deleteTag(row.id)
  ElMessage.success('删除成功')
  fetchTags()
}

onMounted(fetchDevices)
</script>

<template>
  <ContentWrap title="采集点位">
    <template #header>
      <div class="flex-grow flex justify-end items-center">
        <span class="text-14px text-gray-500 mr-8px">设备：</span>
        <ElSelect v-model="currentDevice" class="!w-220px mr-10px" @change="fetchTags">
          <ElOption v-for="d in devices" :key="d.id" :label="d.name" :value="d.id" />
        </ElSelect>
        <ElButton
          v-hasPermi="['tag.write']"
          type="success"
          :disabled="currentDevice == null"
          @click="openCreate"
        >
          新增点位
        </ElButton>
      </div>
    </template>

    <ElEmpty v-if="currentDevice == null" description="请先选择设备" />
    <ElTable v-else v-loading="loading" :data="list" border stripe>
      <ElTableColumn prop="id" label="ID" width="70" />
      <ElTableColumn prop="name" label="点位名称" min-width="150" show-overflow-tooltip />
      <ElTableColumn prop="address" label="地址" width="90" />
      <ElTableColumn prop="register_type" label="寄存器" width="110" />
      <ElTableColumn prop="data_type" label="数据类型" width="110" />
      <ElTableColumn label="当前值" width="110">
        <template #default="{ row }">{{ row.value ?? '—' }}{{ row.unit || '' }}</template>
      </ElTableColumn>
      <ElTableColumn label="可写" width="80">
        <template #default="{ row }">
          <ElTag :type="row.writable ? 'success' : 'info'">{{ row.writable ? '是' : '否' }}</ElTag>
        </template>
      </ElTableColumn>
      <ElTableColumn label="操作" width="150" fixed="right">
        <template #default="{ row }">
          <ElButton v-hasPermi="['tag.write']" link type="primary" @click="openEdit(row)"
            >编辑</ElButton
          >
          <ElButton v-hasPermi="['tag.write']" link type="danger" @click="remove(row)"
            >删除</ElButton
          >
        </template>
      </ElTableColumn>
    </ElTable>

    <ElDialog v-model="dialogVisible" :title="dialogTitle" width="500px">
      <ElForm ref="formRef" :model="form" :rules="rules" label-width="90px">
        <ElFormItem label="点位名称" prop="name">
          <ElInput v-model="form.name" />
        </ElFormItem>
        <ElFormItem label="地址">
          <ElInputNumber v-model="form.address" :min="0" />
        </ElFormItem>
        <ElFormItem label="寄存器">
          <ElSelect v-model="form.register_type" class="w-full">
            <ElOption label="保持寄存器 holding" value="holding" />
            <ElOption label="输入寄存器 input" value="input" />
            <ElOption label="线圈 coil" value="coil" />
            <ElOption label="离散输入 discrete" value="discrete" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="数据类型">
          <ElSelect v-model="form.data_type" class="w-full">
            <ElOption label="int16" value="int16" />
            <ElOption label="uint16" value="uint16" />
            <ElOption label="int32" value="int32" />
            <ElOption label="uint32" value="uint32" />
            <ElOption label="float32" value="float32" />
            <ElOption label="bool" value="bool" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="单位">
          <ElInput v-model="form.unit" placeholder="如 ℃ / kPa" />
        </ElFormItem>
        <ElFormItem label="缩放系数">
          <ElInputNumber v-model="form.scale" :step="0.1" />
        </ElFormItem>
        <ElFormItem label="可写">
          <ElSwitch v-model="form.writable" />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="dialogVisible = false">取消</ElButton>
        <ElButton type="primary" @click="submit">确定</ElButton>
      </template>
    </ElDialog>
  </ContentWrap>
</template>
