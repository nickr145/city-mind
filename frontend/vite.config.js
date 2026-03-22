import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/catalog': 'http://localhost:8000',
      '/audit':   'http://localhost:8000',
      '/query':   'http://localhost:8000',
      '/download': 'http://localhost:8000',
      '/view':    'http://localhost:8000',
      '/health':  'http://localhost:8000',
      '/sync':    'http://localhost:8000',
      '/geo':     'http://localhost:8000',
    },
  },
});
