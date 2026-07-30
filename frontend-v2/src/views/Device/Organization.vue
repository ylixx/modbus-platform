<script setup lang="ts">
import { ref, reactive, onMounted, h, defineComponent } from 'vue'
import { ContentWrap } from '@/components/ContentWrap'
import {
  ElButton,
  ElDialog,
  ElForm,
  ElFormItem,
  ElInput,
  ElSelect,
  ElOption,
  ElTree,
  ElTreeSelect,
  ElTag,
  ElMessage,
  ElMessageBox,
  ElInputNumber
} from 'element-plus'
import { getOrgTree, createOrg, updateOrg, deleteOrg } from '@/api/modbus'

defineOptions({ name: 'Organization' })

// ── 树节点行组件（含操作按钮） ──
const NODE_TYPES = [
  { value: 'factory', label: '厂级' },
  { value: 'area', label: '区级' },
  { value: 'team', label: '班级' },
  { value: 'station', label: '站级' },
  { value: 'location', label: '位置' },
  { value: 'other', label: '其他' }
]
const nodeTypeLabel = (t?: string) => NODE_TYPES.find((o) => o.value === t)?.label || (t || '其他')
const nodeTypeTag = (t?: string) =>
  t === 'factory'
    ? 'danger'
    : t === 'area'
      ? 'warning'
      : t === 'team'
        ? 'success'
        : t === 'station'
          ? 'primary'
          : 'info'

const NodeRow = defineComponent({
  name: 'NodeRow',
  props: { data: { type: Object, required: true } },
  emits: ['add', 'edit', 'remove'],
  setup(props, { emit }) {
    return () =>
      h('div', { class: 'flex items-center justify-between w-full pr-4px' }, [
        h('span', {}, [
          h(ElTag, { type: nodeTypeTag(props.data.node_type), size: 'small' }, () => nodeTypeLabel(props.data.node_type)),
          ' ',
          props.data.name
        ]),
        h('span', { class: 'flex items-center' }, [
          h('span', { class: 'text-gray-400 text-12px mr-8px' }, `设备 ${props.data.device_count || 0}`),
          h(ElButton, { link: true, type: 'primary', size: 'small', onClick: () => emit('add', props.data) }, () => '新增子级'),
          h(ElButton, { link: true, type: 'primary', size: 'small', onClick: () => emit('edit', props.data) }, () => '编辑'),
          h(ElButton, { link: true, type: 'danger', size: 'small', onClick: () => emit('remove', props.data) }, () => '删除')
        ])
      ])
  }
})

const loading = ref(false)
const treeData = ref<any[]>([])

const fetchTree = async () => {
  loading.value = true
  try {
    const res = await getOrgTree()
    treeData.value = res?.data || []
  } finally {
    loading.value = false
  }
}

// ── 表单 ──
const dialogVisible = ref(false)
const dialogTitle = ref('新增节点')
const isEdit = ref(false)
const formRef = ref()
const form = reactive<any>({
  id: null,
  name: '',
  node_type: 'factory',
  parent_id: null as number | null,
  sort_order: 0,
  description: ''
})
const rules = {
  name: [{ required: true, message: '请输入节点名称', trigger: 'blur' }],
  node_type: [{ required: true, message: '请选择节点类型', trigger: 'change' }]
}
const resetForm = () =>
  Object.assign(form, {
    id: null,
    name: '',
    node_type: 'factory',
    parent_id: null,
    sort_order: 0,
    description: ''
  })

const openCreateRoot = () => {
  isEdit.value = false
  dialogTitle.value = '新增顶级节点'
  resetForm()
  dialogVisible.value = true
}
const openCreateChild = (data: any) => {
  isEdit.value = false
  dialogTitle.value = `在「${data.name}」下新增子节点`
  resetForm()
  form.parent_id = data.id
  dialogVisible.value = true
}
const openEdit = (data: any) => {
  isEdit.value = true
  dialogTitle.value = '编辑节点'
  Object.assign(form, {
    id: data.id,
    name: data.name,
    node_type: data.node_type || 'other',
    parent_id: data.parent_id ?? null,
    sort_order: data.sort_order ?? 0,
    description: data.description || ''
  })
  dialogVisible.value = true
}

