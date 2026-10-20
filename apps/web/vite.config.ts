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

// Geist and Geist Mono are eager (F-05-T04): preload their woff2 files in the production page so
// the first paint does not wait for the stylesheet to name them. Same-origin, so the CSP above
// already allows them. The document fonts (Arimo, Gelasio) are never preloaded.
function fontPreload(): Plugin {
  let base = "/";
  return {
    name: "abacus-font-preload",
    apply: "build",
    configResolved: (config) => {
      base = config.base;
    },
    transformIndexHtml: {
      order: "post",
      handler: (_html, context) =>
        Object.keys(context.bundle ?? {})
          .filter((file) => /geist(-mono)?-latin-(400|500)-normal[^/]*\.woff2$/.test(file))
          .sort()
          .map((file) => ({
            tag: "link",
            attrs: {
              rel: "preload",
              as: "font",
              type: "font/woff2",
              crossorigin: "",
              href: `${base}${file}`,
            },
            injectTo: "head" as const,
          })),
    },
  };
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", ["VITE_", "ABACUS_PORT_OFFSET"]);
  // This worktree's port offset (F-01-T09; `make worktree-env`): 0 in the primary checkout and CI.
  const offset = Number(env.ABACUS_PORT_OFFSET ?? "0") || 0;
  const authority = env.VITE_OIDC_AUTHORITY ?? `http://127.0.0.1:${String(9000 + offset)}`;
  return {
    plugins: [react(), tailwindcss(), contentSecurityPolicy(authority), fontPreload()],
    server: {
      port: 5173 + offset,
      strictPort: true,
      // Same origin in the browser: /v1 goes to the API (make dev runs it on :8001 + offset).
      proxy: { "/v1": `http://127.0.0.1:${String(8001 + offset)}` },
    },
    test: {
      environment: "jsdom",
      include: ["src/**/*.test.{ts,tsx}"],
    },
  };
});
