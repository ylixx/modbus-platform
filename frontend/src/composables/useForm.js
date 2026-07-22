/**
 * useForm composable — inspired by yudao's useForm pattern.
 *
 * Encapsulates: dialog visibility, form state, create/update logic,
 * validation, reset, and submit.
 *
 * Usage:
 *   const { form, dialogVisible, isEdit, openDialog, handleSubmit, resetForm } = useForm({
 *     defaultForm: { name: '', enabled: true },
 *     createApi: (data) => api.post('/devices', data),
 *     updateApi: (id, data) => api.put(`/devices/${id}`, data),
 *     onSuccess: () => fetchList(),
 *     validate: (form) => { if (!form.name) return '请输入名称' },
 *   })
 */
import { ref, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import { deepClone } from '../utils'

export function useForm(options = {}) {
  const {
    defaultForm = {},
    createApi,
    updateApi,
    onSuccess,
    onError,
    validate,
  } = options

  const dialogVisible = ref(false)
  const submitLoading = ref(false)
  const editingId = ref(null)
  const form = reactive(deepClone(defaultForm))

  /**
   * Is editing (has ID)
   */
  const isEdit = ref(false)

  /**
   * Open dialog for create or edit
   */
  function openDialog(row) {
    if (row) {
      isEdit.value = true
      editingId.value = row.id
      // Merge row data into form, preserving default keys
      Object.keys(defaultForm).forEach(key => {
        form[key] = row[key] !== undefined ? row[key] : defaultForm[key]
      })
    } else {
      isEdit.value = false
      editingId.value = null
      resetForm()
    }
    dialogVisible.value = true
  }

  /**
   * Reset form to defaults
   */
  function resetForm() {
    Object.keys(defaultForm).forEach(key => {
      form[key] = deepClone(defaultForm[key])
    })
  }

  /**
   * Close dialog
   */
  function closeDialog() {
    dialogVisible.value = false
  }

  /**
   * Submit form (create or update)
   */
  async function handleSubmit() {
    // Validate
    if (validate) {
      const error = validate(form)
      if (error) {
        ElMessage.warning(error)
        return
      }
    }

    submitLoading.value = true
    try {
      const payload = { ...form }
      if (isEdit.value && updateApi) {
        await updateApi(editingId.value, payload)
        ElMessage.success('更新成功')
      } else if (createApi) {
        await createApi(payload)
        ElMessage.success('创建成功')
      }
      dialogVisible.value = false
      onSuccess?.(payload, isEdit.value)
    } catch (e) {
      console.error('Form submit error:', e)
      onError?.(e)
    } finally {
      submitLoading.value = false
    }
  }

  return {
    form,
    dialogVisible,
    submitLoading,
    isEdit,
    editingId,
    openDialog,
    closeDialog,
    handleSubmit,
    resetForm,
  }
}
