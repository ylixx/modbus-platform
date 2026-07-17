<template>
  <div>
    <div class="page-header">
      <h2>远程控制</h2>
      <p>向设备写入值，实现远程启停控制</p>
    </div>

    <el-card style="margin-bottom: 16px">
      <el-row :gutter="16" align="middle">
        <el-col :span="6">
          <el-select v-model="selectedDevice" placeholder="选择设备" @change="onDeviceChange">
            <el-option v-for="d in devices" :key="d.id" :label="d.name" :value="d.id" />
          </el-select>
        </el-col>
        <el-col :span="4">
          <el-button @click="fetchTags" :disabled="!selectedDevice"><el-icon><Refresh /></el-icon> 刷新</el-button>
        </el-col>
      </el-row>
    </el-card>

    <el-card v-if="selectedDevice" header="可写点位">
      <el-table :data="writableTags" stripe>
        <el-table-column prop="name" label="点位名称" width="160" />
        <el-table-column prop="function_code" label="功能码" width="160">
          <template #default="{ row }">{{ fcLabel(row.function_code) }}</template>
        </el-table-column>
        <el-table-column prop="address" label="地址" width="80" />
        <el-table-column prop="data_type" label="类型" width="100" />
        <el-table-column prop="unit" label="单位" width="80" />
        <el-table-column label="当前值" width="120">
          <template #default="{ row }">
            <span style="font-weight: bold; color: #1890ff">{{ liveValues[row.id]?.value ?? '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="写入值" width="200">
          <template #default="{ row }">
            <el-input-number
              v-if="row.function_code === 'holding_register'"
              v-model="writeValues[row.id]"
              :step="1"
              size="small"
              style="width: 150px"
            />
            <el-switch
              v-else-if="row.function_code === 'coil'"
              v-model="writeValues[row.id]"
            />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button
              type="primary"
              size="small"
              :loading="writing[row.id]"
              @click="handleWrite(row)"
            >写入</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="writableTags.length === 0" description="该设备没有可写点位" />
    </el-card>

    <!-- Quick Control Panel -->
    <el-card v-if="selectedDevice" header="快捷控制" style="margin-top: 16px">
      <el-alert type="warning" :closable="false" style="margin-bottom: 16px">
        快捷控制会向指定地址写入预设值，适用于设备启停等常用操作。
      </el-alert>
      <el-form label-width="120px">
        <el-form-item label="写入地址">
          <el-input-number v-model="quickControl.address" :min="0" />
        </el-form-item>
        <el-form-item label="功能码">
          <el-select v-model="quickControl.function_code">
            <el-option label="Coil (FC05)" value="coil" />
            <el-option label="Holding Register (FC06)" value="holding_register" />
          </el-select>
        </el-form-item>
        <el-form-item label="写入值">
          <el-input-number v-if="quickControl.function_code === 'holding_register'" v-model="quickControl.value" />
          <el-switch v-else v-model="quickControl.boolValue" />
        </el-form-item>
        <el-form-item>
          <el-button type="danger" @click="handleQuickWrite" :loading="quickWriting">执行写入</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../../api/request'

const devices = ref([])
const selectedDevice = ref(null)
const tags = ref([])
const liveValues = ref({})
const writeValues = reactive({})
const writing = reactive({})
const quickWriting = ref(false)

const quickControl = reactive({
  address: 0,
  function_code: 'holding_register',
  value: 0,
  boolValue: false,
})

const writableTags = computed(() => tags.value.filter(t => t.writable))
const fcLabel = (fc) => ({
  coil: 'Coil (FC01/05)', discrete_input: 'Discrete Input (FC02)',
  input_register: 'Input Register (FC04)', holding_register: 'Holding Register (FC03/06)',
}[fc] || fc)

async function fetchDevices() {
  const res = await api.get('/devices/all')
  devices.value = res.data
}

async function fetchTags() {
  if (!selectedDevice.value) return
  const res = await api.get(`/devices/${selectedDevice.value}/tags`)
  tags.value = res.data
  fetchLive()
}

async function fetchLive() {
  if (!selectedDevice.value) return
  try {
    const res = await api.get(`/devices/${selectedDevice.value}/live`)
    liveValues.value = res.data.values || {}
  } catch { /* ignore */ }
}

function onDeviceChange() {
  fetchTags()
}

async function handleWrite(tag) {
  const val = writeValues[tag.id]
  if (val === undefined || val === null) {
    ElMessage.warning('请输入写入值')
    return
  }
  await ElMessageBox.confirm(`确定向 ${tag.name} (地址:${tag.address}) 写入值 ${val}？`, '确认写入', { type: 'warning' })
  writing[tag.id] = true
  try {
    await api.post(`/devices/${selectedDevice.value}/write`, { tag_id: tag.id, value: val })
    ElMessage.success('写入成功')
    setTimeout(fetchLive, 1000)
  } catch (e) {
    // Error handled by interceptor
  } finally {
    writing[tag.id] = false
  }
}

async function handleQuickWrite() {
  await ElMessageBox.confirm(
    `确定向地址 ${quickControl.address} 写入 ${quickControl.function_code === 'coil' ? quickControl.boolValue : quickControl.value}？`,
    '确认写入', { type: 'warning' }
  )
  quickWriting.value = true
  try {
    // We need a tag_id, but for quick control we'll create a temporary approach
    // Find or create a tag for this address
    ElMessage.info('请使用点位列表中的写入功能，或先在设备详情中配置可写点位')
  } finally {
    quickWriting.value = false
  }
}

let liveTimer = null
onMounted(() => {
  fetchDevices()
  liveTimer = setInterval(fetchLive, 5000)
})
onUnmounted(() => { if (liveTimer) clearInterval(liveTimer) })
</script>
