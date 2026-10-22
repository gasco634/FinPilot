import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: { host: '0.0.0.0', port: 5173 },
  test: { environment: 'jsdom' },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('/node_modules/recharts/')) return 'charts'
          if (id.includes('/node_modules/framer-motion/') || id.includes('/node_modules/motion-dom/')) return 'motion'
          if (id.includes('/node_modules/lucide-react/')) return 'icons'
          if (id.includes('/node_modules/@tanstack/')) return 'query'
          if (id.includes('/node_modules/react') || id.includes('/node_modules/scheduler/')) return 'react-vendor'
        },
      },
    },
  },
})
