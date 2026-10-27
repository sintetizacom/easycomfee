import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Em desenvolvimento o front roda em 5173 e o backend em 8600; o proxy evita
// CORS e faz o WebSocket funcionar no mesmo endereco da pagina.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:8600',
      '/ws': { target: 'ws://127.0.0.1:8600', ws: true },
    },
  },
})
