// Shared helpers for screen tests: the generated client's `fetch` is replaced by a route table,
// so no test ever makes real HTTP. Sign-in goes through the real auth client (P-01-T11) with the
// BFF's refresh stubbed.
import { client } from "@abacus/api-client/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  Outlet,
  RouterProvider,
  type RouteComponent,
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
} from "@tanstack/react-router";
import { render } from "@testing-library/react";
import type { JSX } from "react";
import { vi } from "vitest";
import { configureClient } from "../api";
import { refreshSession, resetAuthForTest } from "../app-core/auth";

export interface Call {
  method: string;
  path: string;
  query: URLSearchParams;
  headers: Headers;
  body: unknown;
}

export type Handler = (call: Call) => Response | Promise<Response>;

export function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/** Routes are keyed "METHOD /path" (path without query). Unknown routes answer 404. */
/** JSON bodies are parsed; a raw file upload (SPEC-028) is kept as text. */
function parsed(text: string): unknown {
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return text;
  }
}

export function mockApi(routes: Record<string, Handler>): { calls: Call[] } {
  const calls: Call[] = [];
  const fetchMock = async (input: Request): Promise<Response> => {
    const text = await input.clone().text();
    const url = new URL(input.url);
    const call: Call = {
      method: input.method,
      path: url.pathname,
      query: url.searchParams,
      headers: input.headers,
      body: text === "" ? null : parsed(text),
    };
    calls.push(call);
    const handler = routes[`${call.method} ${call.path}`];
    return handler === undefined ? json({ detail: "no such route" }, 404) : handler(call);
  };
  configureClient();
  client.setConfig({ fetch: fetchMock as typeof fetch });
  return { calls };
}

/** A response that never arrives: the screen stays in its loading state. */
export function never(): Promise<Response> {
  return new Promise<Response>(() => undefined);
}

export function newQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 0 }, mutations: { retry: false } },
  });
}

/** Replaces `window.location` so `location.assign` (the redirect to sign in) can be observed. */
export function stubLocation(pathname = "/", search = ""): { assign: ReturnType<typeof vi.fn> } {
  const assign = vi.fn();
  vi.stubGlobal("location", {
    assign,
    origin: "http://localhost:5173",
    pathname,
    search,
    href: `http://localhost:5173${pathname}${search}`,
  });
  return { assign };
}

/** A fresh page holding the access token "tok": the real auth client's refresh, answered by a
 * stubbed BFF. The token came a minute ago, so a later 401 is a real expiry, not a rejected
 * fresh token. */
export async function signInForTest(): Promise<void> {
  resetAuthForTest();
  configureClient();
  const previous = client.getConfig().fetch;
  client.setConfig({
    fetch: () => Promise.resolve(json({ access_token: "tok", expires_in: 600 })),
  });
  try {
    await refreshSession(Date.now() - 60_000);
  } finally {
    // Back to what the test had, including none (the global fetch, read per request).
    client.setConfig({ fetch: previous } as Parameters<typeof client.setConfig>[0]);
  }
  stubLocation();
}

export function renderRoutes(
  routes: { path: string; component: RouteComponent }[],
  options: { root?: RouteComponent; at?: string } = {},
): ReturnType<typeof render> {
  const rootRoute = createRootRoute({ component: options.root ?? Outlet });
  const children = routes.map((r) =>
    createRoute({ getParentRoute: () => rootRoute, path: r.path, component: r.component }),
  );
  const router = createRouter({
    routeTree: rootRoute.addChildren(children),
    history: createMemoryHistory({ initialEntries: [options.at ?? "/"] }),
  });
  return render(
    <QueryClientProvider client={newQueryClient()}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

export function withQueries(ui: JSX.Element): ReturnType<typeof render> {
  return render(<QueryClientProvider client={newQueryClient()}>{ui}</QueryClientProvider>);
}
