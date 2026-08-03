<script setup lang="ts">
/**
 * 图元库页面 — 适配新 svg-templates 系统
 */
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ContentWrap } from '@/components/ContentWrap'
import {
  ElRow,
  ElCol,
  ElCard,
  ElButton,
  ElTag,
  ElEmpty,
  ElMessage,
  ElMessageBox,
  ElDialog,
  ElForm,
  ElFormItem,
  ElInput,
  ElUpload
} from 'element-plus'
import { getScadaWidgets, deleteScadaWidget, uploadScadaWidget, unwrapList } from '@/api/modbus'
import { GAUGE_CATEGORIES } from './svg-templates'

defineOptions({ name: 'ScadaWidgets' })

const router = useRouter()
const loading = ref(false)
const list = ref<any[]>([])

const fetchList = async () => {
  loading.value = true
  try {
    list.value = unwrapList(await getScadaWidgets()).list
  } finally {
    loading.value = false
  }
}
const remove = async (row: any) => {
  await ElMessageBox.confirm(`确认删除图元「${row.name}」？`, '提示', { type: 'warning' })
  await deleteScadaWidget(row.id)
  ElMessage.success('删除成功')
  fetchList()
}

// 上传
const uploadDialogVisible = ref(false)
const uploadForm = ref({ name: '', category: 'custom', description: '' })
const uploadFile = ref<File | null>(null)

const beforeUpload = (file: File) => {
  uploadFile.value = file
  if (!uploadForm.value.name)
    uploadForm.value.name = file.name.replace(/\.(svg|png|jpg|jpeg)$/i, '')
  return false
}
const resetUploadForm = () => {
  uploadFile.value = null
  uploadForm.value = { name: '', category: 'custom', description: '' }
}
const doUpload = async () => {
  if (!uploadFile.value) {
    ElMessage.warning('请选择文件')
    return
  }
  const fd = new FormData()
  fd.append('file', uploadFile.value)
  fd.append('name', uploadForm.value.name)
  fd.append('category', uploadForm.value.category)
  fd.append('description', uploadForm.value.description)
  try {
    await uploadScadaWidget(fd)
    ElMessage.success('上传成功')
    uploadDialogVisible.value = false
    uploadFile.value = null
    uploadForm.value = { name: '', category: 'custom', description: '' }
    fetchList()
  } catch (e: any) {
    ElMessage.error(e?.message || '上传失败')
  }
}

onMounted(fetchList)
</script>

<template>
  <ContentWrap title="图元库">
    <template #header>
      <div class="flex-grow flex justify-end gap-8px">
        <ElButton @click="router.push('/scada/pages')">返回画面</ElButton>
        <ElButton v-hasPermi="['scada.write']" type="success" @click="uploadDialogVisible = true"
          >上传图元</ElButton
        >
      </div>
    </template>

    <!-- 内置图元 -->
    <div v-for="cat in GAUGE_CATEGORIES" :key="cat.key" class="mb-24px">
      <div class="text-16px font-700 mb-12px">{{ cat.label }}</div>
      <ElRow :gutter="16">
        <ElCol
          v-for="w in cat.defs"
          :key="w.typeTag"
          :xs="12"
          :sm="8"
          :md="6"
          :lg="4"
          class="mb-16px"
        >
          <ElCard shadow="hover" class="h-full text-center widget-preview-card">
            <div class="widget-icon-large">{{ w.icon }}</div>
            <div class="text-14px font-600 mb-4px">{{ w.label }}</div>
            <div class="text-12px text-gray-400">{{ w.defaultWidth }}×{{ w.defaultHeight }}</div>
            <div class="text-10px text-gray-500 mt-2px">{{ w.typeTag }}</div>
          </ElCard>
        </ElCol>
      </ElRow>
    </div>

    <!-- 自定义图元 -->
    <div class="text-16px font-700 mb-12px">自定义图元</div>
    <ElEmpty v-if="!loading && !list.length" description="暂无自定义图元" />
    <ElRow v-loading="loading" :gutter="16">
      <ElCol v-for="w in list" :key="w.id" :xs="12" :sm="8" :md="6" class="mb-16px">
        <ElCard shadow="hover" class="h-full">
          <div class="flex flex-col items-center text-center">
            <img
              v-if="w.thumbnail"
              :src="w.thumbnail"
              class="w-60px h-60px object-contain mb-8px"
            />
            <div class="text-14px font-600 mb-4px">{{ w.name }}</div>
            <ElTag size="small" class="mb-8px">{{ w.category || '自定义' }}</ElTag>
            <div class="text-12px text-gray-400 mb-8px">{{ w.description || '无描述' }}</div>
            <ElButton
              v-hasPermi="['scada.write']"
              link
              type="danger"
              size="small"
              @click="remove(w)"
              >删除</ElButton
            >
          </div>
        </ElCard>
      </ElCol>
    </ElRow>

    <!-- 上传对话框 -->
    <ElDialog
      v-model="uploadDialogVisible"
      title="上传自定义图元"
      width="480px"
      @close="resetUploadForm"
    >
      <ElForm label-width="80px">
        <ElFormItem label="名称"
          ><ElInput v-model="uploadForm.name" placeholder="图元名称"
        /></ElFormItem>
        <ElFormItem label="分类"
          ><ElInput v-model="uploadForm.category" placeholder="如：custom、阀门"
        /></ElFormItem>
        <ElFormItem label="描述"
          ><ElInput v-model="uploadForm.description" type="textarea" :rows="2"
        /></ElFormItem>
        <ElFormItem label="文件">
          <ElUpload
            :show-file-list="true"
            :auto-upload="false"
            :before-upload="beforeUpload"
            accept=".svg,.png,.jpg,.jpeg"
            :limit="1"
          >
            <ElButton type="primary">选择文件</ElButton>
            <template #tip
              ><div class="text-12px text-gray-400">支持 SVG / PNG / JPG 格式</div></template
            >
          </ElUpload>
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="uploadDialogVisible = false">取消</ElButton>
        <ElButton type="primary" @click="doUpload">上传</ElButton>
      </template>
    </ElDialog>
  </ContentWrap>
</template>

<style scoped>
.widget-icon-large {
  font-size: 36px;
  line-height: 1;
  margin-bottom: 4px;
}
.widget-preview-card {
  min-height: 140px;
}
</style>
