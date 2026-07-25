<script setup lang="ts">
import { ContentWrap } from '@/components/ContentWrap'
import { ElRow, ElCol, ElCard, ElButton, ElUpload, ElMessage } from 'element-plus'
import {
  importDevices,
  importTags,
  getImportTemplateDevices,
  getImportTemplateTags
} from '@/api/modbus'

defineOptions({ name: 'Imports' })

const downloadBlob = (data: any, filename: string) => {
  const blob = data instanceof Blob ? data : new Blob([data])
  const url = window.URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  window.URL.revokeObjectURL(url)
}

const dlTpl = async (type: string) => {
  try {
    const res: any =
      type === 'devices' ? await getImportTemplateDevices() : await getImportTemplateTags()
    downloadBlob(res?.data ?? res, `${type}-template.csv`)
  } catch (e: any) {
    ElMessage.error(e?.message || '下载失败')
  }
}

const uploadReq = (fn: (data: any) => Promise<any>) => async (opt: any) => {
  const fd = new FormData()
  fd.append('file', opt.file)
  try {
    const res = await fn(fd)
    const body = (res as any)?.data
    ElMessage.success(`导入完成：成功 ${body?.success ?? body?.imported ?? '—'} 条`)
    opt.onSuccess?.(body)
  } catch (e: any) {
    ElMessage.error(e?.message || '导入失败')
    opt.onError?.(e)
  }
}
</script>

<template>
  <ContentWrap title="批量导入" message="先下载模板，按格式填写后上传 CSV 文件">
    <ElRow :gutter="16">
      <ElCol :xs="24" :md="12" class="mb-16px">
        <ElCard shadow="never" class="h-full">
          <div class="text-16px font-700 mb-12px">设备批量导入</div>
          <div class="text-12px text-gray-400 mb-14px">支持一次性导入多台设备的连接信息</div>
          <div class="flex items-center gap-12px">
            <ElButton @click="dlTpl('devices')">下载模板</ElButton>
            <ElUpload
              :show-file-list="false"
              accept=".csv"
              :http-request="uploadReq(importDevices)"
            >
              <ElButton v-hasPermi="['import.write']" type="primary">上传设备文件</ElButton>
            </ElUpload>
          </div>
        </ElCard>
      </ElCol>
      <ElCol :xs="24" :md="12" class="mb-16px">
        <ElCard shadow="never" class="h-full">
          <div class="text-16px font-700 mb-12px">点位批量导入</div>
          <div class="text-12px text-gray-400 mb-14px">支持批量导入采集点位（寄存器）配置</div>
          <div class="flex items-center gap-12px">
            <ElButton @click="dlTpl('tags')">下载模板</ElButton>
            <ElUpload :show-file-list="false" accept=".csv" :http-request="uploadReq(importTags)">
              <ElButton v-hasPermi="['import.write']" type="primary">上传点位文件</ElButton>
            </ElUpload>
          </div>
        </ElCard>
      </ElCol>
    </ElRow>
  </ContentWrap>
</template>
