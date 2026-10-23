// F-04-T05: with VITE_FIXTURES=1 the /components gallery answers the generated client from the
// Brightwater Hale seed under a registered screen, as the persona and clock in the query string,
// and the screen mounts only once it does.
import { TooltipProvider } from "@abacus/ui";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "@tanstack/react-router";
import { cleanup, render, screen } from "@testing-library/react";
import { type JSX, useEffect, useState } from "react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";

vi.setConfig({ testTimeout: 30_000 });

// The lazy gallery chunk is large: transform it once before the first visit, so each visit's
// `findBy` waits on rendering rather than on the compile (F-05-T43 grew the registry).
beforeAll(async () => {
  await import("./pages");
}, 60_000);

afterEach(() => {
  cleanup();
  vi.unstubAllEnvs();
});

// Every visit gets a fresh module graph, so the probe reads the client and the clock from the
// same graph the gallery installs the seed into.
function Probe(): JSX.Element {
  const [text, setText] = useState("loading");
  useEffect(() => {
    void (async () => {
      const { listEngagements, firmClients } = await import("@abacus/api-client");
      const { nowMs } = await import("../app-core/clock");
      const [engagements, clients] = await Promise.all([listEngagements(), firmClients()]);
      setText(
        `${String(engagements.data?.length)} engagements, ${String(clients.data?.length)} clients, ${new Date(nowMs()).toISOString()}`,
      );
    })();
  }, []);
  return <p>{text}</p>;
}

async function visit(url: string): Promise<void> {
  vi.resetModules();
  window.history.pushState({}, "", url);
  const { client } = await import("@abacus/api-client/client");
  client.setConfig({ baseUrl: "http://fixture.test", throwOnError: true });
  const { registerScreen } = await import("./fixture-mode");
  registerScreen("SEED-01", { title: "Seed probe", Component: Probe });
  const { router } = await import("../router");
  render(
    <QueryClientProvider client={new QueryClient()}>
      <TooltipProvider>
        <RouterProvider router={router} />
      </TooltipProvider>
    </QueryClientProvider>,
  );
}

describe("the gallery loads the seed", () => {
  it("answers a registered screen from the seed at the demo instant", async () => {
    vi.stubEnv("VITE_FIXTURES", "1");
    await visit("/components/screens/SEED-01?frame=1");
    expect(
      await screen.findByText("28 engagements, 184 clients, 2026-09-14T14:24:00.000Z"),
    ).toBeTruthy();
  });

  it("reads the persona and clock from the query string (Lena Park never sees Ashford)", async () => {
    vi.stubEnv("VITE_FIXTURES", "1");
    await visit(
      "/components/screens/SEED-01?frame=1&as=lena-park&clock=2026-09-14T09:41:00-05:00",
    );
    expect(
      await screen.findByText("28 engagements, 183 clients, 2026-09-14T14:41:00.000Z"),
    ).toBeTruthy();
  });
});
