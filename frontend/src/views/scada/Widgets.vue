<template>
  <div>
    <div class="page-header">
      <h2>自定义图元</h2>
      <p>上传 SVG / PNG 图元，在 SCADA 编辑器中使用</p>
    </div>

    <el-card style="margin-bottom:16px">
      <el-row :gutter="16" align="middle">
        <el-col :span="6">
          <el-select v-model="filterCategory" placeholder="分类筛选" clearable @change="fetchWidgets">
            <el-option label="自定义" value="custom" />
            <el-option label="容器" value="tank" />
            <el-option label="阀门" value="valve" />
            <el-option label="电机" value="motor" />
            <el-option label="管道" value="pipe" />
            <el-option label="仪表" value="gauge" />
            <el-option label="指示" value="indicator" />
            <el-option label="控件" value="button" />
            <el-option label="其他" value="other" />
          </el-select>
        </el-col>
        <el-col :span="18" style="text-align:right">
          <el-upload
            :action="uploadUrl"
            :headers="uploadHeaders"
            :data="uploadData"
            :on-success="onUploadSuccess"
            :before-upload="beforeUpload"
            multiple
            accept=".svg,.png,.jpg,.jpeg"
            :show-file-list="false"
            style="display:inline-block;margin-right:8px"
          >
            <el-button type="primary"><el-icon><Upload /></el-icon> 上传图元</el-button>
          </el-upload>
          <el-upload
            :action="batchUploadUrl"
            :headers="uploadHeaders"
            :data="{ category: 'custom' }"
            :on-success="onBatchUploadSuccess"
            multiple
            accept=".svg,.png,.jpg,.jpeg"
            :show-file-list="false"
            style="display:inline-block"
          >
            <el-button><el-icon><UploadFilled /></el-icon> 批量上传</el-button>
          </el-upload>
        </el-col>
      </el-row>
    </el-card>

    <el-card>
      <div class="widget-grid">
        <div v-for="w in widgets" :key="w.id" class="widget-card">
          <div class="widget-preview">
            <img v-if="w.thumbnail" :src="w.thumbnail" />
            <div v-else class="no-preview">无预览</div>
          </div>
          <div class="widget-info">
            <div class="widget-name">{{ w.name }}</div>
            <div class="widget-meta">
              <el-tag size="small">{{ w.source_type.toUpperCase() }}</el-tag>
              <span>{{ w.default_width }}×{{ w.default_height }}</span>
            </div>
          </div>
          <div class="widget-actions">
            <el-button size="small" @click="showEditDialog(w)">编辑</el-button>
            <el-button size="small" type="danger" @click="deleteWidget(w)">删除</el-button>
          </div>
        </div>

        <!-- Upload card -->
        <div class="widget-card upload-card" @click="triggerUpload">
          <el-icon size="40"><Plus /></el-icon>
          <div>上传图元</div>
        </div>
      </div>

      <el-empty v-if="!widgets.length && !loading" description="暂无自定义图元" />
    </el-card>

    <!-- Edit Dialog -->
    <el-dialog v-model="editDialogVisible" title="编辑图元" width="500px">
      <el-form :model="editForm" label-width="80px">
        <el-form-item label="名称"><el-input v-model="editForm.name" /></el-form-item>
        <el-form-item label="分类">
          <el-select v-model="editForm.category">
            <el-option label="自定义" value="custom" />
            <el-option label="容器" value="tank" />
            <el-option label="阀门" value="valve" />
            <el-option label="电机" value="motor" />
            <el-option label="管道" value="pipe" />
            <el-option label="仪表" value="gauge" />
            <el-option label="指示" value="indicator" />
            <el-option label="控件" value="button" />
            <el-option label="其他" value="other" />
          </el-select>
        </el-form-item>
        <el-form-item label="描述"><el-input v-model="editForm.description" /></el-form-item>
        <el-form-item label="宽度"><el-input-number v-model="editForm.default_width" :min="10" /></el-form-item>
        <el-form-item label="高度"><el-input-number v-model="editForm.default_height" :min="10" /></el-form-item>
        <el-form-item label="可绑定">
          <el-checkbox-group v-model="editForm.bindable">
            <el-checkbox value="text">文本</el-checkbox>
            <el-checkbox value="value">数值</el-checkbox>
            <el-checkbox value="state">状态</el-checkbox>
            <el-checkbox value="fill">颜色</el-checkbox>
            <el-checkbox value="liquidLevel">液位</el-checkbox>
            <el-checkbox value="flow">流量</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
        <el-form-item label="预览">
          <div style="background:#111;padding:12px;border-radius:6px;text-align:center">
            <img v-if="editForm.thumbnail" :src="editForm.thumbnail" style="max-height:120px" />
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveWidget">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../../api/request'

