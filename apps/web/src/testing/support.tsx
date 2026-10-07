// Shared helpers for screen tests: the generated client's `fetch` is replaced by a route table,
// so no test ever makes real HTTP. Sign-in goes through the real session code with the identity
// provider's token endpoint stubbed.
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
import { completeSignIn, signIn } from "../auth/session";

export interface Call {
  method: string;
  path: string;
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
export function mockApi(routes: Record<string, Handler>): { calls: Call[] } {
  const calls: Call[] = [];
  const fetchMock = async (input: Request): Promise<Response> => {
    const text = await input.clone().text();
    const call: Call = {
      method: input.method,
      path: new URL(input.url).pathname,
      headers: input.headers,
      body: text === "" ? null : (JSON.parse(text) as unknown),
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
export function stubLocation(pathname = "/"): { assign: ReturnType<typeof vi.fn> } {
  const assign = vi.fn();
  vi.stubGlobal("location", {
    assign,
    origin: "http://localhost:5173",
    pathname,
    search: "",
    href: `http://localhost:5173${pathname}`,
  });
  return { assign };
}

/** Signs in through the real `signIn` and `completeSignIn`, with the token endpoint stubbed. */
export async function signInForTest(): Promise<void> {
  const { assign } = stubLocation();
  await signIn("/");
  const url = new URL(String(assign.mock.calls[0]?.[0]));
  const state = url.searchParams.get("state") ?? "";
  vi.stubGlobal(
    "fetch",
    vi.fn(() =>
      Promise.resolve(json({ access_token: "tok", token_type: "Bearer", expires_in: 600 })),
    ),
  );
  await completeSignIn(`?code=c1&state=${state}`);
  vi.unstubAllGlobals();
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
