// Modbus 平台业务类型定义

export interface PageParams {
  page?: number
  page_size?: number
  [key: string]: any
}

export interface PageResult<T> {
  items: T[]
  total: number
  page?: number
  page_size?: number
}

export interface DeviceItem {
  id: number
  name: string
  protocol: string
  host?: string
  port?: number
  slave_id?: number
  unit_id?: number
  location?: string
  group_id?: number
  status?: string
  enabled?: boolean
  description?: string
  created_at?: string
  [key: string]: any
}

export interface TagItem {
  id: number
  device_id: number
  name: string
  address: number
  data_type?: string
  register_type?: string
  unit?: string
  scale?: number
  offset?: number
  writable?: boolean
  description?: string
  value?: any
  [key: string]: any
}

export interface GroupItem {
  id: number
  name: string
  description?: string
  device_count?: number
  [key: string]: any
}

export interface AlarmRecord {
  id: number
  device_id?: number
  device_name?: string
  tag_name?: string
  level?: string
  message?: string
  value?: any
  status?: string
  triggered_at?: string
  acknowledged_at?: string
  cleared_at?: string
  [key: string]: any
}

export interface AlarmRule {
  id: number
  name: string
  device_id?: number
  tag_id?: number
  condition?: string
  threshold?: number
  level?: string
  enabled?: boolean
  [key: string]: any
}

export interface ScriptItem {
  id: number
  name: string
  language?: string
  content?: string
  description?: string
  enabled?: boolean
  [key: string]: any
}

export interface SmsContact {
  id: number
  name: string
  phone: string
  enabled?: boolean
  [key: string]: any
}

export interface SmsRule {
  id: number
  name: string
  enabled?: boolean
  [key: string]: any
}

export interface RoleItem {
  id: number
  name: string
  code?: string
  description?: string
  permissions?: any[]
  [key: string]: any
}

export interface UserItem {
  id: number
  username: string
  display_name?: string
  role?: string
  phone?: string
  email?: string
  is_active?: boolean
  [key: string]: any
}
