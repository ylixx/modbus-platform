import request from '@/axios'

// 后端存在两种响应：纯数组、或 { code, message, total, page, page_size, data } 分页包装。
// 经 axios 适配层后统一为 IResponse，真实业务体在 res.data。
export const unwrap = (res: any) => res?.data
export const unwrapList = (res: any): { list: any[]; total: number } => {
  const body = res?.data
  if (Array.isArray(body)) return { list: body, total: body.length }
  if (body && Array.isArray(body.data))
    return { list: body.data, total: body.total ?? body.data.length }
  return { list: [], total: 0 }
}

// ============ Dashboard ============
export const getDashboardSummary = () => request.get({ url: '/dashboard/summary' })
export const getDeviceStatus = () => request.get({ url: '/dashboard/device-status' })
export const getAlarmTrend = (params?: any) =>
  request.get({ url: '/dashboard/alarm-trend', params })

// ============ Devices ============
export const getDevices = (params?: any) => request.get({ url: '/devices', params })
export const getAllDevices = () => request.get({ url: '/devices/all' })
export const getDevice = (id: number | string) => request.get({ url: `/devices/${id}` })
export const createDevice = (data: any) => request.post({ url: '/devices', data })
export const updateDevice = (id: number, data: any) => request.put({ url: `/devices/${id}`, data })
export const deleteDevice = (id: number) => request.delete({ url: `/devices/${id}` })
export const duplicateDevice = (id: number, newName: string, copyTags = true) =>
  request.post({ url: `/devices/${id}/duplicate`, params: { new_name: newName, copy_tags: copyTags } })
export const getDeviceLive = (id: number | string) => request.get({ url: `/devices/${id}/live` })
export const getDeviceTags = (id: number | string, params?: any) => request.get({ url: `/devices/${id}/tags`, params })
export const writeDevice = (id: number, data: any) =>
  request.post({ url: `/devices/${id}/write`, data })
export const batchWriteDevices = (data: { items: any[]; stop_on_error?: boolean }) =>
  request.post({ url: '/devices/batch-write', data })
export const getLocations = () => request.get({ url: '/devices/locations' })

// ============ Tags ============
export const getAllTags = (params?: any) => request.get({ url: '/devices/tags/all', params })
export const createTag = (data: any) => request.post({ url: '/devices/tags', data })
export const batchCreateTags = (data: any) => request.post({ url: '/devices/tags/batch', data })
export const updateTag = (id: number, data: any) =>
  request.put({ url: `/devices/tags/${id}`, data })
export const deleteTag = (id: number) => request.delete({ url: `/devices/tags/${id}` })

// ============ Groups (保留兼容，设备归属已迁移至组织架构) ============
export const getGroups = () => request.get({ url: '/devices/groups' })
export const createGroup = (data: any) => request.post({ url: '/devices/groups', data })
export const updateGroup = (id: number, data: any) =>
  request.put({ url: `/devices/groups/${id}`, data })
export const deleteGroup = (id: number) => request.delete({ url: `/devices/groups/${id}` })

// ============ Organization (组织架构) ============
export const getOrgTree = () => request.get({ url: '/orgs/tree' })
export const getOrgList = () => request.get({ url: '/orgs' })
export const createOrg = (data: any) => request.post({ url: '/orgs', data })
export const updateOrg = (id: number, data: any) => request.put({ url: `/orgs/${id}`, data })
export const deleteOrg = (id: number, force = false) =>
  request.delete({ url: `/orgs/${id}`, params: { force } })
export const moveDevicesToOrg = (id: number, deviceIds: number[]) =>
  request.post({ url: `/orgs/${id}/move-devices`, data: { device_ids: deviceIds } })

// ============ History ============
export const getHistory = (params?: any) => request.get({ url: '/history', params })
export const getHistoryLatest = (params?: any) => request.get({ url: '/history/latest', params })

// ============ Alarms ============
export const getAlarmRecords = (params?: any) => request.get({ url: '/alarms/records', params })
export const getActiveAlarms = () => request.get({ url: '/alarms/records/active' })
export const getAlarmStats = () => request.get({ url: '/alarms/stats' })
export const ackAlarm = (id: number) => request.post({ url: `/alarms/records/${id}/acknowledge` })
export const clearAlarm = (id: number) => request.post({ url: `/alarms/records/${id}/clear` })
export const getAlarmRules = (params?: any) => request.get({ url: '/alarms/rules', params })
export const getAllAlarmRules = () => request.get({ url: '/alarms/rules/all' })
export const createAlarmRule = (data: any) => request.post({ url: '/alarms/rules', data })
export const updateAlarmRule = (id: number, data: any) =>
  request.put({ url: `/alarms/rules/${id}`, data })
export const deleteAlarmRule = (id: number) => request.delete({ url: `/alarms/rules/${id}` })
export const getEscalationConfig = () => request.get({ url: '/alarms/escalation-config' })
export const updateEscalationConfig = (data: any) =>
  request.put({ url: '/alarms/escalation-config', data })

