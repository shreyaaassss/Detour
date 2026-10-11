import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

const backend = process.env.DETOUR_API ?? 'http://localhost:8000'
const api = [
  'state', 'plan', 'scenario', 'reset', 'presets', 'disruptions', 'validate', 'audit', 'events', 'health',
  'incidents', 'offers', 'telephony', 'clock', 'notifications', 'messages', 'interpreter', 'voice', 'site',
]

const proxy = Object.fromEntries(api.map((p) => [`/${p}`, { target: backend, changeOrigin: true }]))

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    allowedHosts: true, // dev only: lets a tunnel such as cloudflared reach the dev server by its own hostname
    proxy,
  },
  // `npm run build && npm run preview`: one small bundle, much faster through a tunnel than the dev server
  preview: { host: true, allowedHosts: true, proxy },
  test: { environment: 'node' },
})
