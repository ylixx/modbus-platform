<template>
  <div>
    <div class="page-header">
      <h2>短信管理</h2>
      <p>配置短信联系人、推送规则，查看发送记录</p>
    </div>

    <el-tabs v-model="activeTab">
      <!-- Contacts -->
      <el-tab-pane label="联系人" name="contacts">
        <el-card>
          <template #header>
            <div style="display:flex;justify-content:space-between;align-items:center">
              <span>短信联系人</span>
              <el-button type="primary" size="small" @click="openContactDialog()"><el-icon><Plus /></el-icon> 新增联系人</el-button>
            </div>
          </template>
          <el-table :data="contacts" v-loading="loading" stripe>
            <el-table-column prop="id" label="ID" width="60" />
            <el-table-column prop="name" label="姓名" width="120" />
            <el-table-column prop="phone" label="手机号" width="150" />
            <el-table-column prop="department" label="部门" />
            <el-table-column prop="enabled" label="启用" width="80">
              <template #default="{ row }"><DictTag :modelValue="row.enabled" :options="BOOL_OPTIONS" /></template>
            </el-table-column>
            <el-table-column label="操作" width="150">
              <template #default="{ row }">
                <el-button size="small" @click="openContactDialog(row)">编辑</el-button>
                <el-button size="small" type="danger" @click="deleteContact(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <!-- Push Rules -->
      <el-tab-pane label="推送规则" name="rules">
        <el-card>
          <template #header>
            <div style="display:flex;justify-content:space-between;align-items:center">
              <span>推送规则</span>
              <el-button type="primary" size="small" @click="openRuleDialog()"><el-icon><Plus /></el-icon> 新增规则</el-button>
            </div>
          </template>
          <el-table :data="pushRules" v-loading="loading" stripe>
            <el-table-column prop="id" label="ID" width="60" />
            <el-table-column prop="name" label="规则名称" width="160" />
            <el-table-column label="时间窗口" width="140"><template #default="{ row }">{{ row.time_start }} - {{ row.time_end }}</template></el-table-column>
            <el-table-column prop="cooldown_minutes" label="冷却(分)" width="100" />
            <el-table-column prop="enabled" label="启用" width="80"><template #default="{ row }"><DictTag :modelValue="row.enabled" :options="BOOL_OPTIONS" /></template></el-table-column>
            <el-table-column label="操作" width="150">
              <template #default="{ row }">
                <el-button size="small" @click="openRuleDialog(row)">编辑</el-button>
                <el-button size="small" type="danger" @click="deleteRule(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <!-- Records -->
      <el-tab-pane label="发送记录" name="records">
        <el-card>
          <el-table :data="smsRecords" stripe>
            <el-table-column prop="id" label="ID" width="60" />
            <el-table-column prop="phone" label="手机号" width="140" />
            <el-table-column prop="content" label="内容" show-overflow-tooltip />
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }"><DictTag :modelValue="row.status" :options="SMS_STATUS_OPTIONS" /></template>
            </el-table-column>
            <el-table-column prop="error_message" label="错误信息" width="200" show-overflow-tooltip />
            <el-table-column prop="retry_count" label="重试" width="70" />
            <el-table-column prop="sent_at" label="发送时间" width="170"><template #default="{ row }">{{ formatTime(row.sent_at) }}</template></el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <!-- Test -->
      <el-tab-pane label="测试发送" name="test">
        <el-card header="短信测试">
          <el-form :model="testForm" label-width="80px" style="max-width: 500px">
            <el-form-item label="手机号"><el-input v-model="testForm.phone" placeholder="输入手机号" /></el-form-item>
            <el-form-item label="内容"><el-input v-model="testForm.content" type="textarea" :rows="3" /></el-form-item>
            <el-form-item><el-button type="primary" @click="testSms">发送测试</el-button></el-form-item>
          </el-form>
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <!-- Contact Dialog -->
    <el-dialog v-model="contactDialogVisible" :title="contactForm.id ? '编辑联系人' : '新增联系人'" width="480px">
      <el-form :model="contactForm" label-width="80px">
        <el-form-item label="姓名" required><el-input v-model="contactForm.name" /></el-form-item>
        <el-form-item label="手机号" required><el-input v-model="contactForm.phone" /></el-form-item>
        <el-form-item label="部门"><el-input v-model="contactForm.department" /></el-form-item>
        <el-form-item label="启用"><el-switch v-model="contactForm.enabled" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="contactDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveContact">保存</el-button>
      </template>
    </el-dialog>

    <!-- Push Rule Dialog -->
    <el-dialog v-model="ruleDialogVisible" :title="ruleForm.id ? '编辑推送规则' : '新增推送规则'" width="560px">
      <el-form :model="ruleForm" label-width="100px">
        <el-form-item label="规则名称" required><el-input v-model="ruleForm.name" /></el-form-item>
        <el-form-item label="接收人" required>
          <el-select v-model="selectedContacts" multiple placeholder="选择联系人" style="width:100%">
            <el-option v-for="c in contacts" :key="c.id" :label="`${c.name} (${c.phone})`" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="报警等级">
          <el-checkbox-group v-model="selectedLevels">
            <el-checkbox v-for="item in ALARM_LEVEL_OPTIONS" :key="item.value" :label="item.value">{{ item.label }}</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
        <el-form-item label="时间窗口">
          <el-time-picker v-model="timeRange" is-range range-separator="至" start-placeholder="开始" end-placeholder="结束" format="HH:mm" value-format="HH:mm" />
        </el-form-item>
        <el-form-item label="冷却时间(分)"><el-input-number v-model="ruleForm.cooldown_minutes" :min="1" :max="1440" style="width:100%" /></el-form-item>
        <el-form-item label="启用"><el-switch v-model="ruleForm.enabled" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="ruleDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveRule">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../../api/request'
