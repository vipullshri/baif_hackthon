import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// BhashaSetu frontend build configuration.
// The production build is emitted directly into the backend so FastAPI can
// serve the whole app as a single offline deployable.
export default defineConfig({
  plugins: [react()],
  base: '/',
  server: {
    port: 5173,
    proxy: {
      // During `npm run dev`, forward API + WebSocket calls to the backend.
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        ws: true,
      },
    },
  },
  build: {
    outDir: '../backend/app/static',
    emptyOutDir: true,
    chunkSizeWarningLimit: 1200,
  },
})