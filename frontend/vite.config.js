import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  // Load env file based on `mode` in the current working directory.
  // Set the third parameter to '' to load all env regardless of the `VITE_` prefix.
  const env = loadEnv(mode, process.cwd(), '')

  const proxyConfig = {
    '/api': {
      target: env.VITE_API_URL || 'http://localhost:8000',
      changeOrigin: true,
      rewrite: (path) => path.replace(/^\/api/, ''),
    },
  }

  // Only enable NetworkX API proxy in development mode
  // if (mode === 'development') {
  //   proxyConfig['/nx-api'] = {
  //     target: env.VITE_NX_API_URL || 'http://networkx-api:8001',
  //     changeOrigin: true,
  //     rewrite: (path) => path.replace(/^\/nx-api/, ''),
  //   }
  // }

  return {
    plugins: [react()],
    server: {
      proxy: proxyConfig,
    },
  }
})