// ============ Alarm MQTT Push ============
export const getAlarmMqttConfigs = () => request.get({ url: '/alarms/mqtt' })
export const createAlarmMqttConfig = (data: any) => request.post({ url: '/alarms/mqtt', data })
export const updateAlarmMqttConfig = (id: number, data: any) =>
  request.put({ url: `/alarms/mqtt/${id}`, data })
export const deleteAlarmMqttConfig = (id: number) => request.delete({ url: `/alarms/mqtt/${id}` })
export const testAlarmMqttConfig = (id: number) => request.post({ url: `/alarms/mqtt/${id}/test` })

// ============ Data Forward ============
export const getDataForwardRules = () => request.get({ url: '/data-forward' })
export const createDataForwardRule = (data: any) => request.post({ url: '/data-forward', data })
export const updateDataForwardRule = (id: number, data: any) =>
  request.put({ url: `/data-forward/${id}`, data })
export const deleteDataForwardRule = (id: number) => request.delete({ url: `/data-forward/${id}` })
export const testDataForwardRule = (id: number) => request.post({ url: `/data-forward/${id}/test` })

// ============ MQTT Health ============
export const getMqttHealth = () => request.get({ url: '/mqtt-health' })

// ============ Device Publish ============
export const getDevicePublishStatus = () => request.get({ url: '/device-publish/status' })
export const triggerDevicePublish = (deviceId: number) =>
  request.post({ url: `/device-publish/${deviceId}/trigger` })

// ============ Control ============ (reuse writeDevice)

// ============ SMS ============
export const getSmsContacts = () => request.get({ url: '/sms/contacts' })
export const createSmsContact = (data: any) => request.post({ url: '/sms/contacts', data })
export const updateSmsContact = (id: number, data: any) =>
  request.put({ url: `/sms/contacts/${id}`, data })
export const deleteSmsContact = (id: number) => request.delete({ url: `/sms/contacts/${id}` })
export const getSmsRules = () => request.get({ url: '/sms/rules' })
export const createSmsRule = (data: any) => request.post({ url: '/sms/rules', data })
export const updateSmsRule = (id: number, data: any) =>
  request.put({ url: `/sms/rules/${id}`, data })
export const deleteSmsRule = (id: number) => request.delete({ url: `/sms/rules/${id}` })
export const getSmsRecords = (params?: any) => request.get({ url: '/sms/records', params })
export const testSms = (data: any) => request.post({ url: '/sms/test', data })

// ============ Audit ============
export const getAuditLogs = (params?: any) => request.get({ url: '/audit/logs', params })

// ============ Export ============
export const exportDevicesCsv = () =>
  request.get({ url: '/export/devices/csv', responseType: 'blob' })
export const exportHistoryCsv = (params?: any) =>
  request.get({ url: '/export/history/csv', params, responseType: 'blob' })
export const exportTagsCsv = (deviceId: number) =>
  request.get({ url: '/export/tags/csv', params: { device_id: deviceId }, responseType: 'blob' })
export const exportAlarmsCsv = (params?: any) =>
  request.get({ url: '/export/alarms/csv', params, responseType: 'blob' })
export const exportDailyReport = (params?: any) =>
  request.get({ url: '/export/report/daily', params, responseType: 'blob' })

// ============ Import ============
export const importDevices = (data: any) => request.post({ url: '/import/devices', data })
export const importTags = (data: any) => request.post({ url: '/import/tags', data })
export const getImportTemplateDevices = () =>
  request.get({ url: '/import/template/devices', responseType: 'blob' })
export const getImportTemplateTags = () =>
  request.get({ url: '/import/template/tags', responseType: 'blob' })

// ============ Archive ============
export const getArchiveConfig = () => request.get({ url: '/archive/config' })
export const getArchiveStats = () => request.get({ url: '/archive/stats' })
export const updateArchiveConfig = (data: any) => request.put({ url: '/archive/config', data })
export const batchUpdateArchiveConfig = (data: any) =>
  request.put({ url: '/archive/config/batch', data })
export const runArchive = (data?: any) => request.post({ url: '/archive/run', data })
export const cleanArchive = (data?: any) => request.post({ url: '/archive/clean', data })

// ============ Templates ============
export const getDeviceTemplates = () => request.get({ url: '/templates/devices' })
export const getDeviceTemplate = (id: number) => request.get({ url: `/templates/devices/${id}` })
export const createFromTemplate = (id: number, data: any) =>
  request.post({ url: `/templates/devices/${id}/create`, data })
export const getAlarmRuleTemplates = () => request.get({ url: '/templates/alarm-rules' })

// ============ Scripts ============
export const getScripts = (params?: any) => request.get({ url: '/scripts', params })
export const getScript = (id: number) => request.get({ url: `/scripts/${id}` })
export const createScript = (data: any) => request.post({ url: '/scripts', data })
export const updateScript = (id: number, data: any) => request.put({ url: `/scripts/${id}`, data })
export const deleteScript = (id: number) => request.delete({ url: `/scripts/${id}` })
export const testScript = (data: any) => request.post({ url: '/scripts/test', data })
export const assignScript = (data: any) => request.post({ url: '/scripts/assign', data })
export const getScriptTemplates = () => request.get({ url: '/scripts/templates/all' })

