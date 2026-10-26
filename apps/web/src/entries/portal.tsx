import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "@tanstack/react-router";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { configurePortalClient } from "../app-core/auth/bff";
import "../index.css";
// `routes/portal/index` by name: `../routes/portal` is the firm bundle's legacy portal.tsx.
import { createPortalRouter } from "../routes/portal/index";

// The client portal's entry (P-08-T07; DEC-59): portal.html on the portal origin, built with
// `vite build --mode portal` into dist/portal. Same-origin /v1; the access token stays in memory
// and refreshes through the host cookie (app-core/auth/bff.ts, P-08-T11). It imports nothing of the
// firm's app (INV-4) and nothing of the design system: the providers and screens are lazy
// chunks (routes/portal). With VITE_FIXTURES=1 it answers from the portal fixtures, which a
// production build folds away.

configurePortalClient();

if (import.meta.env.VITE_FIXTURES === "1") {
  const { installPortalFixtures } = await import("../fixtures/install-portal");
  installPortalFixtures(window.location.search);
}

const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
const router = createPortalRouter();

const root = document.getElementById("root");
if (root === null) throw new Error("Missing #root element");

createRoot(root).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>,
);
