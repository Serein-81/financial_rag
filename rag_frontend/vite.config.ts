import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  server: {
    port: 5500,  // 使用 5500 端口
    host: '0.0.0.0',  // 允许所有网络访问
    open: false,  // 不自动打开浏览器
    strictPort: true,  // 强制使用 5500 端口，不自动切换
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        configure: (proxy) => {
          proxy.on('proxyReq', (proxyReq) => {
            if (proxyReq.getHeader('origin')) {
              proxyReq.setHeader('origin', 'http://localhost:8000')
            }
          })
        },
      },
    },
  },
})
