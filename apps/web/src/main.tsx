import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "@tanstack/react-router";
import { Toaster, TooltipProvider } from "@abacus/ui";
import { StrictMode } from "react";
import { configureClient, sessionHeaders, shouldRetry } from "./api";
import { bootWithRuntimeConfig } from "./app-core/boot";
import { telemetryTarget } from "./app-core/runtime-config";
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

// Q-01-T23: the router starts only with a valid runtime config; otherwise the plain error state.
// A promise chain, not a top-level await: an entry module that awaits at the top level makes
// Rollup split every module it shares with a lazy route into its own chunk (so no route chunk
// imports from an entry still evaluating), which broke the firm initial bundle budget (TASK-1368).
void bootWithRuntimeConfig(root, () => (
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <RouterProvider router={router} />
        <Toaster />
      </TooltipProvider>
    </QueryClientProvider>
  </StrictMode>
)).then(async (config) => {
  // Q-01-T50: browser error reporting, off unless the runtime config names a DSN and the tunnel.
  // The SDK is a lazy chunk, so a host with reporting off never downloads it.
  if (config === null || telemetryTarget(config) === null) return;
  const { startTelemetry } = await import("./app-core/telemetry");
  startTelemetry(config, {
    routeTemplate: () => router.state.matches.at(-1)?.fullPath,
    sessionHeaders,
  });
});
