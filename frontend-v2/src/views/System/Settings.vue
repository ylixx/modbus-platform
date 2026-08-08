<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { ContentWrap } from '@/components/ContentWrap'
import {
  ElTabs,
  ElTabPane,
  ElForm,
  ElFormItem,
  ElInput,
  ElInputNumber,
  ElSwitch,
  ElButton,
  ElAlert,
  ElMessage,
  ElMessageBox,
  ElTable,
  ElTableColumn,
  ElTag,
  ElCard,
  ElUpload,
  ElCheckbox
} from 'element-plus'
import {
  getRuntimeConfig,
  updateRuntimeConfig,
  getEngineStatus,
  getNotificationConfig,
  updateNotificationConfig,
  testNotification,
  exportPlatformConfig,
  importPlatformConfig,
  unwrap
} from '@/api/modbus'

defineOptions({ name: 'SystemSettings' })

const activeTab = ref('notify')

// ── Tab 1: 报警通知通道 ──
const notifyLoading = ref(false)
const notifSaving = ref(false)
const notifTest = ref('')
const notifyConfig = ref<Record<string, any>>({
  dingtalk: { enabled: false, webhook_url: '', label: '钉钉机器人', desc: '' },
  wechat: { enabled: false, webhook_url: '', label: '企业微信', desc: '' },
  email: { enabled: false, host: '', port: 465, user: '', password: '', from: '', to: '', label: '邮件', desc: '' }
})

const fetchNotify = async () => {
  notifyLoading.value = true
  try {
    const data = unwrap(await getNotificationConfig()) || {}
    notifyConfig.value = data
  } finally {
    notifyLoading.value = false
  }
}

const saveNotify = async () => {
  notifSaving.value = true
  try {
    const res = await updateNotificationConfig(JSON.parse(JSON.stringify(notifyConfig.value)))
    ElMessage.success(unwrap(res)?.message || '已保存')
    notifyConfig.value = unwrap(res)
  } catch (e: any) {
    ElMessage.error(e?.message || '保存失败')
  } finally {
    notifSaving.value = false
  }
}

const doTestNotify = async (channel: string) => {
  notifTest.value = channel
  try {
    const res: any = await testNotification(channel)
    const body = res?.data || res
    if (body?.code === 200 || body?.success) {
      ElMessage.success(body?.message || '发送成功')
    } else {
      ElMessage.warning(body?.message || '发送失败')
    }
  } catch (e: any) {
    ElMessage.error(e?.message || '发送失败')
  } finally {
    notifTest.value = ''
  }
}

// ── Tab 2: 协议引擎与功能开关 ──
const runtimeLoading = ref(false)
const runtimeSaving = ref(false)
const runtimeConfig = ref<{ engines: Record<string, any>; features: Record<string, any> }>({
  engines: {},
  features: {}
})
const engineStatus = ref<Record<string, any>>({})

// 表格行需保留对 runtimeConfig 原对象的引用，否则 v-model 改的是副本，保存时读到旧值
const engineRows = computed(() =>
  Object.entries(runtimeConfig.value.engines).map(([k, v]) => {
    ;(v as any).__key = k
    return v
  })
)
const featureRows = computed(() =>
  Object.entries(runtimeConfig.value.features).map(([k, v]) => {
    ;(v as any).__key = k
    return v
  })
)

const fetchRuntime = async () => {
  runtimeLoading.value = true
  try {
    runtimeConfig.value = unwrap(await getRuntimeConfig()) || runtimeConfig.value
    try {
      const st = unwrap(await getEngineStatus()) || {}
      engineStatus.value = st.engines || {}
    } catch {
      engineStatus.value = {}
    }
  } finally {
    runtimeLoading.value = false
  }
}

const saveRuntime = async () => {
  runtimeSaving.value = true
  try {
    const payload: any = { engines: {}, features: {} }
    for (const [k, v] of Object.entries(runtimeConfig.value.engines)) payload.engines[k] = v.enabled
    for (const [k, v] of Object.entries(runtimeConfig.value.features)) payload.features[k] = v.enabled
    const res = await updateRuntimeConfig(payload)
    ElMessage.success(unwrap(res)?.message || '已保存')
  } catch (e: any) {
    ElMessage.error(e?.message || '保存失败')
  } finally {
    runtimeSaving.value = false
  }
}

// ── Tab 3: 全量配置导出/导入 ──
const exportLoading = ref(false)
const importLoading = ref(false)
const overwrite = ref(false)

