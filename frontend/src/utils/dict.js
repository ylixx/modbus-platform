/**
 * Dictionary definitions — used with DictTag component.
 *
 * Usage:
 *   import { DictTag } from '@/components/DictTag.vue'
 *   import { DEVICE_STATUS_OPTIONS, PROTOCOL_OPTIONS, ALARM_LEVEL_OPTIONS } from '@/utils/dict'
 *
 *   <DictTag :modelValue="row.status" :options="DEVICE_STATUS_OPTIONS" />
 */

export const DEVICE_STATUS_OPTIONS = [
  { value: 'online', label: '在线', type: 'success' },
  { value: 'offline', label: '离线', type: 'info' },
  { value: 'error', label: '异常', type: 'danger' },
  { value: 'maintenance', label: '维护', type: 'warning' },
]

export const PROTOCOL_OPTIONS = [
  { value: 'modbus_tcp', label: 'Modbus TCP', type: '' },
  { value: 'mqtt', label: 'MQTT', type: 'success' },
  { value: 'opc_ua', label: 'OPC-UA', type: 'warning' },
]

export const ALARM_LEVEL_OPTIONS = [
  { value: 'info', label: '提示', type: 'info' },
  { value: 'warning', label: '警告', type: 'warning' },
  { value: 'critical', label: '严重', type: 'danger' },
  { value: 'emergency', label: '紧急', type: 'danger' },
]

export const ALARM_STATUS_OPTIONS = [
  { value: 'active', label: '活跃', type: 'danger' },
  { value: 'acknowledged', label: '已确认', type: 'warning' },
  { value: 'cleared', label: '已消除', type: 'success' },
]

export const ALARM_TYPE_OPTIONS = [
  { value: 'threshold_high', label: '上限报警' },
  { value: 'threshold_low', label: '下限报警' },
  { value: 'threshold_range', label: '区间报警' },
  { value: 'rate_of_change', label: '变化率报警' },
  { value: 'status', label: '状态报警' },
  { value: 'disconnect', label: '设备离线' },
]

export const FUNCTION_CODE_OPTIONS = [
  { value: 'coil', label: 'Coil (FC01/05)' },
  { value: 'discrete_input', label: 'Discrete Input (FC02)' },
  { value: 'input_register', label: 'Input Register (FC04)' },
  { value: 'holding_register', label: 'Holding Register (FC03/06)' },
]

export const DATA_TYPE_OPTIONS = [
  { value: 'bool', label: 'BOOL' },
  { value: 'int16', label: 'INT16' },
  { value: 'uint16', label: 'UINT16' },
  { value: 'int32', label: 'INT32' },
  { value: 'uint32', label: 'UINT32' },
  { value: 'float32', label: 'FLOAT32' },
  { value: 'float64', label: 'FLOAT64' },
  { value: 'string', label: 'STRING' },
  { value: 'bcd', label: 'BCD' },
]

export const BYTE_ORDER_OPTIONS = [
  { value: 'big_endian', label: 'Big Endian (AB CD)' },
  { value: 'little_endian', label: 'Little Endian (DC BA)' },
  { value: 'big_endian_swap', label: 'Big Endian Swap (BA DC)' },
  { value: 'little_endian_swap', label: 'Little Endian Swap (CD AB)' },
]

export const ROLE_OPTIONS = [
  { value: 'admin', label: '系统管理员', type: 'danger' },
  { value: 'engineer', label: '工程师', type: 'warning' },
  { value: 'operator', label: '操作员', type: '' },
  { value: 'viewer', label: '观察者', type: 'info' },
]

export const SMS_STATUS_OPTIONS = [
  { value: 'pending', label: '待发送', type: 'info' },
  { value: 'sent', label: '已发送', type: 'success' },
  { value: 'failed', label: '发送失败', type: 'danger' },
  { value: 'retrying', label: '重试中', type: 'warning' },
]

export const QUALITY_OPTIONS = [
  { value: 'good', label: '正常', type: 'success' },
  { value: 'bad', label: '异常', type: 'danger' },
  { value: 'uncertain', label: '不确定', type: 'warning' },
]

/**
 * Helper: get label by value from options
 */
export function getLabel(options, value) {
  const item = options.find(o => String(o.value) === String(value))
  return item?.label ?? value
}

/**
 * Helper: get tag type by value from options
 */
export function getTagType(options, value) {
  const item = options.find(o => String(o.value) === String(value))
  return item?.type ?? 'info'
}
