import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import tailwindcss from '@tailwindcss/vite'
import path from 'node:path'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  define: {
    'process.env.NODE_ENV': JSON.stringify('production'),
  },
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, './src'),
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    cssCodeSplit: false,
    lib: {
      entry: path.resolve(import.meta.dirname, './src/entry.tsx'),
      name: 'FusanheUIRuntime',
      formats: ['umd'],
      fileName: () => 'ui-runtime.js',
      cssFileName: 'ui',
    },
    rollupOptions: {
      output: {
        assetFileNames: '[name][extname]',
      },
    },
  },
})
