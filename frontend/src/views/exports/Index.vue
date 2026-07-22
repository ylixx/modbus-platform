<template>
  <div>
    <div class="page-header">
      <h2>数据导出</h2>
      <p>导出历史数据、报警记录、设备清单</p>
    </div>

    <el-row :gutter="20">
      <!-- History Export -->
      <el-col :span="8">
        <el-card header="历史数据导出">
          <el-form label-width="80px">
            <el-form-item label="设备">
              <el-select v-model="historyForm.device_id" placeholder="选择设备" @change="fetchTags">
                <el-option v-for="d in devices" :key="d.id" :label="d.name" :value="d.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="点位">
              <el-select v-model="historyForm.tag_id" placeholder="全部" clearable>
                <el-option v-for="t in tags" :key="t.id" :label="`${t.name} (${t.unit||'-'})`" :value="t.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="时间范围">
              <el-date-picker v-model="historyTimeRange" type="datetimerange" range-separator="至"
                start-placeholder="开始" end-placeholder="结束" format="YYYY-MM-DD HH:mm:ss"
                value-format="YYYY-MM-DD HH:mm:ss" style="width:100%" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="exportHistory"><el-icon><Download /></el-icon> 导出 CSV</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <!-- Alarm Export -->
      <el-col :span="8">
        <el-card header="报警记录导出">
          <el-form label-width="80px">
            <el-form-item label="设备">
              <el-select v-model="alarmForm.device_id" placeholder="全部" clearable>
                <el-option v-for="d in devices" :key="d.id" :label="d.name" :value="d.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="等级">
              <el-select v-model="alarmForm.alarm_level" placeholder="全部" clearable>
                <el-option label="提示" value="info" />
                <el-option label="警告" value="warning" />
                <el-option label="严重" value="critical" />
                <el-option label="紧急" value="emergency" />
              </el-select>
            </el-form-item>
            <el-form-item label="时间范围">
              <el-date-picker v-model="alarmTimeRange" type="datetimerange" range-separator="至"
                start-placeholder="开始" end-placeholder="结束" format="YYYY-MM-DD HH:mm:ss"
                value-format="YYYY-MM-DD HH:mm:ss" style="width:100%" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="exportAlarms"><el-icon><Download /></el-icon> 导出 CSV</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <!-- Device Export -->
      <el-col :span="8">
        <el-card header="设备清单导出">
          <el-alert type="info" :closable="false" style="margin-bottom: 16px">
            导出所有设备及采集点位配置
          </el-alert>
          <el-button type="primary" @click="exportDevices" style="width:100%">
            <el-icon><Download /></el-icon> 导出设备清单 CSV
          </el-button>

          <el-divider />
          <el-button type="success" @click="exportDailyReport" style="width:100%">
            <el-icon><Document /></el-icon> 生成日报 JSON
          </el-button>
          <div style="font-size:12px;color:#999;margin-top:8px">
            包含设备在线率、报警统计、短信发送等当日汇总
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../../api/request'

const devices = ref([])
const tags = ref([])
const historyForm = reactive({ device_id: null, tag_id: null })
const alarmForm = reactive({ device_id: null, alarm_level: null })
const historyTimeRange = ref([])
const alarmTimeRange = ref([])

async function fetchDevices() {
  const res = await api.get('/devices/all')
  devices.value = res.data
}

async function fetchTags() {
  if (!historyForm.device_id) { tags.value = []; return }
  const res = await api.get(`/devices/${historyForm.device_id}/tags`)
  tags.value = res.data
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = filename; a.click()
  URL.revokeObjectURL(url)
}

async function exportHistory() {
  if (!historyForm.device_id) { ElMessage.warning('请选择设备'); return }
  const params = { device_id: historyForm.device_id }
  if (historyForm.tag_id) params.tag_id = historyForm.tag_id
  if (historyTimeRange.value?.length === 2) {
    params.start_time = historyTimeRange.value[0]
    params.end_time = historyTimeRange.value[1]
  }
  const res = await api.get('/export/history/csv', { params, responseType: 'blob' })
  downloadBlob(res.data, `history_${historyForm.device_id}.csv`)
  ElMessage.success('导出成功')
}

async function exportAlarms() {
  const params = {}
  if (alarmForm.device_id) params.device_id = alarmForm.device_id
  if (alarmForm.alarm_level) params.alarm_level = alarmForm.alarm_level
  if (alarmTimeRange.value?.length === 2) {
    params.start_time = alarmTimeRange.value[0]
    params.end_time = alarmTimeRange.value[1]
  }
  const res = await api.get('/export/alarms/csv', { params, responseType: 'blob' })
  downloadBlob(res.data, `alarms.csv`)
  ElMessage.success('导出成功')
}

async function exportDevices() {
  const res = await api.get('/export/devices/csv', { responseType: 'blob' })
  downloadBlob(res.data, `devices.csv`)
  ElMessage.success('导出成功')
}

async function exportDailyReport() {
  const res = await api.get('/export/report/daily')
  const blob = new Blob([JSON.stringify(res.data, null, 2)], { type: 'application/json' })
  downloadBlob(blob, `daily_report_${res.data.date}.json`)
  ElMessage.success('日报已生成')
}

onMounted(fetchDevices)
</script>
