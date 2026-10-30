// A-02-T35 (TASK-2141): AUD-06's line agreement and edit with a reason on P-04 fields, in fixture
// mode. Acceptance: "Marcus Delaney agrees KRS Target 2045 to Harborline p.1 and the chip popover
// names him and the page, while amount cells offer no edit." The popover's words come from the
// server's tick and citation (AC-2.2); here the screen sends the reference, then the L1 tick, on
// the line's `wp_ref` field, and the amount cells hold no control.
import type { TbLayerViewOut } from "@abacus/api-client";
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import {
  type FixtureHandler,
  type FixtureRequest,
  type Scenario,
  installFixtureMode,
  json,
} from "../../app-core/fixture-mode";
import { HARBORLINE } from "../../fixtures/seed/trust";
import { newQueryClient } from "../../testing/support";
import { AUD06Frame } from "./artboard";
import { scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

const LAYER = "GET /v1/engagements/{engagement_id}/trial-balances/{tb_id}/layers/{layer}";

/** State a with the person allowed to annotate, every request recorded. */
function annotating(): { scenario: Scenario; seen: FixtureRequest[] } {
  const base = scenarios.a;
  const seen: FixtureRequest[] = [];
  const handlers: Record<string, FixtureHandler> = {};
  for (const [route, handler] of Object.entries(base.handlers)) {
    handlers[route] = async (r) => {
      seen.push(r);
      const answer = await handler(r);
      if (route !== LAYER || answer.status !== 200) return answer;
      const view = (await answer.json()) as TbLayerViewOut;
      return json({
        ...view,
        allowed_actions: [...(view.allowed_actions ?? []), "trial_balance.annotate"],
      });
    };
  }
  return { scenario: { ...base, handlers }, seen };
}

const sent = (seen: FixtureRequest[], method: string, suffix: string): FixtureRequest[] =>
  seen.filter((r) => r.method === method && r.path.endsWith(suffix));

describe("AUD-06 line agreement (A-02-T35, AC-6.1, AC-6.4)", () => {
  it("agrees KRS Target 2045 to the Harborline page: the reference, then the L1 tick", async () => {
    const { scenario, seen } = annotating();
    restore = installFixtureMode(scenario);
    render(
      <QueryClientProvider client={newQueryClient()}>
        <AUD06Frame state="a" />
      </QueryClientProvider>,
    );
    const menu = await screen.findByRole(
      "button",
      { name: "Line actions for KRS Target 2045 Fund" },
      { timeout: 4000 },
    );
    fireEvent.pointerDown(menu, { button: 0 }); // the menu opens on pointer down (Radix)
    fireEvent.click(await screen.findByRole("menuitem", { name: "Agree to source…" }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText("Find in the source"), {
      target: { value: "2,915,330.00" }, // the line's amount as Harborline prints it
    });
    fireEvent.click(await within(dialog).findByRole("button", { name: "Page 2" }));
    fireEvent.click(within(dialog).getByRole("button", { name: "Agree" }));
    await waitFor(() => {
      expect(sent(seen, "POST", "/ticks")).toHaveLength(1);
    });
    const reference = sent(seen, "POST", "/references")[0];
    expect(reference?.params.field_key).toMatch(/^wp_ref:/u);
    expect(reference?.body).toEqual({ document_id: HARBORLINE, page: 2, seen_seq: 1 });
    expect(sent(seen, "POST", "/ticks")[0]?.body).toEqual({
      level: "L1_preparer",
      seen_hash: "0".repeat(64),
    });
    expect(seen.indexOf(reference as FixtureRequest)).toBeLessThan(
      seen.indexOf(sent(seen, "POST", "/ticks")[0] as FixtureRequest),
    );
  });

  it("edits the WP ref only with a reason, and the amount cells hold no control", async () => {
    const { scenario, seen } = annotating();
    restore = installFixtureMode(scenario);
    render(
      <QueryClientProvider client={newQueryClient()}>
        <AUD06Frame state="a" />
      </QueryClientProvider>,
    );
    const menu = await screen.findByRole(
      "button",
      { name: "Line actions for KRS Target 2045 Fund" },
      { timeout: 4000 },
    );
    const row = menu.closest("tr") as HTMLElement;
    expect(row.querySelectorAll("td[data-col] input, td[data-col] button")).toHaveLength(0);
    fireEvent.pointerDown(menu, { button: 0 }); // the menu opens on pointer down (Radix)
    fireEvent.click(await screen.findByRole("menuitem", { name: "Edit…" }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText("WP ref"), { target: { value: "C-2.1" } });
    const save = within(dialog).getByRole("button", { name: "Save" });
    expect((save as HTMLButtonElement).disabled).toBe(true); // a reason is required
    fireEvent.change(within(dialog).getByLabelText("Reason"), {
      target: { value: "Leadsheet renumbered" },
    });
    await waitFor(() => {
      expect((save as HTMLButtonElement).disabled).toBe(false);
    });
    fireEvent.click(save);
    await waitFor(() => {
      expect(sent(seen, "PUT", "/value")).toHaveLength(1);
    });
    expect(sent(seen, "PUT", "/value")[0]?.body).toEqual({
      value: { t: "text", v: "C-2.1" },
      citation_note: "Leadsheet renumbered",
      seen_seq: 1,
    });
  });
});
