<template>
  <div>
    <div class="page-header">
      <h2>采集点位</h2>
      <p>所有设备的采集点位汇总（支持 Modbus / MQTT / OPC-UA）</p>
    </div>
    <el-card>
      <template #header>
        <el-row :gutter="16" align="middle">
          <el-col :span="5">
            <el-select v-model="filterDevice" placeholder="选择设备" clearable @change="fetchTags">
              <el-option v-for="d in allDevices" :key="d.id" :label="`${d.name} [${protoLabel(d.protocol)}]`" :value="d.id" />
            </el-select>
          </el-col>
          <el-col :span="4">
            <el-select v-model="filterProtocol" placeholder="协议" clearable @change="fetchTags">
              <el-option v-for="p in PROTOCOL_OPTIONS" :key="p.value" :label="p.label" :value="p.value" />
            </el-select>
          </el-col>
        </el-row>
      </template>
      <el-table :data="filteredTags" v-loading="loading" stripe>
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="device_id" label="设备" width="120"><template #default="{ row }">{{ deviceName(row.device_id) }}</template></el-table-column>
        <el-table-column prop="name" label="名称" width="150" />
        <el-table-column label="数据源" width="240">
          <template #default="{ row }">
            <span v-if="deviceProtocol(row.device_id) === 'modbus_tcp'">{{ fcLabel(row.function_code) }} @ {{ row.address }}</span>
            <span v-else-if="deviceProtocol(row.device_id) === 'mqtt'">{{ row.mqtt_topic || 'prefix/' + row.name }}</span>
            <span v-else>{{ row.opc_node_id }}</span>
          </template>
        </el-table-column>
        <el-table-column label="类型" width="100">
          <template #default="{ row }">{{ deviceProtocol(row.device_id) === 'mqtt' ? row.mqtt_value_type : deviceProtocol(row.device_id) === 'opc_ua' ? row.opc_node_type : row.data_type }}</template>
        </el-table-column>
        <el-table-column prop="scale_factor" label="系数" width="80" />
        <el-table-column prop="unit" label="单位" width="80" />
        <el-table-column prop="writable" label="可写" width="70"><template #default="{ row }"><DictTag :modelValue="row.writable" :options="BOOL_OPTIONS" /></template></el-table-column>
        <el-table-column prop="enabled" label="启用" width="70"><template #default="{ row }"><DictTag :modelValue="row.enabled" :options="BOOL_OPTIONS" /></template></el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '../../api/request'
import DictTag from '../../components/DictTag.vue'
import { PROTOCOL_OPTIONS, FUNCTION_CODE_OPTIONS } from '../../utils/dict'

const BOOL_OPTIONS = [{ value: true, label: '是', type: 'success' }, { value: false, label: '否', type: 'info' }]

const tags = ref([])
const allDevices = ref([])
const loading = ref(false)
const filterDevice = ref(null)
const filterProtocol = ref(null)

const deviceMap = computed(() => Object.fromEntries(allDevices.value.map(d => [d.id, d])))
const deviceName = (id) => deviceMap.value[id]?.name || `#${id}`
const deviceProtocol = (id) => deviceMap.value[id]?.protocol || 'modbus_tcp'
const protoLabel = (p) => (PROTOCOL_OPTIONS.find(o => o.value === p)?.label || p)
const fcLabel = (fc) => (FUNCTION_CODE_OPTIONS.find(o => o.value === fc)?.label || fc)

const filteredTags = computed(() => {
  let t = tags.value
  if (filterDevice.value) t = t.filter(tag => tag.device_id === filterDevice.value)
  if (filterProtocol.value) t = t.filter(tag => deviceProtocol(tag.device_id) === filterProtocol.value)
  return t
})

async function fetchTags() {
  loading.value = true
  try {
    if (filterDevice.value) { tags.value = (await api.get(`/devices/${filterDevice.value}/tags`)).data }
    else {
      const devs = (await api.get('/devices/all')).data; allDevices.value = devs
      const all = []; for (const d of devs) { all.push(...(await api.get(`/devices/${d.id}/tags`)).data) }; tags.value = all
    }
  } finally { loading.value = false }
}

async function fetchDevices() { allDevices.value = (await api.get('/devices/all')).data }

onMounted(() => { fetchDevices(); fetchTags() })
</script>
