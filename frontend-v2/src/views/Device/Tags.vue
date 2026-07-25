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
  exportTagsCsv,
  importTags,
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

// ── 导出/导入 ──
const downloadBlob = (data: any, filename: string) => {
  const blob = data instanceof Blob ? data : new Blob([data])
  const url = window.URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  window.URL.revokeObjectURL(url)
}

const exportLoading = ref(false)
const doExport = async () => {
  if (!currentDevice.value) {
    ElMessage.warning('请先选择设备')
    return
  }
  exportLoading.value = true
  try {
    const res: any = await exportTagsCsv(currentDevice.value)
    const deviceName = devices.value.find((d) => d.id === currentDevice.value)?.name || 'device'
    downloadBlob(res?.data ?? res, `tags_${deviceName}_${new Date().toISOString().slice(0, 10)}.csv`)
    ElMessage.success('导出成功')
  } catch (e: any) {
    ElMessage.error(e?.message || '导出失败')
  } finally {
    exportLoading.value = false
  }
}

const importDialogVisible = ref(false)
const importLoading = ref(false)
const importResult = ref<any>(null)

const openImport = () => {
  importResult.value = null
  importDialogVisible.value = true
}

const doImport = async (opt: any) => {
  importLoading.value = true
  importResult.value = null
  try {
    const fd = new FormData()
    fd.append('file', opt.file)
    const res: any = await importTags(fd)
    const body = res?.data || res
    importResult.value = body
    ElMessage.success(`导入完成：成功 ${body?.created ?? 0} 条`)
    fetchTags()
    opt.onSuccess?.(body)
  } catch (e: any) {
    ElMessage.error(e?.message || '导入失败')
    opt.onError?.(e)
  } finally {
    importLoading.value = false
  }
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
          v-hasPermi="['export.download']"
          :loading="exportLoading"
          :disabled="currentDevice == null"
          @click="doExport"
        >
          导出点位
        </ElButton>
        <ElButton
          v-hasPermi="['import.write']"
          @click="openImport"
        >
          导入点位
        </ElButton>
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

    <!-- 导入点位对话框 -->
    <ElDialog v-model="importDialogVisible" title="导入点位" width="500px">
      <ElAlert
        title="导入说明"
        type="info"
        :closable="false"
        class="mb-16px"
      >
        <template #default>
          <div>
            <p>1. 先从已有设备「导出点位」获取 CSV 文件</p>
            <p>2. 修改 CSV 中的 device_name 为目标设备名称</p>
            <p>3. 按需修改点位名称、地址等信息</p>
            <p>4. 上传修改后的 CSV 文件</p>
          </div>
        </template>
      </ElAlert>
      <ElUpload
        :show-file-list="true"
        accept=".csv"
        :http-request="doImport"
        :loading="importLoading"
      >
        <ElButton type="primary" :loading="importLoading">选择 CSV 文件</ElButton>
        <template #tip>
          <div class="text-12px text-gray-400 mt-4px">
            CSV 格式: device_name, name, function_code, address, data_type, ...
          </div>
        </template>
      </ElUpload>
      <div v-if="importResult" class="mt-12px">
        <ElAlert
          :title="`导入完成：成功 ${importResult.created} 条`"
          :type="importResult.errors?.length ? 'warning' : 'success'"
          :closable="false"
        />
        <div v-if="importResult.errors?.length" class="mt-8px text-12px text-red-500">
          <div v-for="(err, i) in importResult.errors" :key="i">{{ err }}</div>
        </div>
      </div>
      <template #footer>
        <ElButton @click="importDialogVisible = false">关闭</ElButton>
      </template>
    </ElDialog>
  </ContentWrap>
</template>
