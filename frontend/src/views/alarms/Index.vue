<template>
  <div>
    <div class="page-header">
      <h2>报警管理</h2>
      <p>查看和处理报警信息</p>
    </div>

    <!-- Stats -->
    <div class="card-grid">
      <div class="stat-card danger">
        <div class="stat-value">{{ stats.total_active || 0 }}</div>
        <div class="stat-label">活跃报警</div>
      </div>
      <div class="stat-card warning">
        <div class="stat-value">{{ stats.total_acknowledged || 0 }}</div>
        <div class="stat-label">已确认</div>
      </div>
      <div class="stat-card success">
        <div class="stat-value">{{ stats.total_cleared || 0 }}</div>
        <div class="stat-label">已消除</div>
      </div>
    </div>

    <!-- Tabs -->
    <el-tabs v-model="activeTab">
      <el-tab-pane label="活跃报警" name="active">
        <el-card>
          <el-table :data="activeAlarms" stripe>
            <el-table-column prop="alarm_level" label="等级" width="100">
              <template #default="{ row }">
                <el-tag :type="levelType(row.alarm_level)" size="small">{{ levelLabel(row.alarm_level) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="alarm_message" label="报警信息" />
            <el-table-column prop="trigger_value" label="触发值" width="100" />
            <el-table-column prop="threshold_value" label="阈值" width="100" />
            <el-table-column prop="triggered_at" label="触发时间" width="170">
              <template #default="{ row }">{{ formatTime(row.triggered_at) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="200">
              <template #default="{ row }">
                <el-button size="small" type="warning" @click="showAckDialog(row)">确认</el-button>
                <el-button size="small" type="success" @click="clearAlarm(row)">消除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="全部记录" name="all">
        <el-card>
          <el-row :gutter="16" style="margin-bottom: 16px">
            <el-col :span="4">
              <el-select v-model="filters.level" placeholder="报警等级" clearable @change="fetchRecords">
                <el-option label="提示" value="info" />
                <el-option label="警告" value="warning" />
                <el-option label="严重" value="critical" />
                <el-option label="紧急" value="emergency" />
              </el-select>
            </el-col>
            <el-col :span="4">
              <el-select v-model="filters.status" placeholder="状态" clearable @change="fetchRecords">
                <el-option label="活跃" value="active" />
                <el-option label="已确认" value="acknowledged" />
                <el-option label="已消除" value="cleared" />
              </el-select>
            </el-col>
          </el-row>
          <el-table :data="records" stripe>
            <el-table-column prop="id" label="ID" width="60" />
            <el-table-column prop="alarm_level" label="等级" width="100">
              <template #default="{ row }">
                <el-tag :type="levelType(row.alarm_level)" size="small">{{ levelLabel(row.alarm_level) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="alarm_message" label="报警信息" />
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="triggered_at" label="触发时间" width="170">
              <template #default="{ row }">{{ formatTime(row.triggered_at) }}</template>
            </el-table-column>
            <el-table-column prop="acknowledged_by" label="确认人" width="100" />
          </el-table>
          <el-pagination
            v-model:current-page="recordPage"
            :total="recordTotal"
            layout="total, prev, pager, next"
            style="margin-top: 16px"
            @current-change="fetchRecords"
          />
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="报警规则" name="rules">
        <Rules />
      </el-tab-pane>
    </el-tabs>

    <!-- Ack Dialog -->
    <el-dialog v-model="ackDialogVisible" title="确认报警" width="400px">
      <el-form label-width="60px">
        <el-form-item label="备注">
          <el-input v-model="ackComment" type="textarea" placeholder="输入处理说明" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="ackDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="ackAlarm">确认</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../../api/request'
import dayjs from 'dayjs'
import Rules from './Rules.vue'

const activeTab = ref('active')
const stats = ref({})
const activeAlarms = ref([])
const records = ref([])
const recordTotal = ref(0)
const recordPage = ref(1)
const filters = reactive({ level: '', status: '' })
const ackDialogVisible = ref(false)
const ackComment = ref('')
let ackRecordId = null

const levelMap = { info: '提示', warning: '警告', critical: '严重', emergency: '紧急' }
const levelLabel = (l) => levelMap[l] || l
const levelType = (l) => ({ info: 'info', warning: 'warning', critical: 'danger', emergency: 'danger' }[l] || 'info')
const statusLabel = (s) => ({ active: '活跃', acknowledged: '已确认', cleared: '已消除' }[s] || s)
const statusType = (s) => ({ active: 'danger', acknowledged: 'warning', cleared: 'success' }[s] || 'info')
const formatTime = (t) => t ? dayjs(t).format('YYYY-MM-DD HH:mm:ss') : '-'

async function fetchData() {
  try {
    const [statsRes, activeRes] = await Promise.all([
      api.get('/alarms/stats'),
      api.get('/alarms/records/active'),
    ])
    stats.value = statsRes.data
    activeAlarms.value = activeRes.data
  } catch (e) { console.error(e) }
}

async function fetchRecords() {
  const params = { page: recordPage.value, page_size: 20 }
  if (filters.level) params.alarm_level = filters.level
  if (filters.status) params.status = filters.status
  const res = await api.get('/alarms/records', { params })
  records.value = res.data.data
  recordTotal.value = res.data.total
}

function showAckDialog(row) {
  ackRecordId = row.id
  ackComment.value = ''
  ackDialogVisible.value = true
}

async function ackAlarm() {
  await api.post(`/alarms/records/${ackRecordId}/acknowledge`, { comment: ackComment.value })
  ElMessage.success('已确认')
  ackDialogVisible.value = false
  fetchData()
  fetchRecords()
}

async function clearAlarm(row) {
  await api.post(`/alarms/records/${row.id}/clear`)
  ElMessage.success('已消除')
  fetchData()
  fetchRecords()
}

let timer = null
onMounted(() => {
  fetchData()
  fetchRecords()
  timer = setInterval(fetchData, 15000)
})
onUnmounted(() => { if (timer) clearInterval(timer) })
</script>