// ============ SCADA ============
export const getScadaPages = () => request.get({ url: '/scada/pages' })
export const getScadaPage = (id: number) => request.get({ url: `/scada/pages/${id}` })
export const createScadaPage = (data: any) => request.post({ url: '/scada/pages', data })
export const updateScadaPage = (id: number, data: any) =>
  request.put({ url: `/scada/pages/${id}`, data })
export const deleteScadaPage = (id: number) => request.delete({ url: `/scada/pages/${id}` })
export const duplicateScadaPage = (id: number) =>
  request.post({ url: `/scada/pages/${id}/duplicate` })
export const getScadaWidgets = () => request.get({ url: '/scada/widgets' })
export const createScadaWidget = (data: any) => request.post({ url: '/scada/widgets', data })
export const updateScadaWidget = (id: number, data: any) =>
  request.put({ url: `/scada/widgets/${id}`, data })
export const deleteScadaWidget = (id: number) => request.delete({ url: `/scada/widgets/${id}` })
export const uploadScadaWidget = (formData: FormData) =>
  request.post({ url: '/scada/widgets/upload', data: formData, headers: { 'Content-Type': 'multipart/form-data' } })
export const batchUploadScadaWidgets = (formData: FormData) =>
  request.post({ url: '/scada/widgets/batch-upload', data: formData, headers: { 'Content-Type': 'multipart/form-data' } })

// ============ RBAC ============
export const getRoles = () => request.get({ url: '/rbac/roles' })
export const createRole = (data: any) => request.post({ url: '/rbac/roles', data })
export const updateRole = (id: number, data: any) => request.put({ url: `/rbac/roles/${id}`, data })
export const deleteRole = (id: number) => request.delete({ url: `/rbac/roles/${id}` })
export const getPermissions = () => request.get({ url: '/rbac/permissions' })
export const getMyPermissions = () => request.get({ url: '/rbac/me/permissions' })
export const getUserRoles = (userId: number) => request.get({ url: `/rbac/users/${userId}/roles` })
export const assignUserRole = (userId: number, data: any) =>
  request.post({ url: `/rbac/users/${userId}/roles`, data })
export const deleteUserRole = (id: number) => request.delete({ url: `/rbac/user-roles/${id}` })

// ============ Users ============
export const getUsers = (params?: any) => request.get({ url: '/users', params })
export const createUser = (data: any) => request.post({ url: '/users', data })
export const updateUser = (id: number, data: any) => request.put({ url: `/users/${id}`, data })
export const deleteUser = (id: number) => request.delete({ url: `/users/${id}` })
export const resetUserPassword = (id: number, data?: any) =>
  request.post({ url: `/users/${id}/reset-password`, data })

// ============ Auth Profile ============
export const updateMyProfile = (data: any) => request.put({ url: '/auth/me', data })
export const changeMyPassword = (data: any) => request.post({ url: '/auth/change-password', data })
export const uploadMyAvatar = (data: any) => request.put({ url: '/auth/me', data })

// ============ Hierarchy ============
export const getHierarchyTree = (params?: any) => request.get({ url: '/hierarchy/tree', params })
export const getHierarchyConfigs = () => request.get({ url: '/hierarchy/configs' })
export const getHierarchyFields = () => request.get({ url: '/hierarchy/fields' })

// ============ Lab Data ============
export const getLabData = (params: any) => request.get({ url: '/lab-data', params })
export const createLabData = (data: any) => request.post({ url: '/lab-data', data })
export const updateLabData = (id: number, data: any) => request.put({ url: `/lab-data/${id}`, data })
export const deleteLabData = (id: number) => request.delete({ url: `/lab-data/${id}` })
export const compareLabData = (params: any) => request.get({ url: '/lab-data/compare', params })

// ============ System Settings ============
export const getRuntimeConfig = () => request.get({ url: '/system/runtime-config' })
export const updateRuntimeConfig = (data: any) => request.put({ url: '/system/runtime-config', data })
export const getEngineStatus = () => request.get({ url: '/system/engine-status' })
export const getNotificationConfig = () => request.get({ url: '/system/notifications' })
export const updateNotificationConfig = (data: any) =>
  request.put({ url: '/system/notifications', data })
export const testNotification = (channel: string) =>
  request.post({ url: '/system/notifications/test', data: { channel } })

// ============ Config Transfer (全量配置导出/导入) ============
export const exportPlatformConfig = () =>
  request.get({ url: '/config/export', responseType: 'blob' })
export const importPlatformConfig = (formData: FormData, overwrite = false) =>
  request.post({
    url: '/config/import',
    data: formData,
    params: { overwrite },
    headers: { 'Content-Type': 'multipart/form-data' }
  })
export const getAggregate = (params: any) => request.get({ url: '/lab-data/aggregate', params })
