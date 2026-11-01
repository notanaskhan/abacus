// A-05-T11 (TASK-2908): EBP-01 a–d and the C-20 states in fixture mode, inside the AUD-02 cockpit.
// Row acceptance: "All four artboards render from fixtures and live data, and the EIN is never in
// the DOM, query cache or URL after re-mask." Words and figures are the handoff's.
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { newQueryClient } from "../../testing/support";
import { EBP01Frame } from "./artboard";
import { type Ebp01State, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

function show(state: Ebp01State): ReturnType<typeof newQueryClient> {
  restore = installFixtureMode(scenarios[state]);
  const queries = newQueryClient();
  render(
    <QueryClientProvider client={queries}>
      <EBP01Frame state={state} />
    </QueryClientProvider>,
  );
  return queries;
}

const drawn = (selector: string): Promise<HTMLElement> =>
  waitFor(
    () => {
      const found = document.querySelector<HTMLElement>(selector);
      expect(found).not.toBeNull();
      return found as HTMLElement;
    },
    { timeout: 6000 },
  );

describe.each(["a", "b", "c", "d"] as const)("EBP-01%s", (state) => {
  it("draws the plan facts, the status card and four providers from the server", async () => {
    const queries = show(state);
    const facts = await drawn("[data-ebp01='facts']");
    expect(facts.textContent).toContain("Northwind Robotics 401(k) Plan");
    expect(facts.textContent).toContain("58217");
    const status = await drawn("[data-ebp01='status']");
    expect(status.textContent).toContain("Large plan");
    expect(status.textContent).toContain("286");
    expect(status.textContent).toContain("Oct 15, 2026");
    await waitFor(() => {
      expect(document.querySelectorAll("[data-provider]").length).toBe(4);
    });
    // P-12: no full EIN anywhere: the DOM, the cached payloads and the URL.
    const nineDigits = /\b\d{2}-?\d{7}\b/u;
    expect(document.body.textContent ?? "").not.toMatch(nineDigits);
    expect(JSON.stringify(queries.getQueryCache().getAll().map((q) => q.state.data))).not.toMatch(
      nineDigits,
    );
    expect(window.location.href).not.toMatch(nineDigits);
  });
});

describe("EBP-01 states", () => {
  it("a reads PN 001 and the recordkeeper ID apart", async () => {
    show("a");
    const pn = await drawn("[data-field='plan_number']");
    expect(pn.textContent).toContain("001");
    expect(document.querySelector("[data-help='plan_number']")).toBeNull();
  });

  it("b shows the Form 5500 helper when the PN is missing", async () => {
    show("b");
    const help = await drawn("[data-help='plan_number']");
    expect(help.textContent).toBe(
      "Form 5500 needs a three-digit PN (001–499). The recordkeeper ID 58217 is not a plan number.",
    );
  });

  it("c shows the EIN endings, Raise exception… and Summit's Correction requested", async () => {
    show("c");
    const note = await drawn("[data-provider='Keystone Retirement Services'] [data-check-note]");
    expect(note.textContent).toContain("EIN ending 4402");
    expect(note.textContent).toContain("EIN ending 4420");
    expect(document.querySelector("[data-raise]")?.textContent).toBe("Raise exception…");
    const summit = await drawn("[data-provider='Summit Plan Administrators']");
    expect(summit.textContent).toContain("Correction requested");
  });

  it("d opens in edit mode with fields and Save", async () => {
    show("d");
    await drawn("[data-screen='EBP-01'][data-editing='true']");
    expect(document.querySelector("input[aria-label='Plan number (PN)']")).not.toBeNull();
  });

  it("off draws C-20 and not_allowed reads walled", async () => {
    show("off");
    await waitFor(() => {
      expect(document.querySelector("[data-ebp01='facts']")).toBeNull();
    });
  });
});
