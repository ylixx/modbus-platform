<template>
  <div>
    <el-card>
      <template #header>
        <div style="display:flex;justify-content:space-between;align-items:center">
          <span>报警规则</span>
          <el-button type="primary" size="small" @click="openDialog()"><el-icon><Plus /></el-icon> 新增规则</el-button>
        </div>
      </template>
      <el-table :data="tableData" v-loading="loading" stripe>
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="name" label="规则名称" width="160" />
        <el-table-column prop="device_id" label="设备ID" width="80" />
        <el-table-column prop="alarm_type" label="类型" width="140">
          <template #default="{ row }">
            <DictTag :modelValue="row.alarm_type" :options="ALARM_TYPE_OPTIONS" />
          </template>
        </el-table-column>
        <el-table-column prop="alarm_level" label="等级" width="100">
          <template #default="{ row }">
            <DictTag :modelValue="row.alarm_level" :options="ALARM_LEVEL_OPTIONS" />
          </template>
        </el-table-column>
        <el-table-column label="阈值" width="200">
          <template #default="{ row }">
            <span v-if="row.high_limit !== null">上限: {{ row.high_limit }}</span>
            <span v-if="row.low_limit !== null"> | 下限: {{ row.low_limit }}</span>
            <span v-if="row.rate_limit !== null"> | 变化率: {{ row.rate_limit }}/s</span>
            <span v-if="row.status_value !== null"> | 状态值: {{ row.status_value }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="enabled" label="启用" width="70">
          <template #default="{ row }">
            <el-tag :type="row.enabled ? 'success' : 'info'" size="small">{{ row.enabled ? '是' : '否' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="sms_enabled" label="短信" width="70">
          <template #default="{ row }">{{ row.sms_enabled ? '是' : '否' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="150">
          <template #default="{ row }">
            <el-button size="small" @click="openDialog(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="handleDelete(row, 'name')">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Dialog -->
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑规则' : '新增规则'" width="600px">
      <el-scrollbar max-height="65vh">
        <el-form :model="form" label-width="100px" style="padding-right:20px">
          <el-form-item label="规则名称" required><el-input v-model="form.name" /></el-form-item>
          <el-form-item label="设备" required>
            <el-select v-model="form.device_id" placeholder="选择设备" style="width:100%" @change="onDeviceChange">
              <el-option v-for="d in devices" :key="d.id" :label="d.name" :value="d.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="关联点位">
            <el-select v-model="form.tag_id" placeholder="选择点位(可选)" clearable style="width:100%">
              <el-option v-for="t in deviceTags" :key="t.id" :label="`${t.name} (addr:${t.address})`" :value="t.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="报警类型" required>
            <el-select v-model="form.alarm_type" style="width:100%">
              <el-option v-for="item in ALARM_TYPE_OPTIONS" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="报警等级">
            <el-select v-model="form.alarm_level" style="width:100%">
              <el-option v-for="item in ALARM_LEVEL_OPTIONS" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="上限值" v-if="['threshold_high','threshold_range'].includes(form.alarm_type)">
            <el-input-number v-model="form.high_limit" :step="0.1" style="width:100%" />
          </el-form-item>
          <el-form-item label="下限值" v-if="['threshold_low','threshold_range'].includes(form.alarm_type)">
            <el-input-number v-model="form.low_limit" :step="0.1" style="width:100%" />
          </el-form-item>
          <el-form-item label="变化率/s" v-if="form.alarm_type === 'rate_of_change'">
            <el-input-number v-model="form.rate_limit" :step="0.1" style="width:100%" />
          </el-form-item>
          <el-form-item label="状态值" v-if="form.alarm_type === 'status'">
            <el-input-number v-model="form.status_value" style="width:100%" />
          </el-form-item>
          <el-form-item label="死区"><el-input-number v-model="form.deadband" :step="0.01" style="width:100%" /></el-form-item>
          <el-form-item label="延迟(秒)"><el-input-number v-model="form.delay_seconds" :min="0" style="width:100%" /></el-form-item>
          <el-form-item label="自动消除"><el-switch v-model="form.auto_clear" /></el-form-item>
          <el-form-item label="启用"><el-switch v-model="form.enabled" /></el-form-item>
          <el-form-item label="发送短信"><el-switch v-model="form.sms_enabled" /></el-form-item>
          <el-form-item label="描述"><el-input v-model="form.description" type="textarea" /></el-form-item>
        </el-form>
      </el-scrollbar>
      <template #footer>
        <el-button @click="closeDialog">取消</el-button>
        <el-button type="primary" :loading="submitLoading" @click="handleSubmit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import api from '../../api/request'
import { useTable } from '../../composables/useTable'
import { useForm } from '../../composables/useForm'
import DictTag from '../../components/DictTag.vue'
import { ALARM_TYPE_OPTIONS, ALARM_LEVEL_OPTIONS } from '../../utils/dict'

// Devices list
const devices = ref([])
const deviceTags = ref([])

async function fetchDevices() {
  const res = await api.get('/devices/all')
  devices.value = res.data
}

async function onDeviceChange() {
  form.tag_id = null
  if (form.device_id) {
    const res = await api.get(`/devices/${form.device_id}/tags`)
    deviceTags.value = res.data
  } else {
    deviceTags.value = []
  }
}

// Table
const { tableData, loading, fetchList, handleDelete } = useTable({
  listApi: (params) => api.get('/alarms/rules/all'),
  deleteApi: (id) => api.delete(`/alarms/rules/${id}`),
  immediate: true,
})

// Form
const defaultForm = {
  name: '', device_id: null, tag_id: null, alarm_type: 'threshold_high',
  alarm_level: 'warning', high_limit: null, low_limit: null,
  rate_limit: null, status_value: null, deadband: 0, delay_seconds: 0,
  auto_clear: true, enabled: true, sms_enabled: false, description: '',
}

const { form, dialogVisible, isEdit, submitLoading, openDialog, closeDialog, handleSubmit } = useForm({
  defaultForm,
  createApi: (data) => api.post('/alarms/rules', data),
  updateApi: (id, data) => api.put(`/alarms/rules/${id}`, data),
  validate: (form) => {
    if (!form.name) return '请输入规则名称'
    if (!form.device_id) return '请选择设备'
  },
  onSuccess: () => fetchList(),
})

// Load tags when editing (device_id already set)
watch(() => form.device_id, (val) => {
  if (val) onDeviceChange()
})

onMounted(fetchDevices)
</script>
