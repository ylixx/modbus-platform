/**
 * WebSocket 连接管理器
 *
 * 后端协议：
 *   连接: ws://host/api/v1/ws?token=<jwt>
 *   心跳: client → {"type":"ping"} / server → {"type":"pong"}
 *   推送: {"type":"live_value"|"alarm_*"|"device_status"|"operation_log", "data":{...}}
 */

import { useUserStoreWithOut } from '@/store/modules/user'

export type WsMessageType =
  | 'live_value'
  | 'alarm_created'
  | 'alarm_acknowledged'
  | 'alarm_cleared'
  | 'device_status'
  | 'operation_log'
  | 'pong'

export interface WsMessage {
  type: WsMessageType | string
  data?: any
}

export interface WsLiveValue {
  device_id: number
  tag_id: number
  tag_name: string
  value: number
  quality: string
  time: string
}

export interface WsDeviceStatus {
  device_id: number
  device_name: string
  status: string
  error?: string
  time: string
}

type WsListener = (msg: WsMessage) => void

const HEARTBEAT_INTERVAL = 30_000 // 30s
const RECONNECT_BASE_DELAY = 1_000
const RECONNECT_MAX_DELAY = 30_000
const MAX_RECONNECT_ATTEMPTS = 20

class WebSocketManager {
  private ws: WebSocket | null = null
  private listeners: Map<string, Set<WsListener>> = new Map()
  private globalListeners: Set<WsListener> = new Set()
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private reconnectAttempts = 0
  private manuallyClosed = false
  private _connected = false

  get connected(): boolean {
    return this._connected
  }

  /** 建立连接 */
  connect(): void {
    if (this.ws?.readyState === WebSocket.OPEN) return

    this.manuallyClosed = false
    const userStore = useUserStoreWithOut()
    const token = userStore.getToken
    if (!token) {
      console.warn('[WS] No token, skip connect')
      return
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const base = import.meta.env.VITE_API_BASE_PATH || '/api/v1'
    // 开发环境走 vite proxy（相对路径），生产环境用当前 host
    const host = window.location.host
    // 不再通过 URL query 传递 JWT（避免泄露到日志/代理），改为连接后首条消息认证
    const url = `${protocol}//${host}${base}/ws`

    try {
      this.ws = new WebSocket(url)
    } catch (e) {
      console.error('[WS] Failed to create WebSocket:', e)
      this.scheduleReconnect()
      return
    }

    this.ws.onopen = () => {
      this._connected = true
      this.reconnectAttempts = 0
      // 通过首条消息发送 JWT 认证
      this.ws!.send(JSON.stringify({ type: 'auth', token }))
      this.startHeartbeat()
      this.emit({ type: '__connected' } as any)
    }

    this.ws.onmessage = (event: MessageEvent) => {
      try {
        const msg: WsMessage = JSON.parse(event.data)
        if (msg.type === 'pong') return // 心跳回复，忽略
        this.emit(msg)
      } catch (e) {
        console.warn('[WS] Failed to parse message:', event.data)
      }
    }

    this.ws.onclose = (_event: CloseEvent) => {
      this._connected = false
      this.stopHeartbeat()
      this.emit({ type: '__disconnected' } as any)

      if (!this.manuallyClosed) {
        this.scheduleReconnect()
      }
    }

    this.ws.onerror = (event: Event) => {
      console.error('[WS] Error:', event)
    }
  }

  /** 主动断开连接 */
  disconnect(): void {
    this.manuallyClosed = true
    this.stopHeartbeat()
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
    this._connected = false
  }

  /** 订阅特定消息类型 */
  on(type: WsMessageType | string, listener: WsListener): () => void {
    if (!this.listeners.has(type)) {
      this.listeners.set(type, new Set())
    }
    this.listeners.get(type)!.add(listener)
    return () => this.off(type, listener)
  }

  /** 订阅所有消息 */
  onAny(listener: WsListener): () => void {
    this.globalListeners.add(listener)
    return () => this.globalListeners.delete(listener)
  }

  /** 取消订阅 */
  off(type: WsMessageType | string, listener: WsListener): void {
    this.listeners.get(type)?.delete(listener)
  }

  private emit(msg: WsMessage): void {
    // 类型特定监听器
    this.listeners.get(msg.type)?.forEach((fn) => {
      try {
        fn(msg)
      } catch (e) {
        console.error('[WS] Listener error:', e)
      }
    })
    // 全局监听器
    this.globalListeners.forEach((fn) => {
      try {
        fn(msg)
      } catch (e) {
        console.error('[WS] Global listener error:', e)
      }
    })
  }

  private startHeartbeat(): void {
    this.stopHeartbeat()
    this.heartbeatTimer = setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.ws.send('{"type":"ping"}')
      }
    }, HEARTBEAT_INTERVAL)
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer)
      this.heartbeatTimer = null
    }
  }

  private scheduleReconnect(): void {
    if (this.manuallyClosed) return
    if (this.reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
      console.error('[WS] Max reconnect attempts reached')
      return
    }

    const delay = Math.min(
      RECONNECT_BASE_DELAY * Math.pow(2, this.reconnectAttempts),
      RECONNECT_MAX_DELAY
    )
    this.reconnectAttempts++

    this.reconnectTimer = setTimeout(() => {
      this.connect()
    }, delay)
  }
}

// 全局单例
export const wsManager = new WebSocketManager()
