<template>
  <div>
    <div class="page-header">
      <h2>采集点位</h2>
      <p>所有设备的采集点位汇总（支持 Modbus / MQTT / OPC-UA）</p>
    </div>
    <el-card>
      <el-row :gutter="16" style="margin-bottom: 16px">
        <el-col :span="5">
          <el-select v-model="filterDevice" placeholder="选择设备" clearable @change="fetchTags">
            <el-option v-for="d in allDevices" :key="d.id" :label="`${d.name} [${protoLabel(d.protocol)}]`" :value="d.id" />
          </el-select>
        </el-col>
        <el-col :span="4">
          <el-select v-model="filterProtocol" placeholder="协议" clearable @change="fetchTags">
            <el-option label="Modbus TCP" value="modbus_tcp" />
            <el-option label="MQTT" value="mqtt" />
            <el-option label="OPC-UA" value="opc_ua" />
          </el-select>
        </el-col>
      </el-row>
      <el-table :data="filteredTags" stripe v-loading="loading">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="device_id" label="设备" width="120">
          <template #default="{ row }">{{ deviceName(row.device_id) }}</template>
        </el-table-column>
        <el-table-column prop="name" label="名称" width="150" />
        <el-table-column label="数据源" width="240">
          <template #default="{ row }">
            <span v-if="deviceProtocol(row.device_id) === 'modbus_tcp'">{{ fcLabel(row.function_code) }} @ {{ row.address }}</span>
            <span v-else-if="deviceProtocol(row.device_id) === 'mqtt'">{{ row.mqtt_topic || 'prefix/' + row.name }}</span>
            <span v-else>{{ row.opc_node_id }}</span>
          </template>
        </el-table-column>
        <el-table-column label="类型" width="100">
          <template #default="{ row }">
            {{ deviceProtocol(row.device_id) === 'mqtt' ? row.mqtt_value_type : deviceProtocol(row.device_id) === 'opc_ua' ? row.opc_node_type : row.data_type }}
          </template>
        </el-table-column>
        <el-table-column prop="scale_factor" label="系数" width="80" />
        <el-table-column prop="unit" label="单位" width="80" />
        <el-table-column prop="writable" label="可写" width="70">
          <template #default="{ row }">{{ row.writable ? '是' : '否' }}</template>
        </el-table-column>
        <el-table-column prop="enabled" label="启用" width="70">
          <template #default="{ row }">
            <el-tag :type="row.enabled ? 'success' : 'info'" size="small">{{ row.enabled ? '是' : '否' }}</el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '../../api/request'

const tags = ref([])
const allDevices = ref([])
const loading = ref(false)
const filterDevice = ref(null)
const filterProtocol = ref(null)

const protoLabel = (p) => ({ modbus_tcp: 'Modbus TCP', mqtt: 'MQTT', opc_ua: 'OPC-UA' }[p] || p)
const fcLabel = (fc) => ({
  coil: 'Coil (FC01)', discrete_input: 'Discrete Input (FC02)',
  input_register: 'Input Register (FC04)', holding_register: 'Holding Register (FC03)',
}[fc] || fc)

const deviceMap = computed(() => Object.fromEntries(allDevices.value.map(d => [d.id, d])))
const deviceName = (id) => deviceMap.value[id]?.name || `#${id}`
const deviceProtocol = (id) => deviceMap.value[id]?.protocol || 'modbus_tcp'

const filteredTags = computed(() => {
  if (!filterDevice.value && !filterProtocol.value) return tags.value
  return tags.value.filter(t => {
    if (filterDevice.value && t.device_id !== filterDevice.value) return false
    if (filterProtocol.value && deviceProtocol(t.device_id) !== filterProtocol.value) return false
    return true
  })
})

async function fetchTags() {
  loading.value = true
  try {
    if (filterDevice.value) {
      const res = await api.get(`/devices/${filterDevice.value}/tags`)
      tags.value = res.data
    } else {
      const devs = await api.get('/devices/all')
      allDevices.value = devs.data
      const allTags = []
      for (const d of devs.data) {
        const res = await api.get(`/devices/${d.id}/tags`)
        allTags.push(...res.data)
      }
      tags.value = allTags
    }
  } finally { loading.value = false }
}

async function fetchDevices() {
  const res = await api.get('/devices/all')
  allDevices.value = res.data
}

onMounted(() => { fetchDevices(); fetchTags() })
</script>
