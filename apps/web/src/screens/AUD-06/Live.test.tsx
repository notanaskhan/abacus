// A-02-T24 (TASK-1472): AUD-06's live swap in fixture mode. Adopt from the empty state, the
// newer-TB banner and its re-version with a reason, Open in Excel, the source menu's Ask client to
// reconnect, and Sign off… opening its overlay target. Each asserts the request the screen sends
// through the generated client; the figures are the server's (fixtures).
import type { TbLayerViewOut } from "@abacus/api-client";
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { type JSX } from "react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import {
  type FixtureHandler,
  type FixtureRequest,
  type Scenario,
  installFixtureMode,
  json,
} from "../../app-core/fixture-mode";
import { newQueryClient } from "../../testing/support";
import { AUD06Frame } from "./artboard";
import { OPENS, scenarios } from "./scenarios";
import { useTrialBalancePane } from "./TrialBalance";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
  vi.unstubAllGlobals();
});

const P = "/v1/engagements/{engagement_id}/trial-balances";

/** The scenario with some handlers wrapped, each request recorded. */
function spying(
  base: Scenario,
  extra: Record<string, FixtureHandler> = {},
): { scenario: Scenario; seen: FixtureRequest[] } {
  const seen: FixtureRequest[] = [];
  const handlers: Record<string, FixtureHandler> = {};
  for (const [route, handler] of Object.entries({ ...base.handlers, ...extra })) {
    handlers[route] = (r) => {
      seen.push(r);
      return handler(r);
    };
  }
  return { scenario: { ...base, handlers }, seen };
}

function frame(scenario: Scenario, state: keyof typeof scenarios): void {
  restore = installFixtureMode(scenario);
  render(
    <QueryClientProvider client={newQueryClient()}>
      <AUD06Frame state={state} />
    </QueryClientProvider>,
  );
}

const sent = (seen: FixtureRequest[], method: string, suffix: string): FixtureRequest[] =>
  seen.filter((r) => r.method === method && r.path.endsWith(suffix));

describe("AUD-06 empty: adopt a trial balance of record (A-02-T24, AC-1)", () => {
  it("offers Granite Peak's pulled snapshot and adopts it as Standard", async () => {
    const { scenario, seen } = spying(scenarios.empty);
    frame(scenario, "empty");
    expect(await screen.findByText("No trial balance yet")).toBeTruthy();
    const adopt = await screen.findByRole("button", { name: "Adopt as trial balance of record" });
    expect(document.querySelector("[data-aud06='adopt']")?.textContent).toContain(
      "a NetSuite export",
    );
    fireEvent.click(adopt);
    await waitFor(() => {
      expect(sent(seen, "POST", "/trial-balances")).toHaveLength(1);
    });
    const body = sent(seen, "POST", "/trial-balances")[0]?.body as Record<string, unknown>;
    expect(Object.keys(body).sort()).toEqual(["label", "snapshot_id"]);
    expect(body.label).toBe("standard");
    expect(String(body.snapshot_id)).toMatch(/^[0-9a-f-]{36}$/u);
  });
});

describe("AUD-06 newer: the newer-TB banner (A-02-T24, AC-7.1, AC-7.2)", () => {
  it("names the pull and its code-computed change count, and adopts v2 with a reason", async () => {
    const { scenario, seen } = spying(scenarios.newer);
    frame(scenario, "newer");
    const banner = await waitFor(
      () => {
        const found = document.querySelector<HTMLElement>("[data-aud06='newer']");
        expect(found).not.toBeNull();
        return found as HTMLElement;
      },
      { timeout: 4000 },
    );
    expect(banner.textContent).toMatch(
      /^A newer trial balance is available · pulled \d{1,2}:\d{2} [AP]M · 2 lines changed/u,
    );
    fireEvent.click(screen.getByRole("button", { name: "Use v2…" }));
    const adopt = screen.getByRole("button", { name: "Adopt" });
    expect((adopt as HTMLButtonElement).disabled).toBe(true); // a reason is required
    fireEvent.change(screen.getByLabelText("Reason"), {
      target: { value: "Client re-closed June" },
    });
    fireEvent.click(adopt);
    await waitFor(() => {
      expect(sent(seen, "POST", "/versions")).toHaveLength(1);
    });
    const body = sent(seen, "POST", "/versions")[0]?.body as Record<string, unknown>;
    expect(body.reason).toBe("Client re-closed June");
    expect(body.seen_version).toBe(1);
    expect(typeof body.snapshot_id).toBe("string");
  });

  it("draws no banner where the shown version is the newest (h)", async () => {
    frame(scenarios.h, "h");
    await waitFor(
      () => {
        expect(document.querySelector("[data-aud06='lines']")).not.toBeNull();
      },
      { timeout: 4000 },
    );
    expect(document.querySelector("[data-aud06='newer']")).toBeNull();
  });
});

