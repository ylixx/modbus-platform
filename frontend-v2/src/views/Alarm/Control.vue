<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { ContentWrap } from '@/components/ContentWrap'
import {
  ElButton,
  ElForm,
  ElFormItem,
  ElSelect,
  ElOption,
  ElInput,
  ElInputNumber,
  ElTable,
  ElTableColumn,
  ElTag,
  ElMessage,
  ElMessageBox,
  ElDialog,
  ElAlert,
  ElDescriptions,
  ElDescriptionsItem
} from 'element-plus'
import { getAllDevices, getDeviceTags, writeDevice, unwrap, unwrapList } from '@/api/modbus'

defineOptions({ name: 'Control' })

const devices = ref<any[]>([])
const tags = ref<any[]>([])
const tagsLoading = ref(false)
const form = reactive<any>({ device_id: null, tag_id: null, value: null })

const writableTags = computed(() => tags.value.filter((t) => t.writable))

const selectedDevice = computed(() => devices.value.find((d) => d.id === form.device_id))
const selectedTag = computed(() => tags.value.find((t) => t.id === form.tag_id))

const fetchDevices = async () => {
  try {
    devices.value = unwrapList(await getAllDevices()).list
  } catch (e: any) {
    ElMessage.error(e?.message || '获取设备列表失败')
  }
}
const onDeviceChange = async () => {
  form.tag_id = null
  tags.value = []
  if (form.device_id == null) return
  tagsLoading.value = true
  try {
    const res = await getDeviceTags(form.device_id)
    const body = unwrap(res)
    tags.value = Array.isArray(body) ? body : unwrapList(res).list
  } catch (e: any) {
    ElMessage.error(e?.message || '获取点位列表失败')
  } finally {
    tagsLoading.value = false
  }
}

// ── 二次确认 ──
const confirmDialogVisible = ref(false)
const confirmText = ref('')
const confirmBusy = ref(false)

const doWrite = () => {
  if (form.device_id == null || form.tag_id == null) {
    ElMessage.warning('请选择设备和点位')
    return
  }
  if (form.value == null) {
    ElMessage.warning('请输入写入值')
    return
  }
  // 打开确认对话框
  confirmText.value = ''
  confirmDialogVisible.value = true
}

const confirmAndWrite = async () => {
  if (confirmText.value !== '确认') {
    ElMessage.warning('请输入"确认"以继续')
    return
  }
  confirmBusy.value = true
  try {
    await writeDevice(form.device_id, { tag_id: form.tag_id, value: Number(form.value) })
    ElMessage.success('写入指令已下发')
    confirmDialogVisible.value = false
  } catch (e: any) {
    ElMessage.error(e?.message || '写入失败')
  } finally {
    confirmBusy.value = false
  }
}

onMounted(fetchDevices)
</script>

<template>
  <ContentWrap title="远程控制">
    <ElAlert
      title="远程控制可直接修改设备运行参数，请确认操作对象和数值无误后再执行。"
      type="warning"
      :closable="false"
      class="mb-16px"
    />

    <ElForm :model="form" label-width="90px" class="max-w-560px">
      <ElFormItem label="目标设备">
        <ElSelect
          v-model="form.device_id"
          class="w-full"
          placeholder="请选择设备"
          @change="onDeviceChange"
        >
          <ElOption v-for="d in devices" :key="d.id" :label="d.name" :value="d.id" />
        </ElSelect>
      </ElFormItem>
      <ElFormItem label="控制点位">
        <ElSelect
          v-model="form.tag_id"
          class="w-full"
          placeholder="请选择可写点位"
          :disabled="form.device_id == null"
        >
          <ElOption
            v-for="t in writableTags"
            :key="t.id"
            :label="`${t.name} (地址 ${t.address})`"
            :value="t.id"
          />
        </ElSelect>
      </ElFormItem>
      <ElFormItem label="写入值">
        <ElInputNumber v-model="form.value" :step="0.1" :precision="2" class="w-full" placeholder="请输入要写入的数值" />
      </ElFormItem>
      <ElFormItem>
        <ElButton v-hasPermi="['device.control']" type="danger" @click="doWrite">
          下发控制指令
        </ElButton>
      </ElFormItem>
    </ElForm>

    <div class="mt-16px">
      <div class="text-14px font-600 mb-8px">当前设备可写点位</div>
      <ElEmpty v-if="form.device_id == null" description="请先选择设备" :image-size="70" />
      <ElTable v-else v-loading="tagsLoading" :data="writableTags" border stripe>
        <ElTableColumn prop="name" label="点位名称" min-width="140" />
        <ElTableColumn prop="address" label="地址" width="90" />
        <ElTableColumn prop="register_type" label="寄存器" width="120" />
        <ElTableColumn label="当前值" width="120">
          <template #default="{ row }">{{ row.value ?? '—' }}{{ row.unit || '' }}</template>
        </ElTableColumn>
        <ElTableColumn label="可写" width="80">
          <template #default><ElTag type="success">是</ElTag></template>
        </ElTableColumn>
      </ElTable>
    </div>

    <!-- 二次确认对话框 -->
    <ElDialog v-model="confirmDialogVisible" title="⚠️ 远程控制确认" width="480px" :close-on-click-modal="false">
      <ElAlert type="error" :closable="false" class="mb-16px">
        请仔细确认以下操作信息，写入指令一旦下发将直接作用于设备。
      </ElAlert>

      <ElDescriptions :column="1" border>
        <ElDescriptionsItem label="设备">
          {{ selectedDevice?.name || '—' }}
        </ElDescriptionsItem>
        <ElDescriptionsItem label="协议">
          {{ selectedDevice?.protocol || '—' }}
        </ElDescriptionsItem>
        <ElDescriptionsItem label="连接">
          {{ selectedDevice?.host }}:{{ selectedDevice?.port }} / #{{ selectedDevice?.slave_id }}
        </ElDescriptionsItem>
        <ElDescriptionsItem label="点位">
          {{ selectedTag?.name || '—' }} (地址 {{ selectedTag?.address ?? '—' }})
        </ElDescriptionsItem>
        <ElDescriptionsItem label="寄存器类型">
          {{ selectedTag?.register_type || '—' }}
        </ElDescriptionsItem>
        <ElDescriptionsItem label="当前值">
          {{ selectedTag?.value ?? '—' }}{{ selectedTag?.unit || '' }}
        </ElDescriptionsItem>
        <ElDescriptionsItem label="写入值">
          <span class="text-20px font-700 text-red-500">{{ form.value }}</span>
        </ElDescriptionsItem>
      </ElDescriptions>

      <div class="mt-16px">
        <div class="text-13px mb-8px">
          输入 <span class="font-700 text-red-500">确认</span> 以继续操作：
        </div>
        <ElInput
          v-model="confirmText"
          placeholder="请输入'确认'"
          @keyup.enter="confirmAndWrite"
        />
      </div>

      <template #footer>
        <ElButton @click="confirmDialogVisible = false">取消</ElButton>
        <ElButton
          type="danger"
          :loading="confirmBusy"
          :disabled="confirmText !== '确认'"
          @click="confirmAndWrite"
        >
          确认下发
        </ElButton>
      </template>
    </ElDialog>
  </ContentWrap>
</template>
