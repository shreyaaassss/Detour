import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

const backend = process.env.DETOUR_API ?? 'http://localhost:8000'
const api = [
  'state', 'plan', 'scenario', 'reset', 'presets', 'disruptions', 'validate', 'audit', 'events', 'health',
  'incidents', 'offers', 'telephony', 'clock', 'notifications', 'messages',
]

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    proxy: Object.fromEntries(api.map((p) => [`/${p}`, { target: backend, changeOrigin: true }])),
  },
  test: { environment: 'node' },
})
