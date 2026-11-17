import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined;
          if (id.includes('react-dom') || id.includes(`${'/'}react${'/'}`) || id.includes('\\react\\')) return 'react';
          if (id.includes('motion')) return 'motion';
          if (id.includes('@dnd-kit')) return 'dnd';
          if (id.includes('lucide-react')) return 'icons';
          if (id.includes('socket.io')) return 'realtime';
          return undefined;
        },
      },
    },
  },
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:5000',
      '/socket.io': {
        target: 'http://127.0.0.1:5000',
        ws: true,
      },
      '/static': 'http://127.0.0.1:5000',
    },
  },
})
