<template>
  <div>
    <div class="page-header">
      <h2>批量导入</h2>
      <p>通过 CSV 文件批量导入设备和采集点位</p>
    </div>

    <el-row :gutter="20">
      <!-- Device Import -->
      <el-col :span="12">
        <el-card>
          <template #header>
            <div style="display:flex;justify-content:space-between;align-items:center">
              <span>导入设备</span>
              <el-button size="small" @click="downloadTemplate('devices')"><el-icon><Download /></el-icon> 下载模板</el-button>
            </div>
          </template>
          <el-upload
            drag
            :action="importDevicesUrl"
            :headers="uploadHeaders"
            :on-success="onDeviceImportSuccess"
            :on-error="onImportError"
            accept=".csv"
            :limit="1"
          >
            <el-icon size="40"><Upload /></el-icon>
            <div style="margin-top:8px">拖拽 CSV 文件到此处，或<em>点击上传</em></div>
            <template #tip>
              <div style="font-size:12px;color:#999;margin-top:8px">
                CSV 格式：name, protocol, host, port, slave_id, poll_interval, factory, workshop, production_line, installation, description
              </div>
            </template>
          </el-upload>
          <div v-if="deviceResult" style="margin-top:16px">
            <el-alert :type="deviceResult.errors?.length ? 'warning' : 'success'" :closable="false">
              <template #title>
                <span>导入完成：成功 <b>{{ deviceResult.created }}</b> 条</span>
                <span v-if="deviceResult.errors?.length">，失败 {{ deviceResult.errors.length }} 条</span>
              </template>
            </el-alert>
            <div v-if="deviceResult.errors?.length" style="margin-top:8px;max-height:150px;overflow-y:auto">
              <div v-for="(err, i) in deviceResult.errors" :key="i" style="font-size:12px;color:#f56c6c;padding:2px 0">{{ err }}</div>
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- Tag Import -->
      <el-col :span="12">
        <el-card>
          <template #header>
            <div style="display:flex;justify-content:space-between;align-items:center">
              <span>导入点位</span>
              <el-button size="small" @click="downloadTemplate('tags')"><el-icon><Download /></el-icon> 下载模板</el-button>
            </div>
          </template>
          <el-upload
            drag
            :action="importTagsUrl"
            :headers="uploadHeaders"
            :on-success="onTagImportSuccess"
            :on-error="onImportError"
            accept=".csv"
            :limit="1"
          >
            <el-icon size="40"><Upload /></el-icon>
            <div style="margin-top:8px">拖拽 CSV 文件到此处，或<em>点击上传</em></div>
            <template #tip>
              <div style="font-size:12px;color:#999;margin-top:8px">
                CSV 格式：device_name, name, function_code, address, data_type, byte_order, scale_factor, offset, decimal_places, unit, writable, description
              </div>
            </template>
          </el-upload>
          <div v-if="tagResult" style="margin-top:16px">
            <el-alert :type="tagResult.errors?.length ? 'warning' : 'success'" :closable="false">
              <template #title>
                <span>导入完成：成功 <b>{{ tagResult.created }}</b> 条</span>
                <span v-if="tagResult.errors?.length">，失败 {{ tagResult.errors.length }} 条</span>
              </template>
            </el-alert>
            <div v-if="tagResult.errors?.length" style="margin-top:8px;max-height:150px;overflow-y:auto">
              <div v-for="(err, i) in tagResult.errors" :key="i" style="font-size:12px;color:#f56c6c;padding:2px 0">{{ err }}</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Tips -->
    <el-card header="导入说明" style="margin-top:20px">
      <el-descriptions :column="1" border size="small">
        <el-descriptions-item label="编码">UTF-8（推荐）或 GBK</el-descriptions-item>
        <el-descriptions-item label="设备导入">设备名不可重复，protocol 默认 modbus_tcp</el-descriptions-item>
        <el-descriptions-item label="点位导入">device_name 必须是已存在的设备名</el-descriptions-item>
        <el-descriptions-item label="可写字段">writable 列填 true/1/yes/是 表示可写</el-descriptions-item>
        <el-descriptions-item label="冲突处理">同名设备/点位将跳过并报错</el-descriptions-item>
      </el-descriptions>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { downloadBlob } from '../../utils'
import api from '../../api/request'

const importDevicesUrl = '/api/v1/import/devices'
const importTagsUrl = '/api/v1/import/tags'
const uploadHeaders = computed(() => ({ Authorization: `Bearer ${localStorage.getItem('token')}` }))

const deviceResult = ref(null)
const tagResult = ref(null)

function onDeviceImportSuccess(res) {
  deviceResult.value = res
  if (res.created > 0) ElMessage.success(`成功导入 ${res.created} 台设备`)
}

function onTagImportSuccess(res) {
  tagResult.value = res
  if (res.created > 0) ElMessage.success(`成功导入 ${res.created} 个点位`)
}

function onImportError() {
  ElMessage.error('上传失败，请检查文件格式')
}

async function downloadTemplate(type) {
  const res = await api.get(`/import/template/${type}`, { responseType: 'blob' })
  downloadBlob(res.data, `${type}_template.csv`)
}
</script>
