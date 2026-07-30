<script setup lang="ts">
import { ref, reactive, computed, onMounted, watch } from 'vue'
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
  ElEmpty,
  ElPagination
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
import OrgCascadeSelect from '@/components/OrgCascadeSelect.vue'

defineOptions({ name: 'Tags' })

const devices = ref<any[]>([])
const currentDevice = ref<number | undefined>(undefined)
const loading = ref(false)
const list = ref<any[]>([])

// ── 分页 ──
const page = ref(1)
const pageSize = ref(100)
const total = ref(0)

// 当前选中设备的协议（决定点位表单显示哪些必填字段）
const currentProtocol = computed(() => {
  const d = devices.value.find((x) => x.id === currentDevice.value)
  return d?.protocol || 'modbus_tcp'
})
const isModbus = computed(() => ['modbus_tcp', 'modbus_rtu'].includes(currentProtocol.value))
const isMqtt = computed(() => currentProtocol.value === 'mqtt')
const isOpc = computed(() => currentProtocol.value === 'opc_ua')
// 回读寄存器下拉：从后端获取该设备全量点位（排除自身），避免分页导致选项不全
const allDeviceTags = ref<any[]>([])
const readbackOptions = computed(() => allDeviceTags.value.filter((t) => t.id !== form.id))
const fetchAllDeviceTags = async () => {
  if (!currentDevice.value) { allDeviceTags.value = []; return }
  try {
    const res = await getDeviceTags(currentDevice.value, { page: 1, page_size: 500 })
    const body = unwrap(res)
    allDeviceTags.value = Array.isArray(body) ? body : unwrapList(res).list
  } catch { allDeviceTags.value = [] }
}

// 当前设备的展示信息（用于工具栏与表格「归属设备」列）
const currentDeviceName = computed(() => {
  const d = devices.value.find((x) => x.id === currentDevice.value)
  return d?.name || '—'
})
const currentProtocolText = computed(() => {
  const map: Record<string, string> = {
    modbus_tcp: 'Modbus TCP',
    modbus_rtu: 'Modbus RTU',
    mqtt: 'MQTT',
    opc_ua: 'OPC-UA'
  }
  return map[currentProtocol.value] || currentProtocol.value
})

const fetchDevices = async () => {
  try {
    devices.value = unwrapList(await getAllDevices()).list
    if (devices.value.length && currentDevice.value == null) {
      currentDevice.value = devices.value[0].id
      page.value = 1
      fetchTags()
    }
  } catch (e: any) {
    ElMessage.error(e?.message || '获取设备列表失败')
  }
}
const fetchTags = async () => {
  if (currentDevice.value == null) return
  loading.value = true
  try {
    const res = await getDeviceTags(currentDevice.value, { page: page.value, page_size: pageSize.value })
    const body = unwrap(res)
    if (Array.isArray(body)) {
      list.value = body
      total.value = body.length
    } else {
      const parsed = unwrapList(res)
      list.value = parsed.list
      total.value = parsed.total
    }
    // 同时加载全量点位（用于回读寄存器下拉）
    fetchAllDeviceTags()
  } finally {
    loading.value = false
  }
}
const onPageChange = (p: number) => {
  page.value = p
  fetchTags()
}
const onSizeChange = (s: number) => {
  pageSize.value = s
  page.value = 1
  fetchTags()
}

