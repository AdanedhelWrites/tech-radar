import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    host: true,
    // Windows Docker bind mount dosya olayi uretmez; HMR icin dosyalar taranir
    watch: { usePolling: true, interval: 1000 },
    proxy: {
      '/api': { target: 'http://teknoloji-api:8000', changeOrigin: true },
      // Django admin ve statikleri gelistirmede de ayni kapidan (prod nginx.conf ile ayni)
      '/admin': { target: 'http://teknoloji-api:8000', changeOrigin: true },
      '/static': { target: 'http://teknoloji-api:8000', changeOrigin: true },
    },
  },
})
