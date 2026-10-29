// ADM-04 · AI policy & approval gates (G-02-T25). One test per artboard on its fixture scenario
// (a–j, band, awaiting, real_firm; SPEC-349), plus: no control offers a loosening (the tolerance
// lists only stricter values, Auto mode turns on nowhere it is off, the §7216 floor is locked),
// the principal's c and f write nothing, and the approver is never the requester. axe runs in the
// Playwright journey (A-02-T31 / G-02's parity task), not here.
import { client } from "@abacus/api-client/client";
import { toastStore } from "@abacus/ui";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import {
  type FixtureHandler,
  type Scenario,
  installFixtureMode,
} from "../../app-core/fixture-mode";
import { newQueryClient } from "../../testing/support";
import { ADM04 } from ".";
import { type Adm04State, OPENS, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
  toastStore.clear();
});

interface Call {
  method: string;
  path: string;
  body: unknown;
}

function show(state: Adm04State): Call[] {
  const scenario: Scenario = scenarios[state];
  const calls: Call[] = [];
  const handlers = Object.fromEntries(
    Object.entries(scenario.handlers).map(([key, handler]) => [
      key,
      ((request) => {
        calls.push({ method: request.method, path: request.path, body: request.body });
        return handler(request);
      }) satisfies FixtureHandler,
    ]),
  );
  restore = installFixtureMode({ ...scenario, handlers });
  render(
    <QueryClientProvider client={newQueryClient()}>
      <ADM04 opens={OPENS[state] ?? {}} />
    </QueryClientProvider>,
  );
  return calls;
}

const writes = (calls: Call[]): Call[] => calls.filter((c) => c.method !== "GET");

describe("ADM-04 AI policy & approval gates", () => {
  it("a: the v3 chip, twelve gates, the principal Off + Lock and Save as v4… disabled", async () => {
    show("a");
    expect(await screen.findByText(/^BH AI policy v3 · published /)).toBeTruthy();
    const table = screen.getByRole("table", { name: "Approval gates" });
    expect(within(table).getAllByRole("row")).toHaveLength(13);
    expect(within(table).getByText("5. Proposed AJE within threshold")).toBeTruthy();
    expect(screen.getByText("Off")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Save as v4…" }).hasAttribute("disabled")).toBe(
      true,
    );
  });

  it("b: the draft's 8% → 6% shows Save as v4…", async () => {
    show("b");
    expect(await screen.findByRole("button", { name: "Save as v4…" })).toBeTruthy();
  });

  it("c: Allow policy acceptance? opens, and Allow writes nothing", async () => {
    const calls = show("c");
    const dialog = await screen.findByRole("alertdialog", { name: "Allow policy acceptance?" });
    fireEvent.click(
      within(dialog).getByRole("checkbox", { name: "I understand attest clients are excluded" }),
    );
    fireEvent.click(within(dialog).getByRole("button", { name: "Allow" }));
    expect(await screen.findByText("On · non-attest only")).toBeTruthy();
    expect(writes(calls).filter((c) => c.path.includes("principal"))).toHaveLength(0);
  });

  it("d: the sheet lists the change, Effective and Daniel Reyes as approver", async () => {
    show("d");
    const sheet = await screen.findByRole("dialog", { name: "Save as v4" });
    expect(within(sheet).getByText("Override tolerance 8% → 6%")).toBeTruthy();
    expect(within(sheet).getByText("Effective")).toBeTruthy();
    expect(within(sheet).getByText("Daniel Reyes")).toBeTruthy();
    expect(within(sheet).queryByText("Margaret Okonkwo")).toBeNull();
  });

  it("e: Hannah reads it only: the note, and no Save", async () => {
    show("e");
    expect(await screen.findByText("Only partners can change the AI policy.")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /^Save as v/ })).toBeNull();
  });

  it("f: the principal reads On · non-attest only with the toast, and nothing is written", async () => {
    const calls = show("f");
    expect(await screen.findByText("On · non-attest only")).toBeTruthy();
    await waitFor(() => {
      expect(toastStore.list().some((t) => t.text === "Policy acceptance on · logged")).toBe(true);
    });
    expect(writes(calls)).toHaveLength(0);
  });

  it("g: v4 is the effective chip", async () => {
    show("g");
    expect(await screen.findByText(/^BH AI policy v4 · published /)).toBeTruthy();
  });

  it("h: Auto mode defaults render, none can turn on where it is off", async () => {
    show("h");
    await screen.findByText("Auto mode defaults");
    for (const name of ["EBP audits", "Tax returns", "Notices"]) {
      const toggle = screen.getByRole("switch", { name });
      if (toggle.getAttribute("aria-checked") !== "true") {
        expect(
          toggle.hasAttribute("disabled") || toggle.getAttribute("aria-disabled") === "true",
        ).toBe(true);
      }
    }
  });

  it("i: the row-5 popover says where the gate appears and how it is logged", async () => {
    show("i");
    expect(await screen.findByText("Where this gate appears")).toBeTruthy();
    expect(screen.getByText(/^Logged as /)).toBeTruthy();
  });

  it("j: the version history lists v1 to v3", async () => {
    show("j");
    const drawer = await screen.findByRole("dialog", { name: "Version history" });
    for (const v of ["v1", "v2", "v3"]) {
      expect(await within(drawer).findByText(v)).toBeTruthy();
    }
  });

  it("band: Grace sees the client-data opt-in, the stages and Pause all agents", async () => {
    show("band");
    expect(await screen.findByText("Immediate controls")).toBeTruthy();
    expect(screen.getByText(/^On since Jun 1 · /)).toBeTruthy();
    expect(screen.getByText("Evidence screening")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Pause all agents" }));
    expect(await screen.findByRole("alertdialog", { name: "Pause all agents?" })).toBeTruthy();
  });

  it("awaiting: the chip names Daniel Reyes and Daniel can approve", async () => {
    show("awaiting");
    expect(await screen.findByText("Awaiting approval · Daniel Reyes")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Approve v4" })).toBeTruthy();
  });

  it("real_firm: every Auto mode row is off and cannot be turned on", async () => {
    show("real_firm");
    await screen.findByText("Auto mode defaults");
    expect(screen.getAllByText("Auto mode isn't available for client data yet")).toHaveLength(8);
    for (const name of ["EBP audits", "Financial statement audits", "Advisory projects"]) {
      const toggle = screen.getByRole("switch", { name });
      expect(toggle.getAttribute("aria-checked")).not.toBe("true");
    }
  });

  it("no loosening: the tolerance offers nothing above the effective 8%", async () => {
    show("a");
    await screen.findByText("Override tolerance");
    expect(screen.queryByText("9%")).toBeNull();
    expect(screen.queryByText("10%")).toBeNull();
  });
});
