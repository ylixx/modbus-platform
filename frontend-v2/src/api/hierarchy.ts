import request from '@/axios'

export interface OrgLevel {
  key: string
  label: string
  field: string
  icon?: string
}

export interface OrgDevice {
  id: number
  name: string
  protocol: string
  status: string
  factory: string
  workshop: string
  production_line: string
  installation: string
  group_id: number | null
  host: string
  port: number
  mqtt_broker: string
  opc_endpoint: string
}

export interface OrgNode {
  id?: number
  label: string
  type: 'level' | 'device'
  icon?: string
  level_key?: string
  children?: OrgNode[]
  device?: OrgDevice
}

export interface OrgTreeResponse {
  levels: OrgLevel[]
  tree: OrgNode[]
}

// 级联框数据源统一为系统「组织架构」(OrgNode 树)：/orgs/cascade
export const getOrgTreeApi = (params?: { with_devices?: boolean }) => {
  return request.get<OrgTreeResponse>({ url: '/orgs/cascade', params })
}
