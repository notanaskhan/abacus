import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "@tanstack/react-router";
import { Toaster, TooltipProvider } from "@abacus/ui";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { configureClient, sessionHeaders, shouldRetry } from "./api";
import { loadRuntimeConfig, telemetryTarget } from "./app-core/runtime-config";
import "./index.css";
import { router } from "./router";

configureClient();
// `make dev-fixtures` (VITE_FIXTURES=1): the generated client answers from the Brightwater Hale
// seed, as the persona in `?as=` at the clock in `?clock=` (F-04-T05), with a screen's scenario
// laid over it where `?scenario=` names one (a journey walking a screen built on fixtures). A
// production build folds the flag to a constant and drops the seed.
if (import.meta.env.VITE_FIXTURES === "1") {
  const { installSeedFromSearch, resolveOpens, screenScenarioFromSearch } =
    await import("./fixtures/install");
  const screen = await screenScenarioFromSearch(window.location.search);
  installSeedFromSearch(window.location.search, screen?.scenario);
  if (screen !== undefined) {
    const path = resolveOpens(window.location.pathname, screen.opens);
    if (path !== window.location.pathname) {
      window.history.replaceState(null, "", `${path}${window.location.search}`);
    }
  }
}
// Q-01-T50: browser error reporting, off unless the runtime config names a DSN and the tunnel.
// The SDK is a lazy chunk, so a host with reporting off never downloads it.
void loadRuntimeConfig().then(async (config) => {
  if (config === null || telemetryTarget(config) === null) return;
  const { startTelemetry } = await import("./app-core/telemetry");
  startTelemetry(config, {
    routeTemplate: () => router.state.matches.at(-1)?.fullPath,
    sessionHeaders,
  });
});
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