describe("AUD-06 Open in Excel (A-02-T24, AC-8.1)", () => {
  it("downloads the server's file for the shown layer and version", async () => {
    const created = vi.fn(() => "blob:tb");
    vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: created, revokeObjectURL: vi.fn() }));
    const { scenario, seen } = spying(scenarios.h);
    frame(scenario, "h");
    const button = await screen.findByRole("button", { name: "Open in Excel" }, { timeout: 4000 });
    fireEvent.click(button);
    await waitFor(() => {
      expect(sent(seen, "GET", "/export.xlsx")).toHaveLength(1);
    });
    const asked = sent(seen, "GET", "/export.xlsx")[0];
    expect(asked?.query.get("layer")).toBe("final");
    expect(asked?.query.get("version")).toBe("1");
    await waitFor(() => {
      expect(created).toHaveBeenCalledTimes(1);
    });
  });
});

const CONNECTION = {
  id: "2b1f3c8e-6c55-4c37-9a51-6d1b0f0a7c11",
  provider: "quickbooks_online",
  status: "needs_attention",
  scopes: ["read_ledger"],
  created_by: "tess-moreno",
  created_at: "2026-03-04T10:00:00-06:00",
  expires_at: null,
  last_checked_at: null,
  last_check_ok: false,
  last_pull_at: null,
};

function withActions(base: Scenario, actions: TbLayerViewOut["allowed_actions"]): Scenario {
  const layers = `GET ${P}/{tb_id}/layers/{layer}`;
  const original = base.handlers[layers];
  return {
    ...base,
    handlers: {
      ...base.handlers,
      [layers]: async (r) => {
        const answered = await (original as FixtureHandler)(r);
        const view = (await answered.json()) as TbLayerViewOut;
        return json({ ...view, allowed_actions: [...(view.allowed_actions ?? []), ...(actions ?? [])] });
      },
    },
  };
}

describe("AUD-06 source menu (A-02-T24, AC-11.1)", () => {
  it("asks the client to reconnect a connection that needs it, once", async () => {
    const { scenario, seen } = spying(
      withActions(scenarios.newer, ["connection.reconnect_request"]),
      {
        "GET /v1/engagements/{engagement_id}/connection": () => json(CONNECTION),
        "POST /v1/connections/{connection_id}/reconnect-requests": () =>
          json(
            {
              id: "7a3a2f0e-0d4b-4b0e-8f6e-2a9c7c1d5e21",
              connection_id: CONNECTION.id,
              requested_by: {
                user_id: "0b6f0c55-1a1d-4c9e-9a8b-3f2f4c1d2e3f",
                display_name: "Simone Baptiste",
                kind: "firm",
              },
              requested_at: "2026-09-14T09:30:00-05:00",
            },
            201,
          ),
      },
    );
    frame(scenario, "newer");
    const ask = await screen.findByRole(
      "button",
      { name: "Ask client to reconnect" },
      { timeout: 4000 },
    );
    expect(screen.queryByRole("button", { name: "Pull latest" })).toBeNull();
    fireEvent.click(ask);
    await waitFor(() => {
      expect(sent(seen, "POST", "/reconnect-requests")).toHaveLength(1);
    });
    expect(await screen.findByText("Reconnect requested")).toBeTruthy();
    expect((ask as HTMLButtonElement).disabled).toBe(true);
  });

  it("offers nothing for an imported trial balance", async () => {
    const { scenario } = spying(
      withActions(scenarios.newer, ["connection.reconnect_request", "ledger.pull"]),
      {
        "GET /v1/engagements/{engagement_id}/connection": () =>
          json({ ...CONNECTION, provider: "import", status: "active" }),
      },
    );
    frame(scenario, "newer");
    await waitFor(
      () => {
        expect(document.querySelector("[data-aud06='lines']")).not.toBeNull();
      },
      { timeout: 4000 },
    );
    expect(document.querySelector("[data-aud06='source']")).toBeNull();
  });
});

function SignOffHarness({ onSignOff }: { onSignOff: (tb: string) => void }): JSX.Element {
  const { canvas } = useTrialBalancePane(OPENS.newer.engagementId, { onSignOff });
  return <div>{canvas.actions}</div>;
}

describe("AUD-06 Sign off… (A-02-T24)", () => {
  it("opens the trial balance's sign-off target for a reviewer", async () => {
    restore = installFixtureMode(withActions(scenarios.newer, ["sign_off.review"]));
    const onSignOff = vi.fn();
    render(
      <QueryClientProvider client={newQueryClient()}>
        <SignOffHarness onSignOff={onSignOff} />
      </QueryClientProvider>,
    );
    const button = await screen.findByRole("button", { name: "Sign off…" }, { timeout: 4000 });
    expect((button as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(button);
    expect(onSignOff).toHaveBeenCalledWith(OPENS.newer.tbId);
  });
});
