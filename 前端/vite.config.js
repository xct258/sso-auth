import { fileURLToPath, URL } from 'node:url'

import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

// 开发时把 /api 反代到本机 auth-server（默认 8290）。
// 生产构建输出到 auth-server/static/dist，由 FastAPI 直接托管。
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    host: true,
    port: 5182,
    allowedHosts: ['.xct258.top'],
    proxy: {
      '/api': {
        target: process.env.VITE_PROXY_TARGET || 'http://127.0.0.1:8290',
        changeOrigin: true,
      },
    },
  },
  preview: {
    host: true,
    port: 5183,
    allowedHosts: ['.xct258.top'],
  },
  build: {
    outDir: '../static/dist',
    emptyOutDir: true,
  },
})
