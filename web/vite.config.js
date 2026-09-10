import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Privacy-first SPA: no server, no API routes — everything runs in the browser.
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: 'dist',
    rollupOptions: {
      output: {
        // Recharts is ~2/3 of the bundle and changes far less often than the
        // app code. Splitting it (and React) out means a redeploy only
        // invalidates the small app chunk, not 580 kB of vendor code.
        manualChunks: {
          react: ['react', 'react-dom'],
          charts: ['recharts'],
        },
      },
    },
  },
})
