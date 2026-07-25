<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ContentWrap } from '@/components/ContentWrap'
import {
  ElRow,
  ElCol,
  ElCard,
  ElStatistic,
  ElForm,
  ElFormItem,
  ElInputNumber,
  ElSwitch,
  ElButton,
  ElMessage,
  ElMessageBox
} from 'element-plus'
import {
  getArchiveConfig,
  getArchiveStats,
  updateArchiveConfig,
  runArchive,
  cleanArchive,
  unwrap
} from '@/api/modbus'

defineOptions({ name: 'Archive' })

const stats = ref<any>({})
const config = reactive<any>({
  retention_days: 90,
  auto_archive: false,
  archive_interval_hours: 24
})
const loading = ref(false)

const fetchAll = async () => {
  try {
    stats.value = unwrap(await getArchiveStats()) || {}
  } catch (e) {
    // ignore
  }
  try {
    const c = unwrap(await getArchiveConfig())
    if (c) Object.assign(config, c)
  } catch (e) {
    // ignore
  }
}

const saveConfig = async () => {
  loading.value = true
  try {
    await updateArchiveConfig({ ...config })
    ElMessage.success('配置已保存')
  } finally {
    loading.value = false
  }
}
const doRun = async () => {
  await ElMessageBox.confirm('确认立即执行一次归档任务？', '提示', { type: 'warning' })
  await runArchive()
  ElMessage.success('归档任务已触发')
  fetchAll()
}
const doClean = async () => {
  await ElMessageBox.confirm('确认清理过期历史数据？此操作不可恢复！', '危险操作', {
    type: 'warning'
  })
  await cleanArchive()
  ElMessage.success('清理任务已触发')
  fetchAll()
}

onMounted(fetchAll)
</script>

<template>
  <div>
    <ElRow :gutter="16" class="mb-8px">
      <ElCol :xs="12" :md="6" class="mb-16px">
        <ElCard shadow="hover"
          ><ElStatistic title="历史记录总数" :value="stats.total_records || 0"
        /></ElCard>
      </ElCol>
      <ElCol :xs="12" :md="6" class="mb-16px">
        <ElCard shadow="hover"
          ><ElStatistic title="已归档记录" :value="stats.archived_records || 0"
        /></ElCard>
      </ElCol>
      <ElCol :xs="12" :md="6" class="mb-16px">
        <ElCard shadow="hover"
          ><ElStatistic title="数据库大小(MB)" :value="stats.db_size_mb || 0"
        /></ElCard>
      </ElCol>
      <ElCol :xs="12" :md="6" class="mb-16px">
        <ElCard shadow="hover"
          ><ElStatistic title="最早数据天数" :value="stats.oldest_days || 0"
        /></ElCard>
      </ElCol>
    </ElRow>

    <ContentWrap title="归档配置">
      <ElForm :model="config" label-width="140px" class="max-w-560px">
        <ElFormItem label="数据保留天数">
          <ElInputNumber v-model="config.retention_days" :min="1" :max="3650" />
        </ElFormItem>
        <ElFormItem label="自动归档">
          <ElSwitch v-model="config.auto_archive" />
        </ElFormItem>
        <ElFormItem label="归档间隔(小时)">
          <ElInputNumber v-model="config.archive_interval_hours" :min="1" :max="720" />
        </ElFormItem>
        <ElFormItem>
          <ElButton
            v-hasPermi="['config.write']"
            type="primary"
            :loading="loading"
            @click="saveConfig"
            >保存配置</ElButton
          >
          <ElButton v-hasPermi="['config.write']" @click="doRun">立即归档</ElButton>
          <ElButton v-hasPermi="['config.write']" type="danger" @click="doClean"
            >清理过期数据</ElButton
          >
        </ElFormItem>
      </ElForm>
    </ContentWrap>
  </div>
</template>