// 上级选择：编辑时排除自身及其子树，避免成环
const filteredTree = () => {
  if (!isEdit.value || form.id == null) return treeData.value
  const filter = (nodes: any[]): any[] =>
    nodes
      .filter((n) => n.id !== form.id)
      .map((n) => ({ ...n, children: n.children ? filter(n.children) : [] }))
  return filter(treeData.value)
}

const submit = async () => {
  try {
    await formRef.value?.validate()
    const payload: any = {
      name: form.name,
      node_type: form.node_type,
      parent_id: form.parent_id ?? null,
      sort_order: form.sort_order ?? 0,
      description: form.description || ''
    }
    if (isEdit.value) {
      await updateOrg(form.id, payload)
      ElMessage.success('更新成功')
    } else {
      await createOrg(payload)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    fetchTree()
  } catch (e: any) {
    ElMessage.error(e?.message || '操作失败')
  }
}

const remove = async (data: any) => {
  try {
    await deleteOrg(data.id, false)
    ElMessage.success('删除成功')
    fetchTree()
  } catch (e: any) {
    const msg = e?.response?.data?.detail || e?.response?.data?.message || e?.message || ''
    if (msg.includes('设备')) {
      await ElMessageBox.confirm(`${msg}，是否强制删除（将解除相关设备归属）？`, '提示', {
        type: 'warning',
        confirmButtonText: '强制删除'
      })
      await deleteOrg(data.id, true)
      ElMessage.success('已强制删除')
      fetchTree()
    } else {
      ElMessage.error(msg || '删除失败')
    }
  }
}

onMounted(fetchTree)
</script>

<template>
  <ContentWrap title="组织架构">
    <template #header>
      <div class="flex-grow flex justify-end">
        <ElButton v-hasPermi="['org.write']" type="success" @click="openCreateRoot"
          >新增顶级节点</ElButton
        >
      </div>
    </template>

    <ElTree
      v-loading="loading"
      :data="treeData"
      node-key="id"
      :props="{ label: 'name', children: 'children' }"
      :expand-on-click-node="false"
      default-expand-all
      class="org-tree"
    >
      <template #default="{ data }">
        <NodeRow :data="data" @add="openCreateChild" @edit="openEdit" @remove="remove" />
      </template>
    </ElTree>

    <ElDialog v-model="dialogVisible" :title="dialogTitle" width="480px" @close="formRef?.resetFields()">
      <ElForm ref="formRef" :model="form" :rules="rules" label-width="90px">
        <ElFormItem label="名称" prop="name">
          <ElInput v-model="form.name" placeholder="如：一号厂 / A区 / 一班" />
        </ElFormItem>
        <ElFormItem label="节点类型" prop="node_type">
          <ElSelect v-model="form.node_type" class="w-full">
            <ElOption v-for="o in NODE_TYPES" :key="o.value" :label="o.label" :value="o.value" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="上级节点">
          <ElTreeSelect
            v-model="form.parent_id"
            :data="filteredTree()"
            node-key="id"
            :props="{ label: 'name', children: 'children' }"
            check-strictly
            clearable
            placeholder="不选则为顶级节点"
            class="w-full"
          />
        </ElFormItem>
        <ElFormItem label="排序">
          <ElInputNumber v-model="form.sort_order" :min="0" :max="9999" />
        </ElFormItem>
        <ElFormItem label="描述">
          <ElInput v-model="form.description" type="textarea" :rows="2" />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="dialogVisible = false">取消</ElButton>
        <ElButton type="primary" @click="submit">确定</ElButton>
      </template>
    </ElDialog>
  </ContentWrap>
</template>

<style scoped>
.org-tree :deep(.el-tree-node__content) {
  height: 40px;
}
</style>
