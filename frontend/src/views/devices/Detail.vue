<template>
  <div>
    <div class="page-header">
      <el-button text @click="$router.push('/devices')"><el-icon><ArrowLeft /></el-icon> 返回</el-button>
      <h2>设备详情: {{ device?.name }}
        <el-tag :type="protoTagType(device?.protocol)" size="small" style="margin-left: 8px">{{ protoLabel(device?.protocol) }}</el-tag>
      </h2>
    </div>

    <!-- Device Info -->
    <el-card header="设备信息" style="margin-bottom: 16px">
      <el-descriptions :column="3" border>
        <el-descriptions-item label="状态">
          <span class="status-dot" :class="device?.status"></span>{{ statusLabel(device?.status) }}
        </el-descriptions-item>
        <el-descriptions-item label="协议">{{ protoLabel(device?.protocol) }}</el-descriptions-item>
        <el-descriptions-item label="采集周期">{{ device?.poll_interval }}s</el-descriptions-item>
        <el-descriptions-item v-if="device?.protocol === 'modbus_tcp'" label="连接">{{ device?.host }}:{{ device?.port }}</el-descriptions-item>
        <el-descriptions-item v-if="device?.protocol === 'modbus_tcp'" label="从站ID">{{ device?.slave_id }}</el-descriptions-item>
        <el-descriptions-item v-if="device?.protocol === 'mqtt'" label="Broker">{{ device?.mqtt_broker }}:{{ device?.mqtt_port }}</el-descriptions-item>
        <el-descriptions-item v-if="device?.protocol === 'mqtt'" label="Topic前缀">{{ device?.mqtt_topic_prefix }}</el-descriptions-item>
        <el-descriptions-item v-if="device?.protocol === 'opc_ua'" label="Endpoint">{{ device?.opc_endpoint }}</el-descriptions-item>
        <el-descriptions-item v-if="device?.protocol === 'opc_ua'" label="命名空间">{{ device?.opc_namespace }}</el-descriptions-item>
        <el-descriptions-item label="最后采集">{{ formatTime(device?.last_poll_at) }}</el-descriptions-item>
        <el-descriptions-item label="错误信息" :span="2">{{ device?.last_error || '-' }}</el-descriptions-item>
        <el-descriptions-item label="厂级">{{ device?.factory || '-' }}</el-descriptions-item>
        <el-descriptions-item label="区级">{{ device?.workshop || '-' }}</el-descriptions-item>
        <el-descriptions-item label="班级">{{ device?.production_line || '-' }}</el-descriptions-item>
        <el-descriptions-item label="安装位置">{{ device?.installation || '-' }}</el-descriptions-item>
        <el-descriptions-item label="坐标" v-if="device?.longitude">{{ device?.longitude }}, {{ device?.latitude }}</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <!-- Live Values -->
    <el-card header="实时数据" style="margin-bottom: 16px">
      <el-button @click="fetchLive" size="small" style="margin-bottom: 12px"><el-icon><Refresh /></el-icon> 刷新</el-button>
      <el-table :data="liveData" stripe size="small">
        <el-table-column prop="tag_name" label="点位名称" width="160" />
        <el-table-column prop="value" label="当前值" width="120">
          <template #default="{ row }">
            <span :style="{ color: row.quality === 'good' ? '#52c41a' : '#f5222d', fontWeight: 'bold' }">{{ row.value }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="unit" label="单位" width="80" />
        <el-table-column prop="quality" label="质量" width="80">
          <template #default="{ row }">
            <el-tag :type="row.quality === 'good' ? 'success' : 'danger'" size="small">{{ row.quality }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="time" label="更新时间" />
      </el-table>
    </el-card>

    <!-- Tags -->
    <el-card>
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span>采集点位配置</span>
          <el-button type="primary" size="small" @click="showTagDialog()">新增点位</el-button>
        </div>
      </template>
      <el-table :data="pagedRows" stripe size="small">
        <el-table-column prop="name" label="名称" width="140" />
        <el-table-column label="数据源" width="220">
          <template #default="{ row }">
            <span v-if="device?.protocol === 'modbus_tcp'">{{ fcLabel(row.function_code) }} @ {{ row.address }}</span>
            <span v-else-if="device?.protocol === 'mqtt'">{{ row.mqtt_topic || device?.mqtt_topic_prefix + '/' + row.name }}</span>
            <span v-else>{{ row.opc_node_id }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="data_type" label="数据类型" width="100">
          <template #default="{ row }">
            {{ device?.protocol === 'mqtt' ? row.mqtt_value_type : device?.protocol === 'opc_ua' ? row.opc_node_type : row.data_type }}
          </template>
        </el-table-column>
        <el-table-column prop="scale_factor" label="系数" width="80" />
        <el-table-column prop="offset" label="偏移" width="80" />
        <el-table-column prop="unit" label="单位" width="80" />
        <el-table-column prop="writable" label="可写" width="70">
          <template #default="{ row }">{{ row.writable ? '是' : '否' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="150">
          <template #default="{ row }">
            <el-button size="small" @click="showTagDialog(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="deleteTag(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        style="margin-top:12px; display:flex; justify-content:flex-end"
        layout="total, sizes, prev, pager, next, jumper"
        :total="total"
        :page-size="pageSize"
        :current-page="currentPage"
        :page-sizes="[10, 20, 30, 50, 100]"
        @size-change="onSizeChange"
        @current-change="onPageChange"
      />
    </el-card>

    <!-- Tag Dialog -->
    <el-dialog v-model="tagDialogVisible" :title="editingTagId ? '编辑点位' : '新增点位'" width="640px">
      <el-form :model="tagForm" label-width="100px">
        <el-form-item label="名称" required><el-input v-model="tagForm.name" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="tagForm.description" /></el-form-item>
        <el-form-item label="单位"><el-input v-model="tagForm.unit" /></el-form-item>

        <!-- Modbus fields -->
        <template v-if="device?.protocol === 'modbus_tcp'">
          <el-form-item label="功能码" required>
            <el-select v-model="tagForm.function_code">
              <el-option label="Coil (FC01/05)" value="coil" />
              <el-option label="Discrete Input (FC02)" value="discrete_input" />
              <el-option label="Input Register (FC04)" value="input_register" />
              <el-option label="Holding Register (FC03/06)" value="holding_register" />
            </el-select>
          </el-form-item>
          <el-form-item label="地址" required><el-input-number v-model="tagForm.address" :min="0" /></el-form-item>
          <el-form-item label="数据类型">
            <el-select v-model="tagForm.data_type">
              <el-option label="BOOL" value="bool" /><el-option label="INT16" value="int16" />
              <el-option label="UINT16" value="uint16" /><el-option label="INT32" value="int32" />
              <el-option label="UINT32" value="uint32" /><el-option label="FLOAT32" value="float32" />
              <el-option label="FLOAT64" value="float64" /><el-option label="STRING" value="string" />
              <el-option label="BCD" value="bcd" />
            </el-select>
          </el-form-item>
          <el-form-item label="字节序">
            <el-select v-model="tagForm.byte_order">
              <el-option label="Big Endian (AB CD)" value="big_endian" />
              <el-option label="Little Endian (DC BA)" value="little_endian" />
              <el-option label="Big Endian Swap (BA DC)" value="big_endian_swap" />
              <el-option label="Little Endian Swap (CD AB)" value="little_endian_swap" />
            </el-select>
          </el-form-item>
          <el-form-item label="寄存器数"><el-input-number v-model="tagForm.register_count" :min="1" :max="100" /></el-form-item>
        </template>

        <!-- MQTT fields -->
        <template v-if="device?.protocol === 'mqtt'">
          <el-form-item label="订阅Topic">
            <el-input v-model="tagForm.mqtt_topic" :placeholder="'默认: ' + (device?.mqtt_topic_prefix || '') + '/' + (tagForm.name || 'tag_name')" />
          </el-form-item>
          <el-form-item label="JSON路径">
            <el-input v-model="tagForm.mqtt_json_path" placeholder="e.g. sensors.temperature" />
          </el-form-item>
          <el-form-item label="值类型">
            <el-select v-model="tagForm.mqtt_value_type">
              <el-option label="Float64" value="float64" /><el-option label="Float32" value="float32" />
              <el-option label="Int32" value="int32" /><el-option label="Int16" value="int16" />
              <el-option label="Bool" value="bool" /><el-option label="String" value="string" />
            </el-select>
          </el-form-item>
          <el-form-item label="发布Topic">
            <el-input v-model="tagForm.mqtt_publish_topic" placeholder="覆盖设备默认发布Topic" />
          </el-form-item>
          <el-form-item label="Retain">
            <el-switch v-model="tagForm.mqtt_retain" />
          </el-form-item>
        </template>

        <!-- OPC-UA fields -->
        <template v-if="device?.protocol === 'opc_ua'">
          <el-form-item label="Node ID" required>
            <el-input v-model="tagForm.opc_node_id" placeholder="ns=2;s=Temperature 或 i=1001" />
          </el-form-item>
          <el-form-item label="值类型">
            <el-select v-model="tagForm.opc_node_type">
              <el-option label="Float64" value="float64" /><el-option label="Float32" value="float32" />
              <el-option label="Int32" value="int32" /><el-option label="Int16" value="int16" />
              <el-option label="UInt16" value="uint16" /><el-option label="Bool" value="bool" />
              <el-option label="String" value="string" />
            </el-select>
          </el-form-item>
        </template>

        <!-- Common processing -->
        <el-divider content-position="left">值处理</el-divider>
        <el-form-item label="缩放系数"><el-input-number v-model="tagForm.scale_factor" :step="0.1" /></el-form-item>
        <el-form-item label="偏移量"><el-input-number v-model="tagForm.offset" :step="0.1" /></el-form-item>
        <el-form-item label="小数位"><el-input-number v-model="tagForm.decimal_places" :min="0" :max="10" /></el-form-item>
        <el-divider content-position="left">脚本算法（可选）</el-divider>
        <el-form-item label="处理脚本">
          <el-select v-model="tagForm.script_id" clearable placeholder="不使用脚本" style="width:100%">
            <el-option label="不使用" :value="null" />
            <el-option v-for="s in allScripts" :key="s.id" :label="s.name" :value="s.id">
              <span>{{ s.name }}</span>
              <span style="font-size:11px;color:#999;margin-left:8px">{{ s.description }}</span>
            </el-option>
          </el-select>
          <div style="font-size:12px;color:#999;margin-top:4px">对原始采集值进行公式计算、滤波、标定等处理</div>
        </el-form-item>

        <el-form-item label="可写"><el-switch v-model="tagForm.writable" /></el-form-item>
        <el-form-item label="启用"><el-switch v-model="tagForm.enabled" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="tagDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveTag">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../../api/request'
import dayjs from 'dayjs'
import { useClientPagination } from '../../composables/useClientPagination'

const route = useRoute()
const deviceId = route.params.id
const device = ref(null)
const tags = ref([])
const liveData = ref([])
const loading = ref(false)
const {
  pageSize, currentPage, total, pagedRows,
  onSizeChange, onPageChange, resetPage,
} = useClientPagination(tags)
const allScripts = ref([])
const tagDialogVisible = ref(false)
const editingTagId = ref(null)

const fcLabel = (fc) => ({
  coil: 'Coil (FC01)', discrete_input: 'Discrete Input (FC02)',
  input_register: 'Input Register (FC04)', holding_register: 'Holding Register (FC03)',
}[fc] || fc)
const statusLabel = (s) => ({ online: '在线', offline: '离线', error: '异常', maintenance: '维护' }[s] || s)
const protoLabel = (p) => ({ modbus_tcp: 'Modbus TCP', mqtt: 'MQTT', opc_ua: 'OPC-UA' }[p] || p)
const protoTagType = (p) => ({ modbus_tcp: '', mqtt: 'success', opc_ua: 'warning' }[p] || 'info')
const formatTime = (t) => t ? dayjs(t).format('YYYY-MM-DD HH:mm:ss') : '-'

const tagForm = reactive({
  name: '', description: '', unit: '',
  function_code: 'holding_register', address: 0, data_type: 'uint16',
  byte_order: 'big_endian', register_count: 1, bit_index: null,
  mqtt_topic: '', mqtt_json_path: '', mqtt_value_type: 'float64',
  mqtt_publish_topic: '', mqtt_retain: false,
  opc_node_id: '', opc_node_type: 'float64',
  scale_factor: 1.0, offset: 0, decimal_places: 2,
  script_id: null, writable: false, enabled: true,
})

async function fetchDevice() {
  loading.value = true
  const res = await api.get(`/devices/${deviceId}`)
  device.value = res.data
  tags.value = res.data.tags || []
  resetPage()
}

async function fetchLive() {
  try {
    const res = await api.get(`/devices/${deviceId}/live`)
    const values = res.data.values || {}
    liveData.value = tags.value.map(tag => {
      const v = values[tag.id]
      return { tag_name: tag.name, unit: tag.unit, value: v?.value ?? '-', quality: v?.quality ?? 'unknown', time: v?.time ?? '-' }
    })
  } catch {
    liveData.value = tags.value.map(t => ({ tag_name: t.name, unit: t.unit, value: '-', quality: 'unknown', time: '-' }))
  }
}

function showTagDialog(tag) {
  if (tag) {
    editingTagId.value = tag.id
    Object.assign(tagForm, tag)
  } else {
    editingTagId.value = null
    Object.assign(tagForm, {
      name: '', description: '', unit: '',
      function_code: 'holding_register', address: 0, data_type: 'uint16',
      byte_order: 'big_endian', register_count: 1, bit_index: null,
      mqtt_topic: '', mqtt_json_path: '', mqtt_value_type: 'float64',
      mqtt_publish_topic: '', mqtt_retain: false,
      opc_node_id: '', opc_node_type: 'float64',
      scale_factor: 1.0, offset: 0, decimal_places: 2,
      writable: false, enabled: true,
    })
  }
  tagDialogVisible.value = true
}

async function saveTag() {
  if (!tagForm.name) { ElMessage.warning('请输入名称'); return }
  const proto = device.value?.protocol || 'modbus_tcp'
  if ((proto === 'modbus_tcp' || proto === 'modbus_rtu') && !tagForm.function_code) {
    ElMessage.warning('功能码为必选项，请选择功能码'); return
  }
  if (proto === 'mqtt' && !String(tagForm.mqtt_topic || '').trim() && !device.value?.mqtt_topic_prefix) {
    ElMessage.warning('MQTT 点位必须填写订阅主题（或先在设备上配置 Topic 前缀）'); return
  }
  if (proto === 'opc_ua' && !String(tagForm.opc_node_id || '').trim()) {
    ElMessage.warning('OPC UA 点位必须填写 Node ID，如 ns=2;s=Temperature'); return
  }
  const payload = { ...tagForm, device_id: parseInt(deviceId) }
  try {
    if (editingTagId.value) {
      await api.put(`/devices/tags/${editingTagId.value}`, payload)
    } else {
      await api.post('/devices/tags', payload)
    }
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || e?.response?.data?.message || '保存失败')
    return
  }
  ElMessage.success('保存成功')
  tagDialogVisible.value = false
  fetchDevice()
}

async function deleteTag(tag) {
  await ElMessageBox.confirm(`确定删除点位 "${tag.name}"？`)
  await api.delete(`/devices/tags/${tag.id}`)
  ElMessage.success('删除成功')
  fetchDevice()
}

let liveTimer = null
onMounted(async () => {
  fetchDevice(); fetchLive()
  liveTimer = setInterval(fetchLive, 5000)
  try { allScripts.value = (await api.get('/scripts')).data } catch {}
})
onUnmounted(() => { if (liveTimer) clearInterval(liveTimer) })
</script>
