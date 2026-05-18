import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

const omegaBackend = process.env.OMEGA_BACKEND_URL ?? 'http://localhost:3000'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': omegaBackend,
      '/camera.jpg': omegaBackend,
      '/camera.mjpg': omegaBackend,
    },
  },
})
