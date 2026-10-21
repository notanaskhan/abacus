import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "@tanstack/react-router";
import { Toaster, TooltipProvider } from "@abacus/ui";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { configureClient, shouldRetry } from "./api";
import "./index.css";
import { router } from "./router";

configureClient();
// `make dev-fixtures` (VITE_FIXTURES=1): the generated client answers from the Brightwater Hale
// seed, as the persona in `?as=` at the clock in `?clock=` (F-04-T05). A production build folds
// the flag to a constant and drops the seed.
if (import.meta.env.VITE_FIXTURES === "1") {
  const { installSeedFromSearch } = await import("./fixtures/install");
  installSeedFromSearch(window.location.search);
}
const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: shouldRetry, staleTime: 10_000 } },
});

const root = document.getElementById("root");
if (root === null) {
  throw new Error("Missing #root element");
}

createRoot(root).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <RouterProvider router={router} />
        <Toaster />
      </TooltipProvider>
    </QueryClientProvider>
  </StrictMode>,
);
