<template>
  <div>
    <div class="page-header">
      <h2>脚本算法</h2>
      <p>自定义数据处理脚本，对采集的原始数据进行公式计算、滤波、标定等处理</p>
    </div>

    <el-row :gutter="16">
      <!-- Script List -->
      <el-col :span="10">
        <el-card>
          <template #header>
            <div style="display:flex;justify-content:space-between;align-items:center">
              <span>脚本列表</span>
              <div>
                <el-button size="small" @click="showTemplates"><el-icon><Files /></el-icon> 模板</el-button>
                <el-button type="primary" size="small" @click="createScript"><el-icon><Plus /></el-icon> 新建</el-button>
              </div>
            </div>
          </template>
          <div v-for="s in scripts" :key="s.id" class="script-item" :class="{ active: selectedScript?.id === s.id }" @click="selectScript(s)">
            <div class="script-info">
              <span class="script-name">{{ s.name }}</span>
              <el-tag v-if="s.is_template" size="small" type="info">模板</el-tag>
              <el-tag v-if="!s.enabled" size="small" type="info">禁用</el-tag>
            </div>
            <div class="script-desc">{{ s.description || '无描述' }}</div>
            <div class="script-meta">
              <span>超时: {{ s.timeout_ms }}ms</span>
              <span>历史: {{ s.max_history }}条</span>
            </div>
          </div>
          <el-empty v-if="!scripts.length" description="暂无脚本" />
        </el-card>
      </el-col>

      <!-- Script Editor -->
      <el-col :span="14">
        <el-card v-if="selectedScript">
          <template #header>
            <div style="display:flex;justify-content:space-between;align-items:center">
              <span>{{ isEditing ? '编辑脚本' : '脚本详情' }}</span>
              <div>
                <el-button size="small" @click="testDialogVisible = true"><el-icon><CaretRight /></el-icon> 测试运行</el-button>
                <el-button type="primary" size="small" @click="saveScript">保存</el-button>
                <el-button size="small" type="danger" @click="deleteScript" v-if="!selectedScript.is_template">删除</el-button>
              </div>
            </div>
          </template>
          <el-form :model="editForm" label-width="100px">
            <el-form-item label="名称"><el-input v-model="editForm.name" /></el-form-item>
            <el-form-item label="描述"><el-input v-model="editForm.description" /></el-form-item>
            <el-form-item label="超时(ms)"><el-input-number v-model="editForm.timeout_ms" :min="100" :max="10000" style="width:200px" /></el-form-item>
            <el-form-item label="历史条数"><el-input-number v-model="editForm.max_history" :min="0" :max="1000" style="width:200px" /></el-form-item>
            <el-form-item label="默认参数">
              <el-input v-model="editForm.default_params" placeholder='{"key": "value"}' />
            </el-form-item>
            <el-form-item label="启用"><el-switch v-model="editForm.enabled" /></el-form-item>
            <el-form-item label="脚本代码">
              <el-input v-model="editForm.code" type="textarea" :rows="18" style="font-family:monospace;font-size:13px" placeholder="def process(raw_value, history, tag, context):&#10;    return raw_value" />
            </el-form-item>
          </el-form>
        </el-card>

        <!-- Empty state -->
        <el-card v-else>
          <el-empty description="选择左侧脚本查看，或新建一个">
            <el-button type="primary" @click="createScript">新建脚本</el-button>
          </el-empty>
        </el-card>
      </el-col>
    </el-row>

    <!-- Test Dialog -->
    <el-dialog v-model="testDialogVisible" title="脚本测试" width="550px">
      <el-form label-width="100px">
        <el-form-item label="原始值"><el-input-number v-model="testForm.raw_value" style="width:100%" /></el-form-item>
        <el-form-item label="历史值">
          <el-input v-model="testForm.historyStr" placeholder="逗号分隔，如: 10,20,30" />
        </el-form-item>
        <el-form-item label="脚本代码">
          <el-input v-model="editForm.code" type="textarea" :rows="10" disabled style="font-family:monospace" />
        </el-form-item>
      </el-form>
      <el-button type="primary" :loading="testing" @click="runTest" style="margin-bottom:16px">执行测试</el-button>

      <el-card v-if="testResult" shadow="never">
        <el-descriptions :column="1" border size="small">
          <el-descriptions-item label="执行状态">
            <el-tag :type="testResult.success ? 'success' : 'danger'">{{ testResult.success ? '成功' : '失败' }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="输出值">
            <span style="font-weight:bold;font-size:16px;color:#409eff">{{ testResult.value }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="质量">
            <el-tag :type="testResult.quality === 'good' ? 'success' : 'danger'" size="small">{{ testResult.quality }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item v-if="testResult.alarm" label="报警信息">
            <span style="color:#f56c6c">{{ testResult.alarm }}</span>
          </el-descriptions-item>
        </el-descriptions>
      </el-card>
    </el-dialog>

    <!-- Templates Dialog -->
    <el-dialog v-model="templatesDialogVisible" title="脚本模板" width="600px">
      <div v-for="tpl in templates" :key="tpl.id" class="template-item" @click="useTemplate(tpl)">
        <h4>{{ tpl.name }}</h4>
        <p>{{ tpl.description }}</p>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../../api/request'

const scripts = ref([])
const templates = ref([])
const selectedScript = ref(null)
const isEditing = ref(false)

const editForm = reactive({
  id: null, name: '', description: '', language: 'python', code: '',
  default_params: '{}', timeout_ms: 1000, max_history: 100, enabled: true,
})

const testDialogVisible = ref(false)
const templatesDialogVisible = ref(false)
const testing = ref(false)
const testResult = ref(null)
const testForm = reactive({ raw_value: 100, historyStr: '80,90,95' })

async function fetchScripts() {
  scripts.value = (await api.get('/scripts')).data
}

function selectScript(s) {
  selectedScript.value = s
  isEditing.value = true
  Object.assign(editForm, { ...s })
}

function createScript() {
  selectedScript.value = { id: null }
  isEditing.value = true
  Object.assign(editForm, {
    id: null, name: '', description: '', language: 'python',
    code: 'def process(raw_value, history, tag, context):\n    # raw_value: 原始采集值\n    # history: 最近N个处理后的值列表\n    # tag: {name, unit, scale_factor, offset, params}\n    # context: {device_id, tag_id, timestamp}\n    return raw_value',
    default_params: '{}', timeout_ms: 1000, max_history: 100, enabled: true,
  })
}

async function saveScript() {
  if (!editForm.name) { ElMessage.warning('请输入脚本名称'); return }
  if (!editForm.code) { ElMessage.warning('请输入脚本代码'); return }
  if (editForm.id) {
    await api.put(`/scripts/${editForm.id}`, editForm)
  } else {
    await api.post('/scripts', editForm)
  }
  ElMessage.success('保存成功')
  fetchScripts()
}

async function deleteScript() {
  await ElMessageBox.confirm(`确定删除脚本 "${editForm.name}"？`)
  await api.delete(`/scripts/${editForm.id}`)
  ElMessage.success('已删除')
  selectedScript.value = null
  fetchScripts()
}

async function runTest() {
  testing.value = true
  testResult.value = null
  try {
    const history = testForm.historyStr.split(',').map(s => parseFloat(s.trim())).filter(n => !isNaN(n))
    const res = await api.post('/scripts/test', {
      code: editForm.code,
      raw_value: testForm.raw_value,
      history: history,
      tag_config: { name: 'test', unit: '', scale_factor: 1, offset: 0, params: {} },
    })
    testResult.value = res.data
  } finally { testing.value = false }
}

async function showTemplates() {
  const res = await api.get('/scripts/templates/all')
  templates.value = res.data
  templatesDialogVisible.value = true
}

function useTemplate(tpl) {
  createScript()
  editForm.name = tpl.name
  editForm.description = tpl.description
  editForm.code = tpl.code
  editForm.default_params = tpl.default_params
  templatesDialogVisible.value = false
}

onMounted(fetchScripts)
</script>

<style scoped>
.script-item {
  padding: 12px; border-radius: 6px; margin-bottom: 8px; cursor: pointer;
  border: 1px solid #e8e8e8; transition: all 0.2s;
  &:hover { border-color: #409eff; background: #f5f7fa; }
  &.active { border-color: #409eff; background: #ecf5ff; }
}
.script-name { font-weight: 600; font-size: 14px; }
.script-desc { font-size: 12px; color: #888; margin: 4px 0; }
.script-meta { font-size: 11px; color: #aaa; display: flex; gap: 12px; }
.script-info { display: flex; align-items: center; gap: 8px; }
.template-item {
  padding: 12px; border-radius: 6px; margin-bottom: 8px; cursor: pointer;
  border: 1px solid #e8e8e8; transition: all 0.2s;
  &:hover { border-color: #409eff; background: #f5f7fa; }
  h4 { margin: 0 0 4px; font-size: 14px; }
  p { margin: 0; font-size: 12px; color: #888; }
}
</style>
