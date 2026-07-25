<script setup lang="ts">
import { ref } from 'vue'
import { ContentWrap } from '@/components/ContentWrap'
import { ElRow, ElCol, ElCard, ElButton, ElMessage } from 'element-plus'
import { Icon } from '@/components/Icon'
import {
  exportDevicesCsv,
  exportAlarmsCsv,
  exportHistoryCsv,
  exportDailyReport
} from '@/api/modbus'

defineOptions({ name: 'Exports' })

const downloadBlob = (data: any, filename: string) => {
  const blob = data instanceof Blob ? data : new Blob([data])
  const url = window.URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  window.URL.revokeObjectURL(url)
}

const busy = ref('')
const run = async (key: string, fn: () => Promise<any>, filename: string) => {
  busy.value = key
  try {
    const res: any = await fn()
    downloadBlob(res?.data ?? res, filename)
    ElMessage.success('导出成功')
  } catch (e: any) {
    ElMessage.error(e?.message || '导出失败')
  } finally {
    busy.value = ''
  }
}

const ts = () => new Date().toISOString().slice(0, 10)

const items = [
  {
    key: 'devices',
    title: '设备清单',
    desc: '导出全部设备基础信息 CSV',
    icon: 'vi-ant-design:hdd-outlined',
    color: '#409eff',
    fn: () => run('devices', exportDevicesCsv, `devices-${ts()}.csv`)
  },
  {
    key: 'alarms',
    title: '报警记录',
    desc: '导出报警历史记录 CSV',
    icon: 'vi-ant-design:alert-outlined',
    color: '#f56c6c',
    fn: () => run('alarms', () => exportAlarmsCsv(), `alarms-${ts()}.csv`)
  },
  {
    key: 'history',
    title: '历史数据',
    desc: '导出采集历史数据 CSV',
    icon: 'vi-ant-design:line-chart-outlined',
    color: '#67c23a',
    fn: () => run('history', () => exportHistoryCsv(), `history-${ts()}.csv`)
  },
  {
    key: 'report',
    title: '日报报表',
    desc: '导出当日运行日报',
    icon: 'vi-ant-design:file-text-outlined',
    color: '#e6a23c',
    fn: () => run('report', () => exportDailyReport(), `daily-report-${ts()}.csv`)
  }
]
</script>

<template>
  <ContentWrap title="数据导出" message="按需导出平台数据为 CSV / 报表文件">
    <ElRow :gutter="16">
      <ElCol v-for="it in items" :key="it.key" :xs="24" :sm="12" :md="6" class="mb-16px">
        <ElCard shadow="hover" class="h-full">
          <div class="flex flex-col items-center text-center py-8px">
            <div
              class="w-56px h-56px rounded-8px flex items-center justify-center mb-12px"
              :style="{ background: it.color + '1a' }"
            >
              <Icon :icon="it.icon" :size="28" :color="it.color" />
            </div>
            <div class="text-16px font-700 mb-6px">{{ it.title }}</div>
            <div class="text-12px text-gray-400 mb-14px min-h-32px">{{ it.desc }}</div>
            <ElButton
              v-hasPermi="['export.download']"
              type="primary"
              :loading="busy === it.key"
              @click="it.fn()"
            >
              导出
            </ElButton>
          </div>
        </ElCard>
      </ElCol>
    </ElRow>
  </ContentWrap>
</template>