import { formatTime } from '../../utils'
import DictTag from '../../components/DictTag.vue'
import { SMS_STATUS_OPTIONS, ALARM_LEVEL_OPTIONS } from '../../utils/dict'

const BOOL_OPTIONS = [{ value: true, label: '是', type: 'success' }, { value: false, label: '否', type: 'info' }]

const activeTab = ref('contacts')
const loading = ref(false)
const contacts = ref([])
const pushRules = ref([])
const smsRecords = ref([])

// Contact dialog
const contactDialogVisible = ref(false)
const contactForm = reactive({ id: null, name: '', phone: '', department: '', enabled: true })

// Rule dialog
const ruleDialogVisible = ref(false)
const ruleForm = reactive({ id: null, name: '', cooldown_minutes: 30, enabled: true })
const selectedContacts = ref([])
const selectedLevels = ref([])
const timeRange = ref(['00:00', '23:59'])

const testForm = reactive({ phone: '', content: '【测试】Modbus平台短信测试，请忽略此消息。' })

// ── Contacts ──
async function fetchContacts() { contacts.value = (await api.get('/sms/contacts')).data }

function openContactDialog(c) {
  if (c) { Object.assign(contactForm, c) } else { Object.assign(contactForm, { id: null, name: '', phone: '', department: '', enabled: true }) }
  contactDialogVisible.value = true
}

async function saveContact() {
  if (!contactForm.name || !contactForm.phone) { ElMessage.warning('请填写必填字段'); return }
  if (contactForm.id) { await api.put(`/sms/contacts/${contactForm.id}`, contactForm) }
  else { await api.post('/sms/contacts', contactForm) }
  ElMessage.success('保存成功'); contactDialogVisible.value = false; fetchContacts()
}

async function deleteContact(c) {
  await ElMessageBox.confirm(`确定删除联系人 "${c.name}"？`)
  await api.delete(`/sms/contacts/${c.id}`); ElMessage.success('已删除'); fetchContacts()
}

// ── Rules ──
async function fetchPushRules() { pushRules.value = (await api.get('/sms/rules')).data }

function openRuleDialog(rule) {
  if (rule) {
    Object.assign(ruleForm, { id: rule.id, name: rule.name, cooldown_minutes: rule.cooldown_minutes, enabled: rule.enabled })
    try { selectedContacts.value = JSON.parse(rule.contact_ids) } catch { selectedContacts.value = [] }
    try { selectedLevels.value = JSON.parse(rule.alarm_levels) } catch { selectedLevels.value = [] }
    timeRange.value = [rule.time_start, rule.time_end]
  } else {
    Object.assign(ruleForm, { id: null, name: '', cooldown_minutes: 30, enabled: true })
    selectedContacts.value = []; selectedLevels.value = []; timeRange.value = ['00:00', '23:59']
  }
  ruleDialogVisible.value = true
}

async function saveRule() {
  if (!ruleForm.name || !selectedContacts.value.length) { ElMessage.warning('请填写必填字段'); return }
  const payload = { ...ruleForm, contact_ids: JSON.stringify(selectedContacts.value), alarm_levels: JSON.stringify(selectedLevels.value), time_start: timeRange.value?.[0] || '00:00', time_end: timeRange.value?.[1] || '23:59' }
  if (ruleForm.id) { await api.put(`/sms/rules/${ruleForm.id}`, payload) }
  else { await api.post('/sms/rules', payload) }
  ElMessage.success('保存成功'); ruleDialogVisible.value = false; fetchPushRules()
}

async function deleteRule(rule) {
  await ElMessageBox.confirm(`确定删除规则 "${rule.name}"？`)
  await api.delete(`/sms/rules/${rule.id}`); ElMessage.success('已删除'); fetchPushRules()
}

// ── Records + Test ──
async function fetchRecords() { smsRecords.value = (await api.get('/sms/records', { params: { page: 1, page_size: 100 } })).data.data }

async function testSms() {
  if (!testForm.phone) { ElMessage.warning('请输入手机号'); return }
  await api.post('/sms/test', testForm); ElMessage.success('测试短信已发送')
}

onMounted(() => { fetchContacts(); fetchPushRules(); fetchRecords() })
</script>
