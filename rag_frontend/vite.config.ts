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
    port: 5500,
    host: '0.0.0.0',
    open: false,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
      },
      '/ws-api': {
        target: 'http://localhost:8000',
        ws: true,
        changeOrigin: true,
        secure: false,
        rewrite: (path: string) => path.replace(/^\/ws-api/, '/api'),
      },
    },
  },
})
