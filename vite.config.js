import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'VITE_');
  const target = env.VITE_API_BASE_URL || 'http://localhost:8000';
  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        // Prevents CORS errors with the ML reference FastAPI during local development.
        '/api': { target, changeOrigin: true, rewrite: (path) => path.replace(/^\/api/, '') },
      },
    },
  };
});
