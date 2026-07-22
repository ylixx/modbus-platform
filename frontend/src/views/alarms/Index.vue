<template>
  <div>
    <div class="page-header">
      <h2>报警管理</h2>
      <p>查看和处理报警信息</p>
    </div>

    <!-- Stats -->
    <div class="card-grid">
      <div class="stat-card danger"><div class="stat-value">{{ stats.total_active || 0 }}</div><div class="stat-label">活跃报警</div></div>
      <div class="stat-card warning"><div class="stat-value">{{ stats.total_acknowledged || 0 }}</div><div class="stat-label">已确认</div></div>
      <div class="stat-card success"><div class="stat-value">{{ stats.total_cleared || 0 }}</div><div class="stat-label">已消除</div></div>
    </div>

    <el-tabs v-model="activeTab">
      <el-tab-pane label="活跃报警" name="active">
        <el-card>
          <el-table :data="activeAlarms" stripe>
            <el-table-column prop="alarm_level" label="等级" width="100"><template #default="{ row }"><DictTag :modelValue="row.alarm_level" :options="ALARM_LEVEL_OPTIONS" /></template></el-table-column>
            <el-table-column prop="alarm_message" label="报警信息" />
            <el-table-column prop="trigger_value" label="触发值" width="100" />
            <el-table-column prop="threshold_value" label="阈值" width="100" />
            <el-table-column prop="triggered_at" label="触发时间" width="170"><template #default="{ row }">{{ formatTime(row.triggered_at) }}</template></el-table-column>
            <el-table-column label="操作" width="200">
              <template #default="{ row }">
                <el-button v-if="hasPermission('alarm.ack')" size="small" type="warning" @click="showAckDialog(row)">确认</el-button>
                <el-button v-if="hasPermission('alarm.clear')" size="small" type="success" @click="clearAlarm(row)">消除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="全部记录" name="all">
        <el-card>
          <el-row :gutter="16" style="margin-bottom:16px">
            <el-col :span="4">
              <el-select v-model="searchParams.alarm_level" placeholder="报警等级" clearable @change="handleSearch">
                <el-option v-for="item in ALARM_LEVEL_OPTIONS" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-col>
            <el-col :span="4">
              <el-select v-model="searchParams.status" placeholder="状态" clearable @change="handleSearch">
                <el-option v-for="item in ALARM_STATUS_OPTIONS" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-col>
          </el-row>
          <el-table :data="tableData" v-loading="loading" stripe>
            <el-table-column prop="id" label="ID" width="60" />
            <el-table-column prop="alarm_level" label="等级" width="100"><template #default="{ row }"><DictTag :modelValue="row.alarm_level" :options="ALARM_LEVEL_OPTIONS" /></template></el-table-column>
            <el-table-column prop="alarm_message" label="报警信息" />
            <el-table-column prop="status" label="状态" width="100"><template #default="{ row }"><DictTag :modelValue="row.status" :options="ALARM_STATUS_OPTIONS" /></template></el-table-column>
            <el-table-column prop="triggered_at" label="触发时间" width="170"><template #default="{ row }">{{ formatTime(row.triggered_at) }}</template></el-table-column>
            <el-table-column prop="acknowledged_by" label="确认人" width="100" />
          </el-table>
          <el-pagination v-model:current-page="page" :total="total" layout="total, prev, pager, next" style="margin-top:16px" @current-change="handlePageChange" />
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="报警规则" name="rules"><Rules /></el-tab-pane>
    </el-tabs>

    <!-- Ack Dialog -->
    <el-dialog v-model="ackDialogVisible" title="确认报警" width="400px">
      <el-form label-width="60px"><el-form-item label="备注"><el-input v-model="ackComment" type="textarea" placeholder="输入处理说明" /></el-form-item></el-form>
      <template #footer>
        <el-button @click="ackDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="ackAlarm">确认</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../../api/request'
import { useTable } from '../../composables/useTable'
import { usePermission } from '../../composables/usePermission'

const { hasPermission } = usePermission()
import { formatTime } from '../../utils'
import DictTag from '../../components/DictTag.vue'
import { ALARM_LEVEL_OPTIONS, ALARM_STATUS_OPTIONS } from '../../utils/dict'
import Rules from './Rules.vue'

const activeTab = ref('active')
const stats = ref({})
const activeAlarms = ref([])
const ackDialogVisible = ref(false)
const ackComment = ref('')
let ackRecordId = null

// All records table
const { tableData, loading, total, page, searchParams, fetchList, handleSearch, handlePageChange } = useTable({
  listApi: (params) => api.get('/alarms/records', { params }),
  defaultParams: { alarm_level: '', status: '' },
  immediate: false,
})

// Stats + active alarms
async function fetchStats() {
  try {
    const [s, a] = await Promise.all([api.get('/alarms/stats'), api.get('/alarms/records/active')])
    stats.value = s.data; activeAlarms.value = a.data
  } catch {}
}

function showAckDialog(row) { ackRecordId = row.id; ackComment.value = ''; ackDialogVisible.value = true }

async function ackAlarm() {
  await api.post(`/alarms/records/${ackRecordId}/acknowledge`, { comment: ackComment.value })
  ElMessage.success('已确认'); ackDialogVisible.value = false; fetchStats(); fetchList()
}

async function clearAlarm(row) {
  await api.post(`/alarms/records/${row.id}/clear`); ElMessage.success('已消除'); fetchStats(); fetchList()
}

let timer = null
onMounted(() => { fetchStats(); fetchList(); timer = setInterval(fetchStats, 15000) })
onUnmounted(() => { if (timer) clearInterval(timer) })
</script>
