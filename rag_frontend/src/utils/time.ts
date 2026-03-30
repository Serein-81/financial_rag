/**
 * 统一时间工具函数
 * 
 * 所有项目中的时间处理都应使用此模块，确保统一的时间显示格式
 */

/**
 * 格式化时间戳为相对时间字符串
 */
export function formatTimestamp(timestamp: number): string {
  if (!timestamp && timestamp !== 0) {
    return '未知时间'
  }
  
  const date = new Date(timestamp)
  
  if (isNaN(date.getTime())) {
    return '无效时间'
  }
  
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMins / 60)
  const diffDays = Math.floor(diffHours / 24)

  if (diffMins < 1) return 'Just now'
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays < 7) return `${diffDays}d ago`

  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

/**
 * 格式化时间戳为短日期格式
 */
export function formatShortDate(timestamp: number): string {
  if (!timestamp && timestamp !== 0) {
    return '未知'
  }
  
  const date = new Date(timestamp)
  
  if (isNaN(date.getTime())) {
    return '无效'
  }
  
  return date.toLocaleDateString('en-US', {
    month: '2-digit',
    day: '2-digit',
  })
}

/**
 * 统一格式化聊天时间（相对时间 + 绝对时间）
 * 
 * 格式规则：
 * - 今天：今天 HH:mm
 * - 昨天：昨天 HH:mm
 * - 7天内：X天前
 * - 其他：YYYY-MM-DD
 * 
 * @param dateString ISO 格式的时间字符串或时间戳
 * @returns 格式化后的时间字符串
 */
export function formatChatTime(dateString: string | number | null | undefined): string {
  if (!dateString) {
    return '未知时间'
  }
  
  const date = new Date(dateString)
  
  if (isNaN(date.getTime())) {
    return '无效时间'
  }
  
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

  if (diffDays === 0) {
    return '今天 ' + date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  } else if (diffDays === 1) {
    return '昨天 ' + date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  } else if (diffDays < 7) {
    return diffDays + '天前'
  } else {
    return date.toLocaleDateString('zh-CN')
  }
}

/**
 * 格式化日期为 YYYY-MM-DD HH:mm:ss 格式
 * 
 * @param dateString ISO 格式的时间字符串或时间戳
 * @returns 格式化后的完整时间字符串
 */
export function formatFullDateTime(dateString: string | number): string {
  if (!dateString) {
    return '未知时间'
  }
  
  const date = new Date(dateString)
  
  if (isNaN(date.getTime())) {
    return '无效时间'
  }
  
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')
  const seconds = String(date.getSeconds()).padStart(2, '0')
  
  return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`
}

/**
 * 获取友好的相对时间描述
 * 
 * @param dateString ISO 格式的时间字符串或时间戳
 * @returns 相对时间描述
 */
export function getRelativeTime(dateString: string | number): string {
  if (!dateString) {
    return '未知时间'
  }
  
  const date = new Date(dateString)
  
  if (isNaN(date.getTime())) {
    return '无效时间'
  }
  
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffSecs = Math.floor(diffMs / 1000)
  const diffMins = Math.floor(diffSecs / 60)
  const diffHours = Math.floor(diffMins / 60)
  const diffDays = Math.floor(diffHours / 24)

  if (diffSecs < 60) return '刚刚'
  if (diffMins < 60) return `${diffMins}分钟前`
  if (diffHours < 24) return `${diffHours}小时前`
  if (diffDays < 7) return `${diffDays}天前`
  if (diffDays < 30) return `${Math.floor(diffDays / 7)}周前`
  if (diffDays < 365) return `${Math.floor(diffDays / 30)}个月前`
  
  return `${Math.floor(diffDays / 365)}年前`
}
