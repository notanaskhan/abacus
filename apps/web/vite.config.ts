import path from "node:path";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { type Plugin, loadEnv } from "vite";
import { defineConfig } from "vitest/config";

// Production pages carry a Content-Security-Policy (security review, TASK-012): scripts and
// styles from this origin only, network to this origin only, no framing, plugins or base
// rewriting. Not applied in dev (Vite injects inline scripts for HMR); the deployment sets the
// same policy as a header (TASK-014). P-01 AC 5.1.6 (P-01-T11): the BFF exchanges the code, so the
// SPA only navigates to the identity provider and `connect-src` is back to 'self'.
function contentSecurityPolicy(): Plugin {
  const policy = [
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self'",
    "img-src 'self' data:",
    "connect-src 'self'",
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

// DEC-1006: the portal build swaps the UI kit's icon registry for its portal subset, so a portal
// page ships only the glyphs portal code can name (src/portal/icon-registry.test.ts holds it
// complete). The firm app keeps the full registry.
function portalIcons(): Plugin {
  return {
    name: "abacus-portal-icons",
    enforce: "pre",
    resolveId(source, importer) {
      if (source !== "./registry" || importer === undefined) return null;
      if (!/[\\/]packages[\\/]ui[\\/]src[\\/]icons[\\/][^\\/]+$/.test(importer)) return null;
      return path.join(path.dirname(importer), "portal-registry.ts");
    },
  };
}

export default defineConfig(({ mode, command }) => {
  const env = loadEnv(mode, ".", ["VITE_", "ABACUS_PORT_OFFSET"]);
  // `vite build --mode portal` (P-08-T07; `build:portal`): the client portal's own entry,
  // portal.html, into dist/portal, with no gallery and no firm entry (the same-origin CSP).
  const portal = mode === "portal";
  // The /components gallery (F-05-T09): on for the dev server and tests, off for any build unless
  // VITE_UI_GALLERY=1 opts in. `define` makes the flag a constant, so a production build drops the
  // gallery's routes and its lazy chunk entirely.
  const gallery = portal ? "" : (env.VITE_UI_GALLERY ?? (command === "serve" ? "1" : ""));
  // This worktree's port offset (F-01-T09; `make worktree-env`): 0 in the primary checkout and CI.
  const offset = Number(env.ABACUS_PORT_OFFSET ?? "0") || 0;
  return {
    plugins: [
      react(),
      tailwindcss(),
      contentSecurityPolicy(),
      fontPreload(),
      ...(portal ? [portalIcons()] : []),
    ],
    define: {
      "import.meta.env.VITE_UI_GALLERY": JSON.stringify(gallery),
      // Fixture mode (F-04-T04, T05): `make dev-fixtures` sets VITE_FIXTURES=1. A build folds it
      // to a constant, as the gallery flag is, so a production build drops the seed; the dev
      // server and tests read it live.
      ...(command === "build"
        ? { "import.meta.env.VITE_FIXTURES": JSON.stringify(env.VITE_FIXTURES ?? "") }
        : {}),
    },
    // dist/.vite/manifest.json: scripts/bundle-budget.mjs (F-05-T17) reads the chunk graph from it.
    build: portal
      ? { manifest: true, outDir: "dist/portal", rollupOptions: { input: "portal.html" } }
      : {
          manifest: true,
          // TASK-1368 (DEC-464): the framework every firm page boots with in one chunk. Left to
          // the default splitting, each lazy chunk that shares a few of these modules with the
          // entry split them into their own small common chunks, and the firm initial load paid
          // several KB of gzip for the fragmentation alone. Only modules the shell loads anyway.
          rolldownOptions: {
            output: {
              codeSplitting: {
                groups: [
                  {
                    name: "framework",
                    test: /node_modules[\\/](react|react-dom|scheduler|@tanstack|@radix-ui|@floating-ui|tailwind-merge)[\\/]/,
                  },
                ],
              },
            },
          },
        },
    server: {
      port: 5173 + offset,
      strictPort: true,
      // Same origin in the browser: /v1 goes to the API (make dev runs it on :8001 + offset).
      proxy: { "/v1": `http://127.0.0.1:${String(8001 + offset)}` },
    },
    test: {
      environment: "jsdom",
      include: ["src/**/*.test.{ts,tsx}"],
      // The tokens page reads theme.css as text (`?raw`); Vitest otherwise blanks every .css.
      css: { include: [/theme\.css/] },
    },
  };
});
