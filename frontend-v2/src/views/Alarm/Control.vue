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
  ElTable,
  ElTableColumn,
  ElTag,
  ElMessage,
  ElMessageBox,
  ElEmpty
} from 'element-plus'
import { getAllDevices, getDeviceTags, writeDevice, unwrap, unwrapList } from '@/api/modbus'

defineOptions({ name: 'Control' })

const devices = ref<any[]>([])
const tags = ref<any[]>([])
const form = reactive<any>({ device_id: null, tag_id: null, value: '' })

const writableTags = computed(() => tags.value.filter((t) => t.writable))

const fetchDevices = async () => {
  devices.value = unwrapList(await getAllDevices()).list
}
const onDeviceChange = async () => {
  form.tag_id = null
  tags.value = []
  if (form.device_id == null) return
  const res = await getDeviceTags(form.device_id)
  const body = unwrap(res)
  tags.value = Array.isArray(body) ? body : unwrapList(res).list
}
const doWrite = async () => {
  if (form.device_id == null || form.tag_id == null) {
    ElMessage.warning('请选择设备和点位')
    return
  }
  const tag = tags.value.find((t) => t.id === form.tag_id)
  await ElMessageBox.confirm(`确认向点位「${tag?.name}」写入值 ${form.value} ？`, '远程控制确认', {
    type: 'warning'
  })
  await writeDevice(form.device_id, { tag_id: form.tag_id, value: Number(form.value) })
  ElMessage.success('写入指令已下发')
}

onMounted(fetchDevices)
</script>

<template>
  <ContentWrap title="远程控制" message="向可写点位下发控制指令，请谨慎操作">
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
        <ElInput v-model="form.value" placeholder="请输入要写入的数值" />
      </ElFormItem>
      <ElFormItem>
        <ElButton v-hasPermi="['device.control']" type="danger" @click="doWrite"
          >下发控制指令</ElButton
        >
      </ElFormItem>
    </ElForm>

    <div class="mt-16px">
      <div class="text-14px font-600 mb-8px">当前设备可写点位</div>
      <ElEmpty v-if="form.device_id == null" description="请先选择设备" :image-size="70" />
      <ElTable v-else :data="writableTags" border stripe>
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
  </ContentWrap>
</template>
