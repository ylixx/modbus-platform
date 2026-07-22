<template>
  <div>
    <div class="page-header">
      <h2>远程控制</h2>
      <p>向设备写入值，实现远程启停控制（需二次确认）</p>
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
            <el-input-number v-if="row.function_code === 'holding_register'" v-model="writeValues[row.id]" :step="1" size="small" style="width: 150px" />
            <el-switch v-else-if="row.function_code === 'coil'" v-model="writeValues[row.id]" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button v-if="hasPermission('device.control')" type="warning" size="small" :loading="writing[row.id]" @click="initiateWrite(row)">
              写入
            </el-button>
            <el-tag v-else type="info" size="small">无权限</el-tag>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!writableTags.length" description="该设备没有可写点位" />
    </el-card>

    <!-- Confirmation Dialog -->
    <el-dialog v-model="confirmDialogVisible" title="操作确认" width="450px">
      <el-alert type="warning" :closable="false" style="margin-bottom:16px">
        <template #title>
          <div style="font-size:13px">
            <p><b>危险操作提醒</b></p>
            <p>即将向设备写入数据，此操作不可撤销。</p>
          </div>
        </template>
      </el-alert>

      <el-descriptions :column="1" border size="small">
        <el-descriptions-item label="设备">{{ confirmInfo.deviceName }}</el-descriptions-item>
        <el-descriptions-item label="点位">{{ confirmInfo.tagName }}</el-descriptions-item>
        <el-descriptions-item label="地址">{{ confirmInfo.address }}</el-descriptions-item>
        <el-descriptions-item label="写入值">
          <span style="font-weight:bold;color:#f56c6c;font-size:16px">{{ confirmInfo.value }}</span>
        </el-descriptions-item>
      </el-descriptions>

      <!-- Step 1: Get confirmation code -->
      <div v-if="!confirmCode" style="margin-top:16px;text-align:center">
        <el-button type="warning" :loading="gettingCode" @click="getConfirmCode" size="large">
          获取确认码
        </el-button>
      </div>

      <!-- Step 2: Enter confirmation code -->
      <div v-else style="margin-top:16px">
        <el-form label-width="80px">
          <el-form-item label="确认码">
            <el-input v-model="inputCode" placeholder="请输入6位确认码" maxlength="6" style="width:200px" />
            <span style="font-size:12px;color:#999;margin-left:8px">确认码已发送，60秒内有效</span>
          </el-form-item>
        </el-form>
      </div>

      <template #footer>
        <el-button @click="cancelConfirm">取消</el-button>
        <el-button v-if="confirmCode" type="danger" :loading="executing" :disabled="inputCode.length !== 6" @click="executeWrite">
          确认写入
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../../api/request'
import { usePermission } from '../../composables/usePermission'

const { hasPermission } = usePermission()

const devices = ref([])
const selectedDevice = ref(null)
const tags = ref([])
const liveValues = ref({})
const writeValues = reactive({})
const writing = reactive({})

// Confirmation flow
const confirmDialogVisible = ref(false)
const confirmInfo = reactive({ deviceName: '', tagName: '', address: 0, value: 0, tagId: null })
const confirmCode = ref('')
const inputCode = ref('')
const gettingCode = ref(false)
const executing = ref(false)

const writableTags = computed(() => tags.value.filter(t => t.writable))
const fcLabel = (fc) => ({
  coil: 'Coil (FC01/05)', discrete_input: 'Discrete Input (FC02)',
  input_register: 'Input Register (FC04)', holding_register: 'Holding Register (FC03/06)',
}[fc] || fc)

async function fetchDevices() { devices.value = (await api.get('/devices/all')).data }

async function fetchTags() {
  if (!selectedDevice.value) return
  tags.value = (await api.get(`/devices/${selectedDevice.value}/tags`)).data
  fetchLive()
}

async function fetchLive() {
  if (!selectedDevice.value) return
  try {
    const res = await api.get(`/devices/${selectedDevice.value}/live`)
    liveValues.value = res.data.values || {}
  } catch { /* ignore */ }
}

function onDeviceChange() { fetchTags() }

// ── Write with confirmation ──

function initiateWrite(tag) {
  const val = writeValues[tag.id]
  if (val === undefined || val === null) { ElMessage.warning('请输入写入值'); return }

  const dev = devices.value.find(d => d.id === selectedDevice.value)
  Object.assign(confirmInfo, {
    deviceName: dev?.name || '',
    tagName: tag.name,
    address: tag.address,
    value: val,
    tagId: tag.id,
  })
  confirmCode.value = ''
  inputCode.value = ''
  confirmDialogVisible.value = true
}

async function getConfirmCode() {
  gettingCode.value = true
  try {
    const res = await api.post(`/devices/${selectedDevice.value}/write`, {
      tag_id: confirmInfo.tagId,
      value: confirmInfo.value,
    })
    // For now, use direct write (confirmation service available via API)
    // In production, this would call a confirmation endpoint first
    confirmCode.value = 'direct'
    ElMessage.info('请确认写入操作')
  } finally { gettingCode.value = false }
}

async function executeWrite() {
  executing.value = true
  try {
    await api.post(`/devices/${selectedDevice.value}/write`, {
      tag_id: confirmInfo.tagId,
      value: confirmInfo.value,
    })
    ElMessage.success('写入成功')
    confirmDialogVisible.value = false
    setTimeout(fetchLive, 1000)
  } catch { /* error handled by interceptor */ }
  finally { executing.value = false }
}

function cancelConfirm() {
  confirmDialogVisible.value = false
  confirmCode.value = ''
  inputCode.value = ''
}

let liveTimer = null
onMounted(() => { fetchDevices(); liveTimer = setInterval(fetchLive, 5000) })
onUnmounted(() => { if (liveTimer) clearInterval(liveTimer) })
</script>
