import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'

export type ExportFormat = 'pdf' | 'word' | 'excel'
export type ExportStatus = 'idle' | 'preparing' | 'exporting' | 'completed' | 'failed'

export interface ExportProgress {
  status: ExportStatus
  progress: number
  message: string
  fileName?: string
  startTime?: number
  endTime?: number
}

export function useExport() {
  const exportProgress = ref<ExportProgress>({
    status: 'idle',
    progress: 0,
    message: ''
  })

  const isExporting = computed(() => exportProgress.value.status === 'preparing' || exportProgress.value.status === 'exporting')

  const estimatedTimeRemaining = computed(() => {
    if (exportProgress.value.status !== 'exporting' || !exportProgress.value.startTime) {
      return null
    }

    const elapsed = Date.now() - exportProgress.value.startTime
    const progress = exportProgress.value.progress

    if (progress === 0) return null

    const totalEstimated = (elapsed / progress) * 100
    const remaining = totalEstimated - elapsed

    return Math.max(0, Math.round(remaining / 1000))
  })

  function setProgress(status: ExportStatus, progress: number, message: string) {
    exportProgress.value = {
      ...exportProgress.value,
      status,
      progress,
      message
    }

    if (status === 'exporting' && !exportProgress.value.startTime) {
      exportProgress.value.startTime = Date.now()
    }

    if (status === 'completed' || status === 'failed') {
      exportProgress.value.endTime = Date.now()
    }
  }

  function resetProgress() {
    exportProgress.value = {
      status: 'idle',
      progress: 0,
      message: ''
    }
  }

  async function downloadFile(blob: Blob, fileName: string) {
    try {
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = fileName
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      window.URL.revokeObjectURL(url)
    } catch (error) {
      console.error('Download failed:', error)
      throw error
    }
  }

  function getFileExtension(format: ExportFormat): string {
    const extensions = {
      pdf: 'pdf',
      word: 'docx',
      excel: 'xlsx'
    }
    return extensions[format]
  }

  function generateFileName(baseName: string, format: ExportFormat): string {
    const timestamp = new Date().toISOString().split('T')[0]
    const extension = getFileExtension(format)
    return `${baseName}_${timestamp}.${extension}`
  }

  async function exportWithProgress(
    exportFn: () => Promise<Blob>,
    baseFileName: string,
    format: ExportFormat,
    onProgress?: (progress: number, message: string) => void
  ): Promise<void> {
    try {
      setProgress('preparing', 10, '准备导出数据...')
      onProgress?.(10, '准备导出数据...')

      await new Promise(resolve => setTimeout(resolve, 300))

      setProgress('exporting', 30, '正在获取数据...')
      onProgress?.(30, '正在获取数据...')

      await new Promise(resolve => setTimeout(resolve, 200))

      setProgress('exporting', 60, '正在生成文件...')
      onProgress?.(60, '正在生成文件...')

      const blob = await exportFn()

      setProgress('exporting', 90, '正在下载文件...')
      onProgress?.(90, '正在下载文件...')

      await downloadFile(blob, generateFileName(baseFileName, format))

      setProgress('completed', 100, '导出成功！')
      onProgress?.(100, '导出成功！')

      ElMessage.success('文件导出成功')

      setTimeout(() => {
        resetProgress()
      }, 2000)

    } catch (error: any) {
      setProgress('failed', 0, `导出失败: ${error.message || '未知错误'}`)
      ElMessage.error(`导出失败: ${error.message || '请重试'}`)
      console.error('Export error:', error)
      throw error
    }
  }

  return {
    exportProgress,
    isExporting,
    estimatedTimeRemaining,
    setProgress,
    resetProgress,
    downloadFile,
    generateFileName,
    exportWithProgress
  }
}
