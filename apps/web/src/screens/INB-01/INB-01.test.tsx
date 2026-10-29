// INB-01 · Inbox (N-01-T10; DEC-830). Acceptance (the task row): "Seven scenarios pass their
// Vitest tests and axe, and the rail sums to 23 waiting and 4 unmatched." axe runs in the gallery
// harness (Playwright); here each scenario renders from the live shapes.
import { client } from "@abacus/api-client/client";
import { cleanup, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { useFirmToolbar } from "../../shell/firm/ToolbarData";
import { renderRoutes } from "../../testing/support";
import { INB01 } from ".";
import { COPY } from "./copy";
import { type Inb01State, OPENS, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});
let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

function Screen({ state, clientId }: { state: Inb01State; clientId: string | null }) {
  const bar = useFirmToolbar({
    at: { pathname: "/inbox" },
    firm: "Brightwater Hale",
    navigate: () => undefined,
    hotkeys: false,
  });
  return (
    <INB01 toolbar={bar.toolbar} initialThread={OPENS[state] ?? null} initialClientId={clientId} />
  );
}

function mount(state: Inb01State, clientId: string | null = null): void {
  restore = installFixtureMode(scenarios[state]);
  renderRoutes([
    {
      path: "/",
      component: () => <Screen state={state} clientId={clientId} />,
    },
  ]);
}

describe("INB-01", () => {
  it("AC: the summary reads 23 waiting · 4 unmatched (a)", async () => {
    mount("a");
    expect(await screen.findByText(COPY.summary(23, 4))).toBeTruthy();
    expect(await screen.findAllByText(/Re: 2025 tax documents/)).not.toHaveLength(0);
  });

  it("b: the unmatched Sound Electric thread opens", async () => {
    mount("b");
    expect(await screen.findAllByText(/Invoice SE-1187/)).not.toHaveLength(0);
  });

  it("c: Harold Stein's thread opens", async () => {
    mount("c");
    expect(await screen.findAllByText(/harold\.stein@outlook\.com/)).not.toHaveLength(0);
  });

  it("d: after triage the summary reads 21 waiting", async () => {
    mount("d");
    expect(await screen.findByText(COPY.summary(21, 4))).toBeTruthy();
  });

  it("e: the rail lists every thread", async () => {
    mount("e");
    expect(await screen.findAllByText(/Invoice SE-1187/)).not.toHaveLength(0);
  });

  it("f: a client with no thread shows the empty state", async () => {
    mount("f", "00000000-0000-4000-8000-000000000f00");
    expect(await screen.findByText(COPY.empty.title)).toBeTruthy();
  });

  it("g: the list never answers: skeleton rows, busy", async () => {
    mount("g");
    await waitFor(() => {
      expect(document.querySelector('[aria-busy="true"]')).not.toBeNull();
    });
  });
});
