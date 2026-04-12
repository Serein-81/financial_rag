// API Configuration
// 从环境变量读取 API 基础地址，只需修改 .env 文件即可

export const API_BASE = import.meta.env.VITE_API_BASE || ''

console.log('🔧 API Base URL:', API_BASE || '(使用相对路径/Vite代理)')
