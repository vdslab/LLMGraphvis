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
      configure: (proxy) => {
        proxy.on('error', (err) => {
          console.log('proxy error', err);
        });
        proxy.on('proxyReq', (proxyReq, req) => {
          console.log('Sending Request to the Target:', req.method, req.url);
        });
        proxy.on('proxyRes', (proxyRes, req, res) => {
          console.log('Received Response from the Target:', proxyRes.statusCode, req.url);
          // Vite 8's proxy holds response headers until the first body chunk,
          // so an SSE stream would not open until the backend's first ping.
          // The proxy copies headers synchronously after this event; flush
          // them right after that.
          if (proxyRes.headers['content-type']?.startsWith('text/event-stream')) {
            queueMicrotask(() => res.flushHeaders());
          }
        });
      },
    },
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
      include: ['src/tests/**/*.{test,spec}.{js,jsx}'],
    },
  }
})
