import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  root: 'web',
  base: './',
  plugins: [react()],
  server: { host: '127.0.0.1', port: 1420, strictPort: true },
  preview: { host: '127.0.0.1', port: 4173, strictPort: true },
  build: { outDir: '../dist/web', emptyOutDir: true, target: 'es2022' },
  worker: { format: 'es' },
  test: { include: ['src/**/*.test.ts'], environment: 'node' },
});
