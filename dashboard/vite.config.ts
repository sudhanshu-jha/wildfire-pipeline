import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api/ingestion': { target: 'http://localhost:8001', rewrite: (p) => p.replace('/api/ingestion', '') },
      '/api/detection': { target: 'http://localhost:8002', rewrite: (p) => p.replace('/api/detection', '') },
      '/api/prediction': { target: 'http://localhost:8003', rewrite: (p) => p.replace('/api/prediction', '') },
      '/api/alerting': {
        target: 'http://localhost:8004',
        rewrite: (p) => p.replace('/api/alerting', ''),
        ws: true,
      },
    },
  },
})
