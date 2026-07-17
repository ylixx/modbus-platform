<template>
  <div>
    <el-card>
      <template #header>
        <div style="display:flex;justify-content:space-between;align-items:center">
          <span>报警规则</span>
          <el-button type="primary" size="small" @click="showDialog()">新增规则</el-button>
        </div>
      </template>
      <el-table :data="rules" stripe>
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="name" label="规则名称" width="160" />
        <el-table-column prop="device_id" label="设备ID" width="80" />
        <el-table-column prop="alarm_type" label="类型" width="140">
          <template #default="{ row }">{{ typeLabel(row.alarm_type) }}</template>
        </el-table-column>
        <el-table-column prop="alarm_level" label="等级" width="100">
          <template #default="{ row }">
            <el-tag :type="levelType(row.alarm_level)" size="small">{{ levelLabel(row.alarm_level) }}</el-tag>
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
            <el-button size="small" @click="showDialog(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑规则' : '新增规则'" width="600px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="规则名称" required><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="设备" required>
          <el-select v-model="form.device_id" placeholder="选择设备">
            <el-option v-for="d in devices" :key="d.id" :label="d.name" :value="d.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="关联点位">
          <el-select v-model="form.tag_id" placeholder="选择点位(可选)" clearable>
            <el-option v-for="t in deviceTags" :key="t.id" :label="`${t.name} (addr:${t.address})`" :value="t.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="报警类型" required>
          <el-select v-model="form.alarm_type">
            <el-option label="上限报警" value="threshold_high" />
            <el-option label="下限报警" value="threshold_low" />
            <el-option label="区间报警(上下限)" value="threshold_range" />
            <el-option label="变化率报警" value="rate_of_change" />
            <el-option label="状态报警" value="status" />
            <el-option label="设备离线" value="disconnect" />
          </el-select>
        </el-form-item>
        <el-form-item label="报警等级">
          <el-select v-model="form.alarm_level">
            <el-option label="提示" value="info" />
            <el-option label="警告" value="warning" />
            <el-option label="严重" value="critical" />
            <el-option label="紧急" value="emergency" />
          </el-select>
        </el-form-item>
        <el-form-item label="上限值" v-if="['threshold_high','threshold_range'].includes(form.alarm_type)">
          <el-input-number v-model="form.high_limit" :step="0.1" />
        </el-form-item>
        <el-form-item label="下限值" v-if="['threshold_low','threshold_range'].includes(form.alarm_type)">
          <el-input-number v-model="form.low_limit" :step="0.1" />
        </el-form-item>
        <el-form-item label="变化率/s" v-if="form.alarm_type === 'rate_of_change'">
          <el-input-number v-model="form.rate_limit" :step="0.1" />
        </el-form-item>
        <el-form-item label="状态值" v-if="form.alarm_type === 'status'">
          <el-input-number v-model="form.status_value" />
        </el-form-item>
        <el-form-item label="死区"><el-input-number v-model="form.deadband" :step="0.01" /></el-form-item>
        <el-form-item label="延迟(秒)"><el-input-number v-model="form.delay_seconds" :min="0" /></el-form-item>
        <el-form-item label="自动消除"><el-switch v-model="form.auto_clear" /></el-form-item>
        <el-form-item label="启用"><el-switch v-model="form.enabled" /></el-form-item>
        <el-form-item label="发送短信"><el-switch v-model="form.sms_enabled" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="form.description" type="textarea" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, watch, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../../api/request'

const rules = ref([])
const devices = ref([])
const deviceTags = ref([])
const dialogVisible = ref(false)
const editingId = ref(null)

const typeLabel = (t) => ({
  threshold_high: '上限报警', threshold_low: '下限报警', threshold_range: '区间报警',
  rate_of_change: '变化率报警', status: '状态报警', disconnect: '设备离线',
}[t] || t)
const levelLabel = (l) => ({ info: '提示', warning: '警告', critical: '严重', emergency: '紧急' }[l] || l)
const levelType = (l) => ({ info: 'info', warning: 'warning', critical: 'danger', emergency: 'danger' }[l] || 'info')

const defaultForm = {
  name: '', device_id: null, tag_id: null, alarm_type: 'threshold_high',
  alarm_level: 'warning', high_limit: null, low_limit: null,
  rate_limit: null, status_value: null, deadband: 0, delay_seconds: 0,
  auto_clear: true, enabled: true, sms_enabled: false, description: '',
}
const form = reactive({ ...defaultForm })

watch(() => form.device_id, async (val) => {
  if (val) {
    const res = await api.get(`/devices/${val}/tags`)
    deviceTags.value = res.data
  } else {
    deviceTags.value = []
  }
})

async function fetchRules() {
  const res = await api.get('/alarms/rules/all')
  rules.value = res.data
}

async function fetchDevices() {
  const res = await api.get('/devices/all')
  devices.value = res.data
}

function showDialog(rule) {
  if (rule) {
    editingId.value = rule.id
    Object.assign(form, { ...defaultForm, ...rule })
  } else {
    editingId.value = null
    Object.assign(form, defaultForm)
  }
  dialogVisible.value = true
}

async function handleSave() {
  if (!form.name || !form.device_id) { ElMessage.warning('请填写必填字段'); return }
  if (editingId.value) {
    await api.put(`/alarms/rules/${editingId.value}`, form)
  } else {
    await api.post('/alarms/rules', form)
  }
  ElMessage.success('保存成功')
  dialogVisible.value = false
  fetchRules()
}

async function handleDelete(rule) {
  await ElMessageBox.confirm(`确定删除规则 "${rule.name}"？`)
  await api.delete(`/alarms/rules/${rule.id}`)
  ElMessage.success('删除成功')
  fetchRules()
}

onMounted(() => {
  fetchRules()
  fetchDevices()
})
</script>
