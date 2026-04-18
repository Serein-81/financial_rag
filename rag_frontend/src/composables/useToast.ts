/**
 * Toast 通知封装
 * 基于 vue3-toastify 的统一通知接口
 */

import { toast } from 'vue3-toastify'

type ToastType = 'success' | 'error' | 'warning' | 'info'

interface ToastOptions {
  type?: ToastType
  message: string
  duration?: number
  title?: string
}

export const useToast = () => {
  /**
   * 通用通知
   */
  const show = (options: ToastOptions) => {
    const { type = 'info', message, duration = 3000, title } = options
    
    const content = title ? `${title}\n${message}` : message
    
    toast(content, {
      type,
      autoClose: duration,
      theme: 'colored',
      position: 'top-right'
    })
  }

  /**
   * 成功通知
   */
  const success = (message: string, title?: string, duration?: number) => {
    show({ type: 'success', message, title, duration })
  }

  /**
   * 错误通知
   */
  const error = (message: string, title?: string, duration?: number) => {
    show({ type: 'error', message, title, duration: duration || 5000 })
  }

  /**
   * 警告通知
   */
  const warning = (message: string, title?: string, duration?: number) => {
    show({ type: 'warning', message, title, duration })
  }

  /**
   * 信息通知
   */
  const info = (message: string, title?: string, duration?: number) => {
    show({ type: 'info', message, title, duration })
  }

  /**
   * Promise 通知（自动处理异步操作）
   */
  const promise = async <T>(
    promise: Promise<T>,
    messages: {
      pending?: string
      success?: string | ((result: T) => string)
      error?: string
    },
    duration?: number
  ): Promise<T> => {
    return toast.promise(
      promise,
      {
        pending: messages.pending || '处理中...',
        success: typeof messages.success === 'function' 
          ? messages.success 
          : (messages.success || '操作成功'),
        error: messages.error || '操作失败'
      },
      {
        autoClose: duration || 3000,
        theme: 'colored'
      }
    )
  }

  /**
   * 清除所有通知
   */
  const clear = () => {
    toast.clearAll()
  }

  /**
   * 更新通知
   */
  const update = (id: string | number, options: { type?: ToastType; message?: string }) => {
    toast.update(id, {
      type: options.type,
      render: options.message,
      autoClose: 3000
    })
  }

  return {
    show,
    success,
    error,
    warning,
    info,
    promise,
    clear,
    update,
    toast
  }
}

// 便捷函数（可在组件外使用）
export const $toast = {
  success: (message: string, title?: string) => toast.success(title ? `${title}\n${message}` : message),
  error: (message: string, title?: string) => toast.error(title ? `${title}\n${message}` : message, { autoClose: 5000 }),
  warning: (message: string, title?: string) => toast.warning(title ? `${title}\n${message}` : message),
  info: (message: string, title?: string) => toast.info(title ? `${title}\n${message}` : message),
}
