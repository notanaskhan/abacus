// Generates src/ from openapi.json (ADR-013). Run `make generate` from the repository root.
import { defineConfig } from '@hey-api/openapi-ts';

export default defineConfig({
  input: './openapi.json',
  output: { path: './src' },
  plugins: ['@hey-api/client-fetch', '@hey-api/typescript', '@hey-api/sdk', '@tanstack/react-query'],
});
