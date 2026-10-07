import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { type Plugin, loadEnv } from "vite";
import { defineConfig } from "vitest/config";

// Production pages carry a Content-Security-Policy (security review, TASK-012): scripts and
// styles from this origin only, network to this origin and the identity provider, no framing,
// plugins or base rewriting. Not applied in dev (Vite injects inline scripts for HMR); the
// deployment sets the same policy as a header (TASK-014).
function contentSecurityPolicy(authority: string): Plugin {
  const policy = [
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self'",
    "img-src 'self' data:",
    `connect-src 'self' ${authority}`,
    "frame-ancestors 'none'",
    "object-src 'none'",
    "base-uri 'none'",
    "form-action 'self'",
  ].join("; ");
  return {
    name: "abacus-csp",
    apply: "build",
    transformIndexHtml: () => [
      {
        tag: "meta",
        attrs: { "http-equiv": "Content-Security-Policy", content: policy },
        injectTo: "head-prepend",
      },
    ],
  };
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", "VITE_");
  const authority = env.VITE_OIDC_AUTHORITY ?? "http://127.0.0.1:9000";
  return {
    plugins: [react(), tailwindcss(), contentSecurityPolicy(authority)],
    server: {
      port: 5173,
      strictPort: true,
      // Same origin in the browser: /v1 goes to the API (make dev runs it on :8001). No CORS.
      proxy: { "/v1": "http://127.0.0.1:8001" },
    },
    test: {
      environment: "jsdom",
      include: ["src/**/*.test.{ts,tsx}"],
    },
  };
});
