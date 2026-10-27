// Q-01-T23 (platform-ops contract 3.2): the runtime config is required before the router starts.
// A missing, non-JSON or schema-invalid `/runtime-config.json` renders a plain error state, never
// a blank page and never a half-configured app. Both entries (the firm app and the portal) boot
// through here; the words name no product, because the portal never shows "Accrued" (DEC-01).
import type { JSX, ReactNode } from "react";
import { createRoot } from "react-dom/client";
import { type RuntimeConfig, loadRuntimeConfig } from "./runtime-config";

export const CONFIG_ERROR = {
  title: "This page can't load right now",
  body: "Its configuration is missing or unreadable. Try again in a few minutes.",
} as const;

/** The plain error state: no router, no data, no product name. */
export function ConfigError(): JSX.Element {
  return (
    <main
      role="alert"
      data-boot="config-error"
      className="flex min-h-screen flex-col items-center justify-center gap-[6px] bg-shell px-[16px] text-center"
    >
      <h1 className="text-pane font-medium text-ink">{CONFIG_ERROR.title}</h1>
      <p className="max-w-[420px] text-para text-ink-2">{CONFIG_ERROR.body}</p>
    </main>
  );
}

/** Load the runtime config, then render the app with it, or the error state without it. */
export async function bootWithRuntimeConfig(
  element: HTMLElement,
  app: (config: RuntimeConfig) => ReactNode,
  load: () => Promise<RuntimeConfig | null> = loadRuntimeConfig,
): Promise<RuntimeConfig | null> {
  const config = await load();
  createRoot(element).render(config === null ? <ConfigError /> : app(config));
  return config;
}
