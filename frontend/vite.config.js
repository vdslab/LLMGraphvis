import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  // Load env file based on `mode` in the current working directory.
  // Set the third parameter to '' to load all env regardless of the `VITE_` prefix.
  const env = loadEnv(mode, process.cwd(), '')

  const proxyConfig = {
    '/api': {
      target: process.env.VITE_API_URL || env.VITE_API_URL || 'http://localhost:8000',
      changeOrigin: true,
      secure: false,
      rewrite: (path) => path.replace(/^\/api/, ''),
      configure: (proxy, _options) => {
        proxy.on('error', (err, _req, _res) => {
          console.log('proxy error', err);
        });
        proxy.on('proxyReq', (proxyReq, req, _res) => {
          console.log('Sending Request to the Target:', req.method, req.url);
        });
        proxy.on('proxyRes', (proxyRes, req, _res) => {
          console.log('Received Response from the Target:', proxyRes.statusCode, req.url);
        });
      },
    },
  }

  // Only enable NetworkX API proxy in development mode
  if (mode === 'development') {
    proxyConfig['/nx-api'] = {
      target: process.env.VITE_NX_API_URL || env.VITE_NX_API_URL || 'http://networkx-api:8001',
      changeOrigin: true,
      secure: false,
      rewrite: (path) => path.replace(/^\/nx-api/, ''),
      configure: (proxy, _options) => {
        proxy.on('error', (err, _req, _res) => {
          console.log('nx-api proxy error', err);
        });
      },
    }
  }

  return {
    plugins: [react()],
    server: {
      host: '0.0.0.0',
      port: 5173,
      proxy: proxyConfig,
      hmr: {
        // clientPort: 5173, // Remove to facilitate tunneling
      },
      watch: {
        usePolling: true,
      },
      cors: true, // Enable CORS
    },
    test: {
      globals: true,
      environment: 'jsdom',
      setupFiles: './src/setupTests.js',
    },
  }
})
