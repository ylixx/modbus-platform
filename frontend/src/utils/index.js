/**
 * Common utility functions.
 */
import dayjs from 'dayjs'

/**
 * Format datetime string
 */
export function formatTime(time, fmt = 'YYYY-MM-DD HH:mm:ss') {
  if (!time) return '-'
  return dayjs(time).format(fmt)
}

/**
 * Format number with fixed decimals
 */
export function formatNumber(val, decimals = 2) {
  if (val === null || val === undefined) return '--'
  if (typeof val === 'number') return val.toFixed(decimals)
  return String(val)
}

/**
 * Download content as file
 */
export function downloadFile(content, filename, mimeType = 'text/csv;charset=utf-8;') {
  const blob = new Blob(['\ufeff' + content], { type: mimeType })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

/**
 * Download from API response blob
 */
export function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

/**
 * Generate timestamped filename
 */
export function timestampFilename(prefix, ext = 'csv') {
  return `${prefix}_${dayjs().format('YYYYMMDD_HHmmss')}.${ext}`
}

/**
 * Export array of objects to CSV
 */
export function exportToCSV(rows, headers, filename) {
  if (!rows.length) return
  const csvHeader = headers.map(h => `"${h.label}"`).join(',')
  const csvRows = rows.map(row =>
    headers.map(h => {
      const val = row[h.key]
      return `"${String(val ?? '').replace(/"/g, '""')}"`
    }).join(',')
  )
  downloadFile([csvHeader, ...csvRows].join('\n'), filename)
}

/**
 * Debounce function
 */
export function debounce(fn, delay = 300) {
  let timer = null
  return function (...args) {
    if (timer) clearTimeout(timer)
    timer = setTimeout(() => fn.apply(this, args), delay)
  }
}

/**
 * Deep clone (simple version)
 */
export function deepClone(obj) {
  return JSON.parse(JSON.stringify(obj))
}

/**
 * Parse JSON safely
 */
export function parseJSON(str, fallback = null) {
  try {
    return JSON.parse(str)
  } catch {
    return fallback
  }
}
