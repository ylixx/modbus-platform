import request from '@/axios'
import type { UserLoginType, TokenResponse, UserInfo, UserType } from './types'

interface RoleParams {
  roleName: string
}

export const loginApi = (data: UserLoginType): Promise<IResponse<TokenResponse>> => {
  return request.post({ url: '/auth/login', data })
}

export const getMeApi = (): Promise<IResponse<UserInfo>> => {
  return request.get({ url: '/auth/me' })
}

export const loginOutApi = (): Promise<IResponse> => {
  return request.get({ url: '/logout' })
}

export const getUserListApi = ({ params }: AxiosConfig) => {
  return request.get<{
    code: string
    data: {
      list: UserType[]
      total: number
    }
  }>({ url: '/mock/user/list', params })
}

export const getAdminRoleApi = (
  params: RoleParams
): Promise<IResponse<AppCustomRouteRecordRaw[]>> => {
  return request.get({ url: '/mock/role/list', params })
}

export const getTestRoleApi = (params: RoleParams): Promise<IResponse<string[]>> => {
  return request.get({ url: '/mock/role/list2', params })
}
