<template>
  <div>
    <div class="page-header">
      <h2>数据归档</h2>
      <p>配置数据保留策略，管理历史数据清理</p>
    </div>

    <el-row :gutter="20">
      <!-- Config -->
      <el-col :span="14">
        <el-card header="归档策略配置">
          <el-form label-width="140px">
            <el-form-item label="启用自动归档">
              <el-switch v-model="config['archive.enabled']" @change="saveConfig('archive.enabled', config['archive.enabled'])" />
              <span style="font-size:12px;color:#999;margin-left:8px">每天凌晨 3:00 自动执行</span>
            </el-form-item>

            <el-divider content-position="left">保留天数设置</el-divider>

            <el-form-item label="历史数据">
              <el-input-number v-model="config['archive.history_days']" :min="1" :max="3650" style="width:200px" />
              <span style="font-size:12px;color:#999;margin-left:12px">原始采集数据（默认 7 天）</span>
            </el-form-item>

            <el-form-item label="报警记录">
              <el-input-number v-model="config['archive.alarm_days']" :min="1" :max="3650" style="width:200px" />
              <span style="font-size:12px;color:#999;margin-left:12px">已消除的报警记录（默认 365 天）</span>
            </el-form-item>

            <el-form-item label="短信记录">
              <el-input-number v-model="config['archive.sms_days']" :min="1" :max="3650" style="width:200px" />
              <span style="font-size:12px;color:#999;margin-left:12px">短信发送记录（默认 90 天）</span>
            </el-form-item>

            <el-form-item label="审计日志">
              <el-input-number v-model="config['archive.audit_days']" :min="1" :max="3650" style="width:200px" />
              <span style="font-size:12px;color:#999;margin-left:12px">操作审计日志（默认 365 天）</span>
            </el-form-item>

            <el-form-item>
              <el-button type="primary" :loading="saving" @click="saveAll">保存全部设置</el-button>
              <el-button @click="fetchConfig">重置</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <!-- Stats -->
      <el-col :span="10">
        <el-card header="当前数据量" style="margin-bottom:16px">
          <el-descriptions :column="1" border size="small">
            <el-descriptions-item label="历史数据">
              <span style="font-weight:bold">{{ stats.tag_history?.toLocaleString() || 0 }}</span> 条
            </el-descriptions-item>
            <el-descriptions-item label="最早记录">
              {{ stats.tag_history_oldest || 'N/A' }}
            </el-descriptions-item>
            <el-descriptions-item label="报警记录">
              <span style="font-weight:bold">{{ stats.alarm_records?.toLocaleString() || 0 }}</span> 条
            </el-descriptions-item>
            <el-descriptions-item label="短信记录">
              <span style="font-weight:bold">{{ stats.sms_records?.toLocaleString() || 0 }}</span> 条
            </el-descriptions-item>
            <el-descriptions-item label="审计日志">
              <span style="font-weight:bold">{{ stats.audit_logs?.toLocaleString() || 0 }}</span> 条
            </el-descriptions-item>
          </el-descriptions>
        </el-card>

        <el-card header="手动操作">
          <el-button type="warning" :loading="archiving" @click="runArchive" style="width:100%">
            <el-icon><Delete /></el-icon> 立即执行归档
          </el-button>
          <div style="font-size:12px;color:#999;margin-top:8px">
            按照上方配置的保留天数清理过期数据
          </div>

          <el-divider />

          <el-alert type="info" :closable="false">
            <template #title>
              <div style="font-size:13px">
                <p><strong>归档策略说明：</strong></p>
                <p>• 历史数据：超过保留天数的原始采集数据将被删除</p>
                <p>• 报警记录：仅删除已"消除"状态的报警</p>
                <p>• 短信记录：超过保留天数的发送记录</p>
                <p>• 审计日志：超过保留天数的操作记录</p>
                <p style="margin-top:8px;color:#e6a23c">⚠️ 删除后不可恢复，建议保留足够的天数</p>
              </div>
            </template>
          </el-alert>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../../api/request'

const config = reactive({
  'archive.enabled': true,
  'archive.history_days': 7,
  'archive.alarm_days': 365,
  'archive.sms_days': 90,
  'archive.audit_days': 365,
})
const stats = ref({})
const saving = ref(false)
const archiving = ref(false)

async function fetchConfig() {
  const res = await api.get('/archive/config')
  for (const [key, meta] of Object.entries(res.data)) {
    config[key] = meta.value
  }
}

async function fetchStats() {
  stats.value = (await api.get('/archive/stats')).data
}

async function saveConfig(key, value) {
  await api.put('/archive/config', { key, value })
}

async function saveAll() {
  saving.value = true
  try {
    await api.put('/archive/config/batch', {
      history_days: config['archive.history_days'],
      alarm_days: config['archive.alarm_days'],
      sms_days: config['archive.sms_days'],
      audit_days: config['archive.audit_days'],
      enabled: config['archive.enabled'],
    })
    ElMessage.success('归档策略已保存')
  } finally { saving.value = false }
}

async function runArchive() {
  await ElMessageBox.confirm('确定立即执行归档？将按照配置的保留天数清理过期数据。', '确认', { type: 'warning' })
  archiving.value = true
  try {
    const res = await api.post('/archive/run')
    ElMessage.success(res.data.message)
    fetchStats()
  } finally { archiving.value = false }
}

onMounted(() => { fetchConfig(); fetchStats() })
</script>
