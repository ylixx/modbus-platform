<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ContentWrap } from '@/components/ContentWrap'
import {
  ElRow,
  ElCol,
  ElCard,
  ElButton,
  ElTag,
  ElDialog,
  ElForm,
  ElFormItem,
  ElInput,
  ElMessage,
  ElEmpty
} from 'element-plus'
import { getDeviceTemplates, createFromTemplate, unwrapList } from '@/api/modbus'

defineOptions({ name: 'Templates' })

const loading = ref(false)
const list = ref<any[]>([])
const fetchList = async () => {
  loading.value = true
  try {
    list.value = unwrapList(await getDeviceTemplates()).list
  } finally {
    loading.value = false
  }
}

const dialogVisible = ref(false)
const current = ref<any>(null)
const formRef = ref()
const form = reactive<any>({ name: '', host: '', port: 502, slave_id: 1 })
const rules = { name: [{ required: true, message: '请输入设备名称', trigger: 'blur' }] }

const openUse = (tpl: any) => {
  current.value = tpl
  Object.assign(form, { name: tpl.name + ' 副本', host: '', port: 502, slave_id: 1 })
  dialogVisible.value = true
}
const submit = async () => {
  await formRef.value?.validate()
  await createFromTemplate(current.value.id, { ...form })
  ElMessage.success('已根据模板创建设备')
  dialogVisible.value = false
}

onMounted(fetchList)
</script>

<template>
  <ContentWrap title="设备模板" message="选择预置模板，快速创建设备与点位">
    <ElEmpty v-if="!loading && !list.length" description="暂无模板" />
    <ElRow :gutter="16">
      <ElCol v-for="tpl in list" :key="tpl.id" :xs="24" :sm="12" :md="8" class="mb-16px">
        <ElCard shadow="hover" class="h-full">
          <div class="flex items-center justify-between mb-8px">
            <span class="text-16px font-700">{{ tpl.name }}</span>
            <ElTag size="small">{{ tpl.protocol || tpl.category || '模板' }}</ElTag>
          </div>
          <div class="text-13px text-gray-500 mb-12px min-h-40px">{{
            tpl.description || '无描述'
          }}</div>
          <div class="text-12px text-gray-400 mb-12px">
            点位数：{{
              (tpl.tags || tpl.tag_count || 0) &&
              ((tpl.tags && tpl.tags.length) || tpl.tag_count || 0)
            }}
          </div>
          <ElButton
            v-hasPermi="['template.write']"
            type="primary"
            size="small"
            @click="openUse(tpl)"
          >
            使用此模板
          </ElButton>
        </ElCard>
      </ElCol>
    </ElRow>

    <ElDialog v-model="dialogVisible" title="根据模板创建设备" width="480px">
      <ElForm ref="formRef" :model="form" :rules="rules" label-width="90px">
        <ElFormItem label="设备名称" prop="name">
          <ElInput v-model="form.name" />
        </ElFormItem>
        <ElFormItem label="主机地址">
          <ElInput v-model="form.host" placeholder="192.168.1.100" />
        </ElFormItem>
        <ElFormItem label="端口">
          <ElInput v-model.number="form.port" />
        </ElFormItem>
        <ElFormItem label="从站地址">
          <ElInput v-model.number="form.slave_id" />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="dialogVisible = false">取消</ElButton>
        <ElButton type="primary" @click="submit">创建</ElButton>
      </template>
    </ElDialog>
  </ContentWrap>
</template>
