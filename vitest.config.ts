// Vitest config. `npm run test` runs every *.test.ts under src/ once and exits.
import { defineConfig } from 'vitest/config'

export default defineConfig({
  test: {
    // jsdom gives tests a real DOM (DOMParser, document, etc.) without a browser —
    // required because DocumentStore is built on DOMParser + querySelector.
    environment: 'jsdom',
    include: ['src/**/*.test.ts'],
  },
})
