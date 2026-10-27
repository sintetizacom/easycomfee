import { fileURLToPath } from 'node:url'
import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

// Pacote unico (IIFE) servido pelo app em /plenio/editor.js.
export default defineConfig({
  plugins: [vue()],
  define: {
    'process.env.NODE_ENV': JSON.stringify('production'),
    __VUE_OPTIONS_API__: 'false',
    __VUE_PROD_DEVTOOLS__: 'false',
    __VUE_PROD_HYDRATION_MISMATCH_DETAILS__: 'false'
  },
  build: {
    outDir: fileURLToPath(new URL('../../frontend/public/plenio', import.meta.url)),
    emptyOutDir: true,
    target: 'es2022',
    minify: true,
    lib: {
      entry: fileURLToPath(new URL('./editor-app.ts', import.meta.url)),
      formats: ['iife'],
      name: 'PlenioSheetBundle',
      fileName: () => 'editor.js'
    },
    rollupOptions: { output: { inlineDynamicImports: true } }
  }
})
