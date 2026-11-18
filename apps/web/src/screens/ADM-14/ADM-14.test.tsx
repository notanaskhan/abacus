// G-04-T18 (TASK-8639, DEC-5639): ADM-14 in fixture mode. Row acceptance: a to f render from
// scenarios, Save stays disabled until a change, and Margaret's view is read-only with Request
// more enabled.
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import exported from "../../fixtures/seed/scenario.adm14.json";
import { newQueryClient } from "../../testing/support";
import { ADM14, type ADM14Props } from "./index";
import { type Adm14ScenarioState, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

function show(state: Adm14ScenarioState, props: ADM14Props = {}): void {
  restore = installFixtureMode(scenarios[state]);
  render(
    <QueryClientProvider client={newQueryClient()}>
      <ADM14 {...props} />
    </QueryClientProvider>,
  );
}

async function meter(): Promise<HTMLElement> {
  await waitFor(() => {
    expect(document.querySelector("[data-adm14='meter']")).not.toBeNull();
  });
  return document.querySelector<HTMLElement>("[data-adm14='meter']") as HTMLElement;
}

describe("ADM-14 Plan & usage", () => {
  it("the export foots: 8,640 + 4,610 + 1,420 + 120 + 130 = 14,920; rates 7 + 7 + 11 + 19 + 2 = 46", () => {
    const lines = exported.usage.a.by_service_line.reduce((n, l) => n + l.minutes, 0);
    expect(lines).toBe(exported.usage.a.used_minutes);
    expect(exported.rates_people).toBe(46);
    expect(exported.seats).toBe(46);
  });

  it("a: 14,920 of 20,000 at 74.6%, the next alert at 75%, 46 of 46 Full", async () => {
    show("a");
    const m = await meter();
    expect(m.textContent).toContain("14,920");
    expect(m.textContent).toContain(" of 20,000 included");
    expect(m.textContent).toContain("74.6%");
    expect(m.textContent).toContain("Next alert at 75% (15,000) · 80 agent-minutes away");
    expect(screen.getByText("46 of 46 used")).toBeTruthy();
    expect(screen.getAllByText("Tax").length).toBeGreaterThan(0);
  });

  function banner(): string {
    return document.querySelector("[data-adm14='banner']")?.textContent ?? "";
  }

  it("a: no banner before the first alert", async () => {
    show("a");
    await meter();
    expect(document.querySelector("[data-adm14='banner']")).toBeNull();
  });

  it("b: 18,240 at 91.2%, the 90% alert's banner names when and to whom, the helper the 75% one", async () => {
    show("b");
    const m = await meter();
    expect(m.textContent).toContain("91.2%");
    expect(banner()).toBe(
      "90% of included agent-minutes used · alert sent Oct 9, 1:47 PM to Grace Holloway, Margaret Okonkwo and Felix Andersen",
    );
    expect(m.querySelector("[data-adm14='helper']")?.textContent).toBe(
      "1,760 left until Oct 15 · 75% alert sent Oct 1, 11:06 AM",
    );
  });

  it("c: 20,860 at 104.3%, the red banner 860 over with no amount, reset tomorrow", async () => {
    show("c");
    const c = await meter();
    expect(c.textContent).toContain("104.3%");
    expect(banner()).toBe(
      "860 agent-minutes over included · agents keep running (setting: Keep agents running) · overage is billed on the next invoice at the order-form rate",
    );
    expect(banner()).not.toMatch(/\$/);
    expect(c.querySelector("[data-adm14='helper']")?.textContent).toBe(
      "Included minutes reset tomorrow, Oct 15",
    );
  });

  it("Save stays disabled until an alert setting changes (a, then d dirty)", async () => {
    show("a");
    await meter();
    expect(screen.getByRole("button", { name: "Save" })).toHaveProperty("disabled", true);
    cleanup();
    restore?.();
    show("d", { initial: { at100: "pause_scheduled" } });
    await meter();
    expect(screen.getByRole("button", { name: "Save" })).toHaveProperty("disabled", false);
  });

  it("e: Margaret reads only, with Request more… enabled", async () => {
    show("e", { readOnly: true });
    await meter();
    expect(
      screen.getByText("Only firm admins can change alerts and billing contact."),
    ).toBeTruthy();
    expect(screen.getByRole("button", { name: "Request more…" })).toHaveProperty(
      "disabled",
      false,
    );
  });

  it("f: Request more opens with the partner approver", async () => {
    show("f", { initial: { requestOpen: true } });
    await meter();
    expect(await screen.findByText("Partner approval: Margaret Okonkwo")).toBeTruthy();
  });
});