const dialogVisible = ref(false)
const dialogTitle = ref('新增点位')
const formRef = ref()
const emptyForm = () => ({
  id: null,
  name: '',
  // Modbus
  function_code: '',
  address: 0,
  data_type: 'uint16',
  // MQTT
  mqtt_topic: '',
  mqtt_json_path: '',
  mqtt_value_type: 'float64',
  // OPC UA
  opc_node_id: '',
  opc_node_type: 'float64',
  // 通用
  unit: '',
  scale_factor: 1,
  writable: false,
  readback_tag_id: null
})
const form = reactive<any>(emptyForm())
const rules = computed(() => ({
  name: [{ required: true, message: '请输入点位名称', trigger: 'blur' }],
  ...(isModbus.value
    ? { function_code: [{ required: true, message: '请选择功能码', trigger: 'change' }] }
    : {}),
  ...(isMqtt.value
    ? { mqtt_topic: [{ required: true, message: '请输入订阅主题', trigger: 'blur' }] }
    : {}),
  ...(isOpc.value
    ? { opc_node_id: [{ required: true, message: '请输入节点ID', trigger: 'blur' }] }
    : {})
}))
const openCreate = () => {
  dialogTitle.value = '新增点位'
  Object.assign(form, emptyForm())
  dialogVisible.value = true
}
const openEdit = (row: any) => {
  dialogTitle.value = '编辑点位'
  Object.assign(form, emptyForm(), {
    id: row.id,
    name: row.name,
    function_code: row.function_code || '',
    address: row.address ?? 0,
    data_type: row.data_type || 'uint16',
    mqtt_topic: row.mqtt_topic || '',
    mqtt_json_path: row.mqtt_json_path || '',
    mqtt_value_type: row.mqtt_value_type || 'float64',
    opc_node_id: row.opc_node_id || '',
    opc_node_type: row.opc_node_type || 'float64',
    unit: row.unit || '',
    scale_factor: row.scale_factor ?? 1,
    writable: !!row.writable,
    readback_tag_id: row.readback_tag_id ?? null
  })
  dialogVisible.value = true
}
const submit = async () => {
  await formRef.value?.validate()
  const payload = { ...form, device_id: currentDevice.value }
  delete payload.id
  try {
    if (form.id) {
      await updateTag(form.id, payload)
      ElMessage.success('更新成功')
    } else {
      await createTag(payload)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    fetchTags()
  } catch (e: any) {
    const msg = e?.response?.data?.detail || e?.response?.data?.message || e?.message || '保存失败'
    ElMessage.error(msg)
  }
}
const remove = async (row: any) => {
  try {
    await ElMessageBox.confirm(`确认删除点位「${row.name}」？`, '提示', { type: 'warning' })
    await deleteTag(row.id)
    ElMessage.success('删除成功')
    fetchTags()
  } catch (e: any) {
    if (e !== 'cancel' && e?.message !== 'cancel') {
      ElMessage.error(e?.message || '删除失败')
    }
  }
}

// ── 导出/导入 ──
import { saveBlob } from '@/utils/modbus'

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
    saveBlob(res, `tags_${deviceName}_${new Date().toISOString().slice(0, 10)}.csv`)
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

const resetImportState = () => {
  importResult.value = null
  importLoading.value = false
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

// 组织架构级联筛选（与实时数据页一致）：选中设备即加载该设备点位
const selectedIds = ref<number[]>([])
const orgPath = ref<{ org_node_id: number | null; labels: string[] } | null>(null)
const onCascadeSearch = () => {
  if (selectedIds.value.length) {
    currentDevice.value = selectedIds.value[0]
    page.value = 1
    fetchTags()
  } else {
    ElMessage.info('请在级联中选择设备')
  }
}
// 级联直接选设备（不点搜索按钮）也联动加载该设备点位
watch(selectedIds, (ids) => {
  if (ids.length && ids[0] !== currentDevice.value) {
    currentDevice.value = ids[0]
    page.value = 1
    fetchTags()
  }
})

onMounted(fetchDevices)
</script>

<template>
  <ContentWrap title="采集点位">
    <!-- 组织架构级联筛选（与实时数据页一致） -->
    <div class="mb-16px">
      <OrgCascadeSelect v-model="selectedIds" v-model:path="orgPath" @search="onCascadeSearch" />
    </div>

    <!-- 操作工具栏：当前设备信息 + 导入/导出/新增点位（从右侧 header 移至此） -->
    <div class="flex items-center mb-12px flex-wrap gap-8px">
      <ElTag v-if="currentDevice != null" type="primary" effect="plain" size="small">
        当前设备：{{ currentDeviceName }}（{{ currentProtocolText }}）
      </ElTag>
      <span class="flex-grow" />
      <ElButton v-hasPermi="['import.write']" @click="openImport">导入点位</ElButton>
      <ElButton
        v-hasPermi="['export.download']"
        :loading="exportLoading"
        :disabled="currentDevice == null"
        @click="doExport"
      >
        导出点位
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

    <ElEmpty v-if="currentDevice == null" description="请在上方级联中选择设备" />
    <ElTable v-else v-loading="loading" :data="list" border stripe>
      <ElTableColumn prop="id" label="ID" width="70" />
      <ElTableColumn label="归属设备" min-width="150" show-overflow-tooltip>
        <template #default>{{ currentDeviceName }}</template>
      </ElTableColumn>
      <ElTableColumn prop="name" label="点位名称" min-width="150" show-overflow-tooltip />
      <template v-if="isModbus">
        <ElTableColumn prop="address" label="地址" width="90" />
        <ElTableColumn label="功能码" width="130">
          <template #default="{ row }">
            <ElTag v-if="row.function_code" size="small">{{
              (
                {
                  coil: '线圈 FC01',
                  discrete_input: '离散输入 FC02',
                  input_register: '输入寄存器 FC04',
                  holding_register: '保持寄存器 FC03'
                } as any
              )[row.function_code] || row.function_code
            }}</ElTag>
            <ElTag v-else type="danger" size="small">未设置</ElTag>
          </template>
        </ElTableColumn>
        <ElTableColumn prop="data_type" label="数据类型" width="110" />
      </template>
      <template v-else-if="isMqtt">
        <ElTableColumn prop="mqtt_topic" label="订阅主题" min-width="180" show-overflow-tooltip />
        <ElTableColumn prop="mqtt_json_path" label="JSON路径" width="130" show-overflow-tooltip />
      </template>
      <template v-else-if="isOpc">
        <ElTableColumn prop="opc_node_id" label="节点ID" min-width="180" show-overflow-tooltip />
        <ElTableColumn prop="opc_node_type" label="节点类型" width="110" />
      </template>
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
    <div v-if="currentDevice != null" class="flex justify-end mt-12px">
      <ElPagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        layout="total, sizes, prev, pager, next, jumper"
        :page-sizes="[10, 20, 50, 100]"
        @current-change="onPageChange"
        @size-change="onSizeChange"
      />
    </div>

    <ElDialog v-model="dialogVisible" :title="dialogTitle" width="500px" @close="formRef?.resetFields()">
      <ElForm ref="formRef" :model="form" :rules="rules" label-width="90px">
        <ElFormItem label="点位名称" prop="name">
          <ElInput v-model="form.name" placeholder="请输入点位名称" />
        </ElFormItem>
        <!-- Modbus 专属：功能码必选 -->
        <template v-if="isModbus">
          <ElFormItem label="功能码" prop="function_code">
            <ElSelect v-model="form.function_code" class="w-full" placeholder="请选择功能码（必选）">
              <ElOption label="保持寄存器 Holding (FC03/06)" value="holding_register" />
              <ElOption label="输入寄存器 Input (FC04)" value="input_register" />
              <ElOption label="线圈 Coil (FC01/05)" value="coil" />
              <ElOption label="离散输入 Discrete (FC02)" value="discrete_input" />
            </ElSelect>
          </ElFormItem>
          <ElFormItem label="地址">
            <ElInputNumber v-model="form.address" :min="0" :controls="false" class="!w-full" />
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
        </template>
        <!-- MQTT 专属：订阅主题必填 -->
        <template v-else-if="isMqtt">
          <ElFormItem label="订阅主题" prop="mqtt_topic">
            <ElInput v-model="form.mqtt_topic" placeholder="如 factory/line1/temp（必填）" />
          </ElFormItem>
          <ElFormItem label="JSON路径">
            <ElInput v-model="form.mqtt_json_path" placeholder="如 data.temperature（留空取整个消息体）" />
          </ElFormItem>
          <ElFormItem label="值类型">
            <ElSelect v-model="form.mqtt_value_type" class="w-full">
              <ElOption label="float64" value="float64" />
              <ElOption label="int64" value="int64" />
              <ElOption label="bool" value="bool" />
              <ElOption label="string" value="string" />
            </ElSelect>
          </ElFormItem>
        </template>
        <!-- OPC UA 专属：节点ID必填 -->
        <template v-else-if="isOpc">
          <ElFormItem label="节点ID" prop="opc_node_id">
            <ElInput v-model="form.opc_node_id" placeholder="如 ns=2;s=Temperature 或 i=1001（必填）" />
          </ElFormItem>
          <ElFormItem label="节点类型">
            <ElSelect v-model="form.opc_node_type" class="w-full">
              <ElOption label="float64" value="float64" />
              <ElOption label="int64" value="int64" />
              <ElOption label="bool" value="bool" />
              <ElOption label="string" value="string" />
            </ElSelect>
          </ElFormItem>
        </template>
        <ElFormItem label="单位">
          <ElInput v-model="form.unit" placeholder="如 ℃ / kPa" />
        </ElFormItem>
        <ElFormItem label="缩放系数">
          <ElInputNumber v-model="form.scale_factor" :step="0.1" :controls="false" class="!w-full" />
        </ElFormItem>
        <ElFormItem label="可写">
          <ElSwitch v-model="form.writable" />
        </ElFormItem>
        <ElFormItem label="回读寄存器">
          <ElSelect
            v-model="form.readback_tag_id"
            class="w-full"
            clearable
            placeholder="绑定写操作后回读的寄存器（可选）"
          >
            <ElOption
              v-for="t in readbackOptions"
              :key="t.id"
              :label="`${t.name}（${t.address ?? '—'}）${t.writable ? ' · 可写' : ''}`"
              :value="t.id"
            />
          </ElSelect>
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="dialogVisible = false">取消</ElButton>
        <ElButton type="primary" @click="submit">确定</ElButton>
      </template>
    </ElDialog>

    <!-- 导入点位对话框 -->
    <ElDialog v-model="importDialogVisible" title="导入点位" width="500px" @close="resetImportState">
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
