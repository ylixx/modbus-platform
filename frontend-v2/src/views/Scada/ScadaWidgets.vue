<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
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
  ElUpload,
  ElSelect,
  ElOption
} from 'element-plus'
import { getScadaWidgets, updateScadaWidget, deleteScadaWidget, uploadScadaWidget, unwrapList } from '@/api/modbus'
import { svgWidgetCategories, getSvgWidgetsByCategory } from './widgets/svg-widgets'

defineOptions({ name: 'ScadaWidgets' })

const router = useRouter()
const loading = ref(false)
const list = ref<any[]>([])
const filterCategory = ref('')
const categories = ref<string[]>([])

const filteredList = computed(() => {
  if (!filterCategory.value) return list.value
  return list.value.filter((w) => w.category === filterCategory.value)
})

const fetchList = async () => {
  loading.value = true
  try {
    list.value = unwrapList(await getScadaWidgets()).list
    categories.value = [...new Set(list.value.map((w) => w.category).filter(Boolean))] as string[]
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
  if (!uploadForm.value.name) {
    uploadForm.value.name = file.name.replace(/\.(svg|png|jpg|jpeg)$/i, '')
  }
  return false // 阻止自动上传
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

// 编辑（SVG 源可直接改 data-bind-target 等绑定域标记）
const editDialogVisible = ref(false)
const editForm = ref<any>({ id: 0, name: '', category: '', description: '', source_data: '', source_type: '' })

const openEdit = (row: any) => {
  editForm.value = { ...row }
  editDialogVisible.value = true
}

const saveEdit = async () => {
  try {
    await updateScadaWidget(editForm.value.id, {
      name: editForm.value.name,
      category: editForm.value.category,
      description: editForm.value.description,
      source_data: editForm.value.source_data
    })
    ElMessage.success('保存成功')
    editDialogVisible.value = false
    fetchList()
  } catch (e: any) {
    ElMessage.error(e?.message || '保存失败')
  }
}

onMounted(fetchList)
</script>

<template>
  <ContentWrap title="图元库">
    <template #header>
      <div class="flex-grow flex justify-end gap-8px">
        <ElButton @click="router.push('/scada/pages')">返回画面</ElButton>
        <ElButton
          v-hasPermi="['scada.write']"
          type="success"
          @click="uploadDialogVisible = true"
        >
          上传图元
        </ElButton>
      </div>
    </template>

    <!-- 内置图元（SVG 缩略图） -->
    <div class="text-16px font-700 mb-12px">内置工业图元</div>
    <ElRow :gutter="16" class="mb-24px">
      <template v-for="cat in svgWidgetCategories()" :key="cat">
        <ElCol :span="24" class="mb-8px">
          <div class="text-14px font-600 text-gray-500">{{ cat }}</div>
        </ElCol>
        <ElCol
          v-for="w in getSvgWidgetsByCategory(cat)"
          :key="w.name"
          :xs="12"
          :sm="8"
          :md="6"
          :lg="4"
          class="mb-16px"
        >
          <ElCard shadow="hover" class="h-full text-center widget-preview-card">
            <div class="svg-thumb-wrap mb-8px" v-html="w.thumbnail"></div>
            <div class="text-14px font-600 mb-4px">{{ w.name }}</div>
            <div class="text-12px text-gray-400">{{ w.defaultWidth }}×{{ w.defaultHeight }}</div>
            <div class="text-10px text-gray-500 mt-2px">{{ w.typeTag }}</div>
          </ElCard>
        </ElCol>
      </template>
    </ElRow>

    <!-- 自定义图元 -->
    <div class="flex items-center justify-between mb-12px">
      <div class="text-16px font-700">自定义图元</div>
      <el-select
        v-if="categories.length"
        v-model="filterCategory"
        placeholder="全部分类"
        clearable
        size="small"
        class="w-160px"
      >
        <el-option v-for="c in categories" :key="c" :label="c" :value="c" />
      </el-select>
    </div>
    <ElEmpty v-if="!loading && !list.length" description="暂无自定义图元" />
    <ElEmpty v-else-if="!loading && !filteredList.length" description="该分类下暂无图元" />
    <ElRow v-loading="loading" :gutter="16">
      <ElCol v-for="w in filteredList" :key="w.id" :xs="12" :sm="8" :md="6" class="mb-16px">
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
            <div class="flex gap-8px">
              <ElButton
                v-hasPermi="['scada.write']"
                link
                type="primary"
                size="small"
                @click="openEdit(w)"
              >
                编辑
              </ElButton>
              <ElButton
                v-hasPermi="['scada.write']"
                link
                type="danger"
                size="small"
                @click="remove(w)"
              >
                删除
              </ElButton>
            </div>
          </div>
        </ElCard>
      </ElCol>
    </ElRow>

    <!-- 上传对话框 -->
    <ElDialog v-model="uploadDialogVisible" title="上传自定义图元" width="480px" @close="resetUploadForm">
      <ElForm label-width="80px">
        <ElFormItem label="名称">
          <ElInput v-model="uploadForm.name" placeholder="图元名称" />
        </ElFormItem>
        <ElFormItem label="分类">
          <ElInput v-model="uploadForm.category" placeholder="如：custom、阀门" />
        </ElFormItem>
        <ElFormItem label="描述">
          <ElInput v-model="uploadForm.description" type="textarea" :rows="2" />
        </ElFormItem>
        <ElFormItem label="文件">
          <ElUpload
            :show-file-list="true"
            :auto-upload="false"
            :before-upload="beforeUpload"
            accept=".svg,.png,.jpg,.jpeg"
            :limit="1"
          >
            <ElButton type="primary">选择文件</ElButton>
            <template #tip>
              <div class="text-12px text-gray-400">支持 SVG / PNG / JPG 格式</div>
            </template>
          </ElUpload>
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="uploadDialogVisible = false">取消</ElButton>
        <ElButton type="primary" @click="doUpload">上传</ElButton>
      </template>
    </ElDialog>

    <!-- 编辑对话框 -->
    <ElDialog v-model="editDialogVisible" title="编辑图元" width="560px" @close="editDialogVisible = false">
      <ElForm label-width="80px">
        <ElFormItem label="名称">
          <ElInput v-model="editForm.name" />
        </ElFormItem>
        <ElFormItem label="分类">
          <ElInput v-model="editForm.category" placeholder="如：custom、阀门" />
        </ElFormItem>
        <ElFormItem label="描述">
          <ElInput v-model="editForm.description" type="textarea" :rows="2" />
        </ElFormItem>
        <ElFormItem v-if="editForm.source_type === 'svg'" label="SVG 源">
          <ElInput
            v-model="editForm.source_data"
            type="textarea"
            :rows="10"
            class="font-mono text-12px"
            placeholder="在元素上添加 data-bind-target / data-bind-prop 标记以支持绑定"
          />
          <div class="text-12px text-gray-400 mt-4px">
            绑定域标记：如 <code>&lt;text data-bind-target="text" data-bind-prop="text"&gt;</code>
          </div>
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="editDialogVisible = false">取消</ElButton>
        <ElButton type="primary" @click="saveEdit">保存</ElButton>
      </template>
    </ElDialog>
  </ContentWrap>
</template>

<style scoped>
.svg-thumb-wrap {
  width: 80px;
  height: 80px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto;
  background: #0d1117;
  border-radius: 4px;
  padding: 4px;
}
.svg-thumb-wrap :deep(svg) {
  max-width: 70px;
  max-height: 70px;
}
.widget-preview-card {
  min-height: 140px;
}
</style>
