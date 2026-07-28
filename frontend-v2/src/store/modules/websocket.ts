/**
 * WebSocket Pinia Store
 * 管理 WS 连接状态和实时数据缓存
 */
import { defineStore } from 'pinia'
import { store } from '../index'
import { wsManager } from '@/utils/websocket'
import type { WsMessage, WsLiveValue, WsDeviceStatus } from '@/utils/websocket'

export interface WsState {
  /** 是否已连接 */
  connected: boolean
  /** 最新的实时数据 { `${deviceId}:${tagName}`: WsLiveValue } */
  liveData: Record<string, WsLiveValue>
  /** 设备状态 { deviceId: WsDeviceStatus } */
  deviceStatuses: Record<number, WsDeviceStatus>
  /** 未读报警数 */
  unreadAlarms: number
  /** 最近报警列表（最多保留 50 条） */
  recentAlarms: any[]
}

export const useWsStore = defineStore('websocket', {
  state: (): WsState & { _initialized: boolean } => ({
    connected: false,
    liveData: {},
    deviceStatuses: {},
    unreadAlarms: 0,
    recentAlarms: [],
    _initialized: false
  }),

  getters: {
    isConnected(): boolean {
      return this.connected
    },
    getLiveValue: (state) => {
      return (deviceId: number, tagName: string): WsLiveValue | undefined => {
        return state.liveData[`${deviceId}:${tagName}`]
      }
    },
    getDeviceStatus: (state) => {
      return (deviceId: number): WsDeviceStatus | undefined => {
        return state.deviceStatuses[deviceId]
      }
    }
  },

  actions: {
    /** 初始化 WebSocket 连接和事件监听（幂等，多次调用不会重复注册监听器） */
    init() {
      if (this._initialized) return
      this._initialized = true
      // 连接/断开事件
      wsManager.on('__connected', () => {
        this.connected = true
      })
      wsManager.on('__disconnected', () => {
        this.connected = false
      })

      // 实时数据更新（单条，兼容旧格式）
      wsManager.on('live_value', (msg: WsMessage) => {
        const d = msg.data as WsLiveValue
        if (d) {
          this.liveData[`${d.device_id}:${d.tag_name}`] = d
        }
      })

      // 实时数据更新（批量，v2 引擎）
      wsManager.on('batch_live', (msg: WsMessage) => {
        const items = msg.data as WsLiveValue[]
        if (Array.isArray(items)) {
          for (const d of items) {
            this.liveData[`${d.device_id}:${d.tag_name}`] = d
          }
        }
      })

      // 设备状态变更
      wsManager.on('device_status', (msg: WsMessage) => {
        const d = msg.data as WsDeviceStatus
        if (d) {
          this.deviceStatuses[d.device_id] = d
        }
      })

      // 报警事件
      wsManager.on('alarm_created', (msg: WsMessage) => {
        this.unreadAlarms++
        this.recentAlarms.unshift({ ...msg.data, _type: 'created', _time: Date.now() })
        if (this.recentAlarms.length > 50) this.recentAlarms.pop()
      })
      wsManager.on('alarm_acknowledged', (msg: WsMessage) => {
        this._updateAlarm(msg.data, 'acknowledged')
      })
      wsManager.on('alarm_cleared', (msg: WsMessage) => {
        this._updateAlarm(msg.data, 'cleared')
      })

      // 建立连接
      wsManager.connect()
    },

    /** 清除未读报警计数 */
    clearUnreadAlarms() {
      this.unreadAlarms = 0
    },

    /** 断开连接（退出登录时调用） */
    destroy() {
      wsManager.disconnect()
      this._initialized = false
      this.$reset()
    },

    /** 内部：更新报警状态 */
    _updateAlarm(data: any, status: string) {
      if (!data) return
      const idx = this.recentAlarms.findIndex((a) => a.id === data.id)
      if (idx !== -1) {
        this.recentAlarms[idx] = { ...this.recentAlarms[idx], ...data, _type: status }
      }
    }
  },

  persist: false // WS 状态不持久化
})

export const useWsStoreWithOut = () => {
  return useWsStore(store)
}
