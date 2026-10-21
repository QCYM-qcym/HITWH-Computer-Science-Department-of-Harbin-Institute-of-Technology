import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  build: { outDir: 'dist.local' },
  resolve: { alias: { '@fixtures': fileURLToPath(new URL('../../tests/fixtures', import.meta.url)) } },
  server: { proxy: { '/api': 'http://127.0.0.1:8101' } },
  test: { environment: 'jsdom', include: ['src/__tests__/**/*.test.ts'], restoreMocks: true },
})
