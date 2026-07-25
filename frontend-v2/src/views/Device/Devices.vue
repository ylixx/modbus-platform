<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ContentWrap } from '@/components/ContentWrap'
import {
  ElButton,
  ElTable,
  ElTableColumn,
  ElTag,
  ElInput,
  ElPagination,
  ElDialog,
  ElForm,
  ElFormItem,
  ElSelect,
  ElOption,
  ElInputNumber,
  ElMessage,
  ElMessageBox
} from 'element-plus'
import {
  getDevices,
  createDevice,
  updateDevice,
  deleteDevice,
  getGroups,
  unwrapList
} from '@/api/modbus'

defineOptions({ name: 'Devices' })

const router = useRouter()
const loading = ref(false)
const list = ref<any[]>([])
const total = ref(0)
const query = reactive({ page: 1, page_size: 10, keyword: '' })
const groups = ref<any[]>([])

const statusType = (s?: string) => {
  if (s === 'online') return 'success'
  if (s === 'error') return 'danger'
  return 'info'
}
const statusText = (s?: string) => {
  if (s === 'online') return '在线'
  if (s === 'error') return '异常'
  return '离线'
}

const fetchList = async () => {
  loading.value = true
  try {
    const res = await getDevices({
      page: query.page,
      page_size: query.page_size,
      keyword: query.keyword || undefined
    })
    const { list: l, total: t } = unwrapList(res)
    list.value = l
    total.value = t
  } finally {
    loading.value = false
  }
}

const fetchGroups = async () => {
  const res = await getGroups()
  groups.value = unwrapList(res).list
}

// ------- 表单 -------
const dialogVisible = ref(false)
const dialogTitle = ref('新增设备')
const formRef = ref()
const form = reactive<any>({
  id: null,
  name: '',
  protocol: 'modbus_tcp',
  host: '',
  port: 502,
  slave_id: 1,
  group_id: null,
  description: ''
})
const rules = {
  name: [{ required: true, message: '请输入设备名称', trigger: 'blur' }],
  protocol: [{ required: true, message: '请选择协议', trigger: 'change' }]
}

const openCreate = () => {
  dialogTitle.value = '新增设备'
  Object.assign(form, {
    id: null,
    name: '',
    protocol: 'modbus_tcp',
    host: '',
    port: 502,
    slave_id: 1,
    group_id: null,
    description: ''
  })
  dialogVisible.value = true
}
const openEdit = (row: any) => {
  dialogTitle.value = '编辑设备'
  Object.assign(form, {
    id: row.id,
    name: row.name,
    protocol: row.protocol || 'modbus_tcp',
    host: row.host || '',
    port: row.port ?? 502,
    slave_id: row.slave_id ?? 1,
    group_id: row.group_id ?? null,
    description: row.description || ''
  })
  dialogVisible.value = true
}
const submit = async () => {
  await formRef.value?.validate()
  const payload = { ...form }
  delete payload.id
  if (form.id) {
    await updateDevice(form.id, payload)
    ElMessage.success('更新成功')
  } else {
    await createDevice(payload)
    ElMessage.success('创建成功')
  }
  dialogVisible.value = false
  fetchList()
}
const remove = async (row: any) => {
  await ElMessageBox.confirm(`确认删除设备「${row.name}」？`, '提示', { type: 'warning' })
  await deleteDevice(row.id)
  ElMessage.success('删除成功')
  fetchList()
}

onMounted(() => {
  fetchList()
  fetchGroups()
})
</script>

<template>
  <ContentWrap title="设备管理">
    <template #header>
      <div class="flex-grow flex justify-end">
        <ElInput
          v-model="query.keyword"
          placeholder="搜索设备名称"
          clearable
          class="!w-200px mr-10px"
          @keyup.enter="((query.page = 1), fetchList())"
        />
        <ElButton type="primary" @click="((query.page = 1), fetchList())">查询</ElButton>
        <ElButton v-hasPermi="['device.write']" type="success" @click="openCreate"
          >新增设备</ElButton
        >
      </div>
    </template>

    <ElTable v-loading="loading" :data="list" border stripe>
      <ElTableColumn prop="id" label="ID" width="70" />
      <ElTableColumn prop="name" label="设备名称" min-width="160" show-overflow-tooltip />
      <ElTableColumn prop="protocol" label="协议" width="120" />
      <ElTableColumn label="连接" min-width="160">
        <template #default="{ row }">{{ row.host }}:{{ row.port }} / #{{ row.slave_id }}</template>
      </ElTableColumn>
      <ElTableColumn label="状态" width="90">
        <template #default="{ row }">
          <ElTag :type="statusType(row.status)">{{ statusText(row.status) }}</ElTag>
        </template>
      </ElTableColumn>
      <ElTableColumn prop="description" label="描述" min-width="160" show-overflow-tooltip />
      <ElTableColumn label="操作" width="220" fixed="right">
        <template #default="{ row }">
          <ElButton link type="primary" @click="router.push(`/device/detail/${row.id}`)"
            >详情</ElButton
          >
          <ElButton v-hasPermi="['device.write']" link type="primary" @click="openEdit(row)"
            >编辑</ElButton
          >
          <ElButton v-hasPermi="['device.write']" link type="danger" @click="remove(row)"
            >删除</ElButton
          >
        </template>
      </ElTableColumn>
    </ElTable>

    <div class="flex justify-end mt-16px">
      <ElPagination
        v-model:current-page="query.page"
        v-model:page-size="query.page_size"
        :total="total"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next"
        @current-change="fetchList"
        @size-change="((query.page = 1), fetchList())"
      />
    </div>

    <ElDialog v-model="dialogVisible" :title="dialogTitle" width="520px">
      <ElForm ref="formRef" :model="form" :rules="rules" label-width="90px">
        <ElFormItem label="设备名称" prop="name">
          <ElInput v-model="form.name" placeholder="请输入设备名称" />
        </ElFormItem>
        <ElFormItem label="协议" prop="protocol">
          <ElSelect v-model="form.protocol" class="w-full">
            <ElOption label="Modbus TCP" value="modbus_tcp" />
            <ElOption label="Modbus RTU" value="modbus_rtu" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="主机地址">
          <ElInput v-model="form.host" placeholder="192.168.1.100" />
        </ElFormItem>
        <ElFormItem label="端口">
          <ElInputNumber v-model="form.port" :min="1" :max="65535" />
        </ElFormItem>
        <ElFormItem label="从站地址">
          <ElInputNumber v-model="form.slave_id" :min="0" :max="255" />
        </ElFormItem>
        <ElFormItem label="设备分组">
          <ElSelect v-model="form.group_id" clearable class="w-full" placeholder="不分组">
            <ElOption v-for="g in groups" :key="g.id" :label="g.name" :value="g.id" />
          </ElSelect>
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
