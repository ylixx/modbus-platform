/**
 * Common form validation rules.
 */
export const required = (message = '此项为必填项') => ({
  required: true,
  message,
  trigger: 'blur',
})

export const requiredSelect = (message = '请选择') => ({
  required: true,
  message,
  trigger: 'change',
})

export const minLength = (min, message) => ({
  min,
  message: message || `最少${min}个字符`,
  trigger: 'blur',
})

export const maxLength = (max, message) => ({
  max,
  message: message || `最多${max}个字符`,
  trigger: 'blur',
})

export const ipRule = () => ({
  pattern: /^(\d{1,3}\.){3}\d{1,3}$|^[\w.-]+$/,
  message: '请输入有效的IP地址或主机名',
  trigger: 'blur',
})

export const phoneRule = () => ({
  pattern: /^1[3-9]\d{9}$/,
  message: '请输入有效的手机号',
  trigger: 'blur',
})

export const portRule = () => ({
  type: 'number',
  min: 1,
  max: 65535,
  message: '端口范围 1-65535',
  trigger: 'blur',
})

export const numberRange = (min, max, message) => ({
  type: 'number',
  min,
  max,
  message: message || `范围 ${min}-${max}`,
  trigger: 'blur',
})
