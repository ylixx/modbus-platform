export interface UserLoginType {
  username: string
  password: string
}

// 记住登录信息（仅用户名，不存储密码）
export interface RememberedLoginType {
  username: string
}

// 登录表单数据仅需用户名密码
export type UserType = UserLoginType

// 当前登录用户信息（来自后端 /auth/login 或 /auth/me 的 user 字段）
export interface UserInfo {
  id: number
  username: string
  display_name: string
  phone: string
  email: string
  role: string
  is_active: boolean
  permissions: string[]
  avatar_url?: string
  roles?: string[]
}

// 登录返回结构（后端 TokenResponse）
export interface TokenResponse {
  access_token: string
  token_type: string
  user: UserInfo
}