const widgets = ref([])
const loading = ref(false)
const filterCategory = ref(null)
const editDialogVisible = ref(false)
const editingId = ref(null)
const editForm = reactive({ name: '', category: 'custom', description: '', default_width: 100, default_height: 100, bindable: ['text', 'value', 'state'], thumbnail: '' })

const uploadUrl = '/api/v1/scada/widgets/upload'
const batchUploadUrl = '/api/v1/scada/widgets/batch-upload'
const uploadHeaders = computed(() => ({ Authorization: `Bearer ${localStorage.getItem('token')}` }))
const uploadData = reactive({ name: '', category: 'custom' })

async function fetchWidgets() {
  loading.value = true
  try {
    const res = await api.get('/scada/widgets', { params: { enabled_only: true } })
    widgets.value = filterCategory.value
      ? res.data.filter(w => w.category === filterCategory.value)
      : res.data
  } finally { loading.value = false }
}

function beforeUpload(file) {
  const ok = file.name.toLowerCase().endsWith('.svg') || /\.(png|jpg|jpeg)$/.test(file.name.toLowerCase())
  if (!ok) ElMessage.error('仅支持 SVG / PNG / JPG')
  uploadData.name = file.name.replace(/\.[^.]+$/, '')
  return ok
}

function onUploadSuccess(res) {
  ElMessage.success(`图元 "${res.name}" 上传成功`)
  fetchWidgets()
}

function onBatchUploadSuccess(res) {
  ElMessage.success(`批量上传 ${res.count} 个图元`)
  fetchWidgets()
}

function triggerUpload() { document.querySelector('.el-upload input')?.click() }

function showEditDialog(w) {
  editingId.value = w.id
  Object.assign(editForm, {
    name: w.name, category: w.category, description: w.description,
    default_width: w.default_width, default_height: w.default_height,
    bindable: w.bindable || [], thumbnail: w.thumbnail,
  })
  editDialogVisible.value = true
}

async function saveWidget() {
  await api.put(`/scada/widgets/${editingId.value}`, editForm)
  ElMessage.success('保存成功')
  editDialogVisible.value = false
  fetchWidgets()
}

async function deleteWidget(w) {
  await ElMessageBox.confirm(`确定删除图元 "${w.name}"？`)
  await api.delete(`/scada/widgets/${w.id}`)
  ElMessage.success('已删除')
  fetchWidgets()
}

onMounted(fetchWidgets)
</script>

<style scoped lang="scss">
.widget-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 16px;
}
.widget-card {
  background: #161b22; border: 1px solid #30363d; border-radius: 8px;
  overflow: hidden; transition: all 0.2s;
  &:hover { border-color: #58a6ff; }
}
.widget-preview {
  height: 120px; display: flex; align-items: center; justify-content: center;
  background: #0d1117; padding: 8px;
  img { max-width: 100%; max-height: 100%; object-fit: contain; }
  .no-preview { color: #555; font-size: 12px; }
}
.widget-info { padding: 8px 12px; }
.widget-name { font-size: 14px; font-weight: 500; margin-bottom: 4px; }
.widget-meta { display: flex; align-items: center; gap: 8px; font-size: 12px; color: #8b949e; }
.widget-actions { padding: 8px 12px; display: flex; gap: 8px; border-top: 1px solid #21262d; }
.upload-card {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  min-height: 200px; cursor: pointer; border-style: dashed; color: #58a6ff;
  &:hover { background: #1c2333; }
}
</style>