const doExport = async () => {
  exportLoading.value = true
  try {
    const res: any = await exportPlatformConfig()
    const blob = new Blob([res.data], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `modbus-platform-config-${new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')}.json`
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('配置已导出')
  } catch (e: any) {
    ElMessage.error(e?.message || '导出失败')
  } finally {
    exportLoading.value = false
  }
}

const beforeImport = (file: File) => {
  if (!file.name.endsWith('.json')) {
    ElMessage.error('仅支持 .json 配置文件')
    return false
  }
  return true
}

const doImport = async (file: File) => {
  try {
    await ElMessageBox.confirm(
      '导入将按名称匹配并覆盖或新增设备/点位/规则/脚本等配置，确认继续？',
      '导入全量配置',
      { type: 'warning', confirmButtonText: '继续导入', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  importLoading.value = true
  try {
    const formData = new FormData()
    formData.append('file', file)
    const res = await importPlatformConfig(formData, overwrite.value)
    const body = unwrap(res)
    ElMessage.success(body?.message || '导入完成')
  } catch (e: any) {
    ElMessage.error(e?.message || '导入失败')
  } finally {
    importLoading.value = false
  }
}

onMounted(() => {
  fetchNotify()
  fetchRuntime()
})
</script>

<template>
  <ContentWrap title="系统设置">
    <ElTabs v-model="activeTab">
      <ElTabPane label="报警通知" name="notify" v-loading="notifyLoading">
        <ElAlert
          type="info"
          :closable="false"
          title="报警触发时可推送钉钉/企业微信/邮件，保存后立即生效；留空的字段将回退使用 .env 中的默认配置"
          style="margin-bottom: 16px"
        />
        <ElForm label-width="140px" style="max-width: 720px">
          <!-- 钉钉 -->
          <ElFormItem :label="notifyConfig.dingtalk?.label || '钉钉机器人'">
            <div class="flex-1">
              <ElSwitch v-model="notifyConfig.dingtalk.enabled" />
              <ElInput
                v-model="notifyConfig.dingtalk.webhook_url"
                placeholder="https://oapi.dingtalk.com/robot/send?access_token=..."
                style="margin-top: 8px"
                clearable
              />
            </div>
          </ElFormItem>
          <!-- 企业微信 -->
          <ElFormItem :label="notifyConfig.wechat?.label || '企业微信'">
            <div class="flex-1">
              <ElSwitch v-model="notifyConfig.wechat.enabled" />
              <ElInput
                v-model="notifyConfig.wechat.webhook_url"
                placeholder="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=..."
                style="margin-top: 8px"
                clearable
              />
            </div>
          </ElFormItem>
          <!-- 邮件 -->
          <ElFormItem :label="notifyConfig.email?.label || '邮件'">
            <div class="flex-1">
              <ElSwitch v-model="notifyConfig.email.enabled" />
              <div class="grid grid-cols-2 gap-x-12px" style="margin-top: 8px">
                <ElInput v-model="notifyConfig.email.host" placeholder="SMTP 服务器，如 smtp.qq.com" />
                <ElInputNumber
                  v-model="notifyConfig.email.port"
                  :min="1"
                  :max="65535"
                  :controls="false"
                  style="width: 100%"
                />
                <ElInput v-model="notifyConfig.email.user" placeholder="邮箱账号" style="margin-top: 8px" />
                <ElInput v-model="notifyConfig.email.password" placeholder="授权码/密码" type="password" show-password style="margin-top: 8px" />
                <ElInput v-model="notifyConfig.email.from" placeholder="发件人（留空=账号）" style="margin-top: 8px" />
                <ElInput v-model="notifyConfig.email.to" placeholder="收件人，多个用逗号分隔" style="margin-top: 8px" />
              </div>
            </div>
          </ElFormItem>
          <ElFormItem>
            <ElButton type="primary" :loading="notifSaving" @click="saveNotify">保存配置</ElButton>
            <ElButton
              :loading="notifTest === 'dingtalk'"
              :disabled="!notifyConfig.dingtalk?.webhook_url"
              @click="doTestNotify('dingtalk')"
            >
              测试钉钉
            </ElButton>
            <ElButton
              :loading="notifTest === 'wechat'"
              :disabled="!notifyConfig.wechat?.webhook_url"
              @click="doTestNotify('wechat')"
            >
              测试企业微信
            </ElButton>
            <ElButton
              :loading="notifTest === 'email'"
              :disabled="!notifyConfig.email?.host || !notifyConfig.email?.to"
              @click="doTestNotify('email')"
            >
              测试邮件
            </ElButton>
          </ElFormItem>
        </ElForm>
      </ElTabPane>

      <ElTabPane label="引擎与功能" name="runtime" v-loading="runtimeLoading">
        <ElAlert
          type="warning"
          :closable="false"
          title="关闭的引擎/功能在下次重启后端时不再启动（当前运行中的服务不受影响）。采集轮询间隔、发布周期可在设备编辑表单中分别配置"
          style="margin-bottom: 16px"
        />
        <div class="flex gap-x-24px flex-wrap" style="max-width: 1080px">
          <!-- 协议引擎 -->
          <div class="flex-1" style="min-width: 420px">
            <div class="text-15px font-semibold mb-8px">协议采集引擎</div>
            <ElTable :data="engineRows" size="default">
              <ElTableColumn label="引擎" min-width="130">
                <template #default="{ row }">{{ row.label }}</template>
              </ElTableColumn>
              <ElTableColumn label="说明" min-width="220">
                <template #default="{ row }">{{ row.desc }}</template>
              </ElTableColumn>
              <ElTableColumn label="运行状态" width="90">
                <template #default="{ row }">
                  <ElTag v-if="engineStatus[row.__key]" :type="engineStatus[row.__key].running ? 'success' : 'info'" size="small">
                    {{ engineStatus[row.__key].running ? '运行中' : '未运行' }}
                  </ElTag>
                  <ElTag v-else type="info" size="small">未知</ElTag>
                </template>
              </ElTableColumn>
              <ElTableColumn label="启用" width="80">
                <template #default="{ row }">
                  <ElSwitch v-model="row.enabled" />
                </template>
              </ElTableColumn>
            </ElTable>
          </div>
          <!-- 功能模块 -->
          <div class="flex-1" style="min-width: 420px">
            <div class="text-15px font-semibold mb-8px">功能模块</div>
            <ElTable :data="featureRows" size="default">
              <ElTableColumn label="模块" min-width="130">
                <template #default="{ row }">{{ row.label }}</template>
              </ElTableColumn>
              <ElTableColumn label="说明" min-width="220">
                <template #default="{ row }">{{ row.desc }}</template>
              </ElTableColumn>
              <ElTableColumn label="启用" width="80">
                <template #default="{ row }">
                  <ElSwitch v-model="row.enabled" />
                </template>
              </ElTableColumn>
            </ElTable>
          </div>
        </div>
        <div style="margin-top: 16px">
          <ElButton type="primary" :loading="runtimeSaving" @click="saveRuntime">保存开关配置</ElButton>
        </div>
      </ElTabPane>

      <ElTabPane label="配置迁移" name="transfer">
        <ElAlert
          type="info"
          :closable="false"
          title="导出平台全部配置（设备/点位/报警规则/脚本/短信/SCADA 等）为 JSON 文件，可在另一套系统导入，适合现场部署复制"
          style="margin-bottom: 16px"
        />
        <div class="flex gap-x-24px flex-wrap">
          <ElCard shadow="never" class="flex-1" style="min-width: 360px">
            <template #header>导出配置</template>
            <p class="text-13px text-gray-500" style="margin-bottom: 12px">
              下载当前系统全部配置，用于备份或迁移到新系统
            </p>
            <ElButton type="primary" :loading="exportLoading" @click="doExport">导出全部配置</ElButton>
          </ElCard>
          <ElCard shadow="never" class="flex-1" style="min-width: 360px">
            <template #header>导入配置</template>
            <p class="text-13px text-gray-500" style="margin-bottom: 12px">
              从 JSON 文件恢复配置，按名称匹配更新
            </p>
            <div style="margin-bottom: 12px">
              <ElCheckbox v-model="overwrite">已存在同名的设备/点位时覆盖其配置</ElCheckbox>
            </div>
            <ElUpload
              :auto-upload="false"
              :show-file-list="false"
              accept=".json"
              :before-upload="beforeImport"
              :on-change="(f: any) => doImport(f.raw)"
              :disabled="importLoading"
            >
              <ElButton type="warning" :loading="importLoading">选择 JSON 文件导入</ElButton>
            </ElUpload>
          </ElCard>
        </div>
      </ElTabPane>
    </ElTabs>
  </ContentWrap>
</template>
