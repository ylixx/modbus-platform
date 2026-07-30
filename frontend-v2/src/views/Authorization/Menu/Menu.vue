<script setup lang="ts">
import { ref } from 'vue'
import { ContentWrap } from '@/components/ContentWrap'
import {
  ElTable,
  ElTableColumn,
  ElTag,
  ElEmpty
} from 'element-plus'
import { constantRouterMap, asyncRouterMap } from '@/router'

defineOptions({ name: 'MenuManagement' })

// 菜单管理：展示当前系统路由配置（只读）
// 后续如需动态菜单 CRUD，可对接后端菜单 API
const routes = ref<any[]>([])

const fetchRoutes = () => {
  try {
    const allRoutes = [...constantRouterMap, ...asyncRouterMap]
    routes.value = flattenRoutes(allRoutes)
  } catch {
    routes.value = []
  }
}

const flattenRoutes = (routes: any[], parentPath = ''): any[] => {
  const result: any[] = []
  for (const route of routes) {
    if (route.meta?.hidden) continue
    const fullPath = parentPath ? `${parentPath}/${route.path}`.replace(/\/+/g, '/') : route.path
    result.push({
      name: route.meta?.title || route.name || '',
      path: fullPath,
      component: route.component?.name || (route.children ? '目录' : '页面'),
      icon: route.meta?.icon || '',
      permission: route.meta?.permissions?.join(', ') || '',
      status: route.meta?.hidden ? 0 : 1
    })
    if (route.children && route.children.length) {
      result.push(...flattenRoutes(route.children, fullPath))
    }
  }
  return result
}

fetchRoutes()
</script>

<template>
  <ContentWrap title="菜单管理">
    <div class="mb-12px text-13px text-gray-500">
      当前系统菜单基于路由配置自动生成，如需调整请联系管理员修改路由配置。
    </div>
    <ElTable :data="routes" border stripe row-key="path" default-expand-all>
      <template #empty><ElEmpty description="暂无数据" :image-size="80" /></template>
      <ElTableColumn prop="name" label="菜单名称" min-width="160" show-overflow-tooltip />
      <ElTableColumn prop="path" label="路径" min-width="200" show-overflow-tooltip />
      <ElTableColumn prop="component" label="组件" min-width="120" show-overflow-tooltip />
      <ElTableColumn prop="permission" label="权限标识" min-width="160" show-overflow-tooltip />
      <ElTableColumn label="状态" width="80">
        <template #default="{ row }">
          <ElTag :type="row.status === 1 ? 'success' : 'danger'" size="small">
            {{ row.status === 1 ? '启用' : '禁用' }}
          </ElTag>
        </template>
      </ElTableColumn>
    </ElTable>
  </ContentWrap>
</template>
