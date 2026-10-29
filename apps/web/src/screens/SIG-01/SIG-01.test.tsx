// SIG-01 · Signatures hub (N-02-T11; DEC-827). Acceptance (the task row): "Scenario tests for a, b,
// c, d, e and g pass at 1400 with the DF-11 copy in the E2 drawer and no Send new link at unlock."
import { client } from "@abacus/api-client/client";
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { renderRoutes } from "../../testing/support";
import { SIG01 } from ".";
import { COPY } from "./copy";
import { OPENS, type Sig01State, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

function mount(state: Sig01State): void {
  restore = installFixtureMode(scenarios[state]);
  const open = OPENS[state];
  renderRoutes([
    {
      path: "/",
      component: () => <SIG01 initialTab={open.tab} initialEnvelope={open.envelope} />,
    },
  ]);
}

describe("SIG-01", () => {
  it("a: out for signature with the E2 drawer and the DF-11 copy, no Send new link", async () => {
    mount("a");
    expect(await screen.findAllByText(/Thomas & Irene Kowal/)).not.toHaveLength(0);
    const drawer = await screen.findByRole("dialog");
    expect(within(drawer).getByText(COPY.df11.needsHandwritten)).toBeTruthy();
    expect(within(drawer).getByRole("button", { name: COPY.df11.upload })).toBeTruthy();
    expect(within(drawer).queryByText(/Send new link at unlock/)).toBeNull();
  });

  it("a: the tiles foot 8, 5, 4 and 4", async () => {
    mount("a");
    await screen.findAllByText(/Thomas & Irene Kowal/);
    for (const label of [COPY.tiles.sent, COPY.tiles.viewed, COPY.tiles.partiallySigned]) {
      expect(screen.getAllByText(label).length).toBeGreaterThan(0);
    }
    expect(screen.getByText(COPY.summary)).toBeTruthy();
  });

  it("b: two drafts to send, the agent's drafted via Agent", async () => {
    mount("b");
    expect(await screen.findByText(/Harborview Dental Properties, LP/)).toBeTruthy();
    expect(screen.getByText(/Form 2848 · Aurelio Santos/)).toBeTruthy();
  });

  it("c: completed, last 30 days", async () => {
    mount("c");
    expect(await screen.findByText(/Summit Line Logistics, Inc\./)).toBeTruthy();
  });

  it("d: the expired consent", async () => {
    mount("d");
    expect(await screen.findByText(/disclosure to offshore preparers/)).toBeTruthy();
  });

  it("e: the declined variant", async () => {
    mount("e");
    expect(await screen.findByText(/Noor & Adam Farouk/)).toBeTruthy();
    expect(screen.getAllByText("Declined").length).toBeGreaterThan(0);
  });

  it("g: empty To send", async () => {
    mount("g");
    expect(await screen.findByText(COPY.empty.title)).toBeTruthy();
  });
});

// N-02-T15 (TASK-2016; DEC-1057). Acceptance (the task row, fixture half): "the f scenario sends
// nothing until a human clicks Send."
describe("SIG-01 · N-02-T15", () => {
  function mountWith(state: Sig01State): void {
    restore = installFixtureMode(scenarios[state]);
    const open = OPENS[state];
    renderRoutes([
      {
        path: "/",
        component: () => (
          <SIG01
            initialTab={open.tab}
            initialEnvelope={open.envelope}
            initialChecked={open.checked ?? []}
            initialImport={open.importing ?? false}
          />
        ),
      },
    ]);
  }

  it("f: three checked, the bar reads 3 selected · Remind 3…, nothing sends until Send", async () => {
    const sent: unknown[] = [];
    const base = scenarios.f;
    const send = base.handlers["POST /v1/envelopes/remind/send"];
    if (send === undefined) throw new Error("the f scenario has no send");
    restore = installFixtureMode({
      ...base,
      handlers: {
        ...base.handlers,
        "POST /v1/envelopes/remind/send": (request) => {
          sent.push(request.body);
          return send(request);
        },
      },
    });
    const open = OPENS.f;
    renderRoutes([
      {
        path: "/",
        component: () => (
          <SIG01
            initialTab={open.tab}
            initialEnvelope={open.envelope}
            initialChecked={open.checked ?? []}
          />
        ),
      },
    ]);
    expect(await screen.findByText(COPY.selection.selected(3))).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: COPY.selection.remind(3) }));
    const dialog = await screen.findByRole("dialog");
    expect(await within(dialog).findByText(/Please sign/)).toBeTruthy();
    const button = await within(dialog).findByRole("button", { name: "Send 3 reminders" });
    await waitFor(() => {
      expect((button as HTMLButtonElement).disabled).toBe(false);
    });
    expect(sent).toHaveLength(0);
    fireEvent.click(button);
    await waitFor(() => {
      expect(sent).toHaveLength(1);
    });
  });

  it("r: Import signed package waits for the attestation", async () => {
    mountWith("r");
    const sheet = await screen.findByRole("dialog");
    expect(within(sheet).getAllByText(COPY.importSheet.title).length).toBeGreaterThan(0);
    expect(within(sheet).getByText(COPY.importSheet.attest)).toBeTruthy();
    const importButton = within(sheet).getByRole("button", { name: COPY.importSheet.import });
    expect((importButton as HTMLButtonElement).disabled).toBe(true);
  });
});
