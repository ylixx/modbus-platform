<template>
  <div>
    <div class="page-header">
      <h2>设备模板</h2>
      <p>从预定义模板快速创建设备，一键生成全部采集点位</p>
    </div>

    <el-row :gutter="16">
      <el-col :span="6" v-for="tpl in templates" :key="tpl.id">
        <el-card class="template-card" @click="showCreateDialog(tpl)">
          <div class="tpl-header">
            <span class="tpl-icon">{{ categoryIcon(tpl.category) }}</span>
            <el-tag size="small">{{ tpl.category }}</el-tag>
          </div>
          <h3>{{ tpl.name }}</h3>
          <p class="tpl-desc">{{ tpl.description }}</p>
          <div class="tpl-meta">
            <span>{{ tpl.protocol.toUpperCase() }}</span>
            <span>{{ tpl.tags?.length || 0 }} 个点位</span>
          </div>
          <el-button type="primary" size="small" style="width:100%;margin-top:12px">使用此模板</el-button>
        </el-card>
      </el-col>
    </el-row>

    <!-- Create Dialog -->
    <el-dialog v-model="dialogVisible" :title="`从模板创建设备: ${selectedTpl?.name}`" width="500px">
      <el-form :model="createForm" label-width="100px">
        <el-form-item label="设备名称" required>
          <el-input v-model="createForm.name" :placeholder="selectedTpl?.name" />
        </el-form-item>
        <el-form-item :label="selectedTpl?.protocol === 'mqtt' ? 'Broker地址' : selectedTpl?.protocol === 'opc_ua' ? 'Endpoint' : '主机地址'">
          <el-input v-model="createForm.host" :placeholder="hostPlaceholder" />
        </el-form-item>
        <el-form-item label="厂区"><el-input v-model="createForm.factory" placeholder="选填" /></el-form-item>
        <el-form-item label="车间"><el-input v-model="createForm.workshop" placeholder="选填" /></el-form-item>
      </el-form>

      <el-divider content-position="left">预置点位 ({{ selectedTpl?.tags?.length || 0 }} 个)</el-divider>
      <el-table :data="selectedTpl?.tags || []" size="small" max-height="250">
        <el-table-column prop="name" label="名称" width="140" />
        <el-table-column label="数据源" width="180">
          <template #default="{ row }">
            <span v-if="selectedTpl?.protocol === 'opc_ua'">{{ row.opc_node_id }}</span>
            <span v-else-if="selectedTpl?.protocol === 'mqtt'">{{ row.mqtt_topic }}</span>
            <span v-else>{{ row.function_code }} @ {{ row.address }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="unit" label="单位" width="60" />
        <el-table-column prop="writable" label="可写" width="60">
          <template #default="{ row }"><el-tag v-if="row.writable" type="warning" size="small">可写</el-tag></template>
        </el-table-column>
      </el-table>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="createFromTemplate">创建设备</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '../../api/request'

const router = useRouter()
const templates = ref([])
const dialogVisible = ref(false)
const selectedTpl = ref(null)
const creating = ref(false)

const createForm = reactive({ name: '', host: '', factory: '', workshop: '' })

const hostPlaceholder = computed(() => {
  if (!selectedTpl.value) return ''
  if (selectedTpl.value.protocol === 'mqtt') return '192.168.1.100'
  if (selectedTpl.value.protocol === 'opc_ua') return 'opc.tcp://192.168.1.100:4840'
  return '192.168.1.100'
})

const categoryIcon = (cat) => ({
  'PLC': '🔌', '传感器': '🌡️', '仪表': '🎛️', '网关': '🌐', '其他': '📦',
}[cat] || '📦')

async function fetchTemplates() {
  templates.value = (await api.get('/templates/devices')).data
}

function showCreateDialog(tpl) {
  selectedTpl.value = tpl
  createForm.name = ''
  createForm.host = ''
  createForm.factory = ''
  createForm.workshop = ''
  dialogVisible.value = true
}

async function createFromTemplate() {
  if (!createForm.name) { ElMessage.warning('请输入设备名称'); return }
  creating.value = true
  try {
    const res = await api.post(`/templates/devices/${selectedTpl.value.id}/create`, null, {
      params: { name: createForm.name, host: createForm.host, factory: createForm.factory, workshop: createForm.workshop },
    })
    ElMessage.success(res.data.message)
    dialogVisible.value = false
    router.push(`/devices/${res.data.device_id}`)
  } finally { creating.value = false }
}

onMounted(fetchTemplates)
</script>

<style scoped>
.template-card {
  cursor: pointer; transition: all 0.2s; margin-bottom: 16px;
  &:hover { border-color: #409eff; transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
}
.tpl-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.tpl-icon { font-size: 28px; }
.tpl-desc { font-size: 13px; color: #888; margin: 8px 0; min-height: 36px; }
.tpl-meta { display: flex; justify-content: space-between; font-size: 12px; color: #aaa; }
h3 { margin: 0; font-size: 16px; }
</style>
