// A-07-T25 (TASK-6215): AUD-19 in fixture mode. Row: "All seven AUD-19 artboards render from
// fixtures and the summary reads 12 of 17 with N/A excluded."
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, waitFor } from "@testing-library/react";
import type { JSX } from "react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { COMPLETION_WORK_ITEM, aud19Runs } from "../../fixtures/seed/audit-completion";
import { newQueryClient } from "../../testing/support";
import { type CompletionTab, useCompletionCanvas } from "./Completion";
import { type State, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

function Canvas({ tab, calls }: { tab: CompletionTab; calls: string[] }): JSX.Element {
  const canvas = useCompletionCanvas(COMPLETION_WORK_ITEM, {
    tab,
    onSignOff: () => calls.push("SHL-12"),
    onLink: (target) => calls.push(target),
    onRequestLegalLetter: () => calls.push("SHL-14"),
  });
  return (
    <div>
      <div data-test="state">{canvas.state?.kind}</div>
      <div data-test="actions">{canvas.actions}</div>
      {canvas.children}
    </div>
  );
}

function show(state: State, tab: CompletionTab = "checklist", calls: string[] = []): void {
  restore = installFixtureMode(scenarios[state]);
  render(
    <QueryClientProvider client={newQueryClient()}>
      <Canvas tab={tab} calls={calls} />
    </QueryClientProvider>,
  );
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

describe("AUD-19", () => {
  it("a: the summary reads 12 of 17 with N/A excluded, and 18 rows tie", async () => {
    show("a");
    expect((await drawn("[data-aud19='of']")).textContent).toBe("12 of 17");
    const summary = await drawn("[data-aud19='summary']");
    expect(summary.textContent).toContain("12 complete");
    expect(summary.textContent).toContain("1 not applicable");
    expect(summary.textContent).toContain("5 open");
    expect(document.querySelectorAll("[data-item]")).toHaveLength(18);
    expect(document.querySelectorAll("[data-status='not_applicable']")).toHaveLength(1);
  });

  it("a: five blockers, each linked or dated; only the rep letter carries G7", async () => {
    const calls: string[] = [];
    show("a", "checklist", calls);
    await drawn("[data-aud19='blockers']");
    const rows = Array.from(document.querySelectorAll<HTMLElement>("[data-blocker]"));
    expect(rows.map((r) => r.dataset.blocker)).toEqual([
      "independence", "subsequent_events", "mgmt_approval", "rep_letter", "tcwg_260",
    ]); // prettier-ignore
    const tagged = rows.filter((r) => r.textContent.includes("G7"));
    expect(tagged.map((r) => r.dataset.blocker)).toEqual(["rep_letter"]);
    expect(rows[0]?.textContent).toContain("Oct 9");
    rows[3]?.querySelector<HTMLElement>("[data-link='AUD-21']")?.click();
    expect(calls).toEqual(["AUD-21"]);
  });

  it("a2: Sign off… opens SHL-12, which lists what blocks it", async () => {
    const calls: string[] = [];
    show("a2", "checklist", calls);
    await drawn("[data-aud19='blockers']");
    const button = Array.from(document.querySelectorAll("button")).find((b) =>
      b.textContent.includes("Sign off"),
    );
    button?.click();
    expect(calls).toEqual(["SHL-12"]);
  });

  it("b: procedures through Oct 6, two nonrecognized events citing notes", async () => {
    show("b", "subsequent_events");
    await drawn("[data-aud19='events']");
    const events = Array.from(document.querySelectorAll<HTMLElement>("[data-event]"));
    expect(events.map((e) => e.dataset.recognition)).toEqual(["nonrecognized", "nonrecognized"]);
    expect(events[0]?.textContent).toContain("Note 11");
    expect(events[1]?.textContent).toContain("Note 9");
    expect((await drawn("[data-procedure='bring_down']")).dataset.status).toBe("open");
  });

  it("c: legal letters not applicable with a basis, and the request", async () => {
    const calls: string[] = [];
    show("c", "legal_letters", calls);
    const card = await drawn("[data-aud19='legal']");
    expect(card.textContent).toContain("Not applicable");
    expect(card.textContent).toContain("inquiry of Dana Kowalski");
    Array.from(card.querySelectorAll("button"))
      .find((b) => b.textContent.includes("Request a legal letter"))
      ?.click();
    expect(calls).toEqual(["SHL-14"]);
  });

  it("d: the going-concern card is decided, read-only and reserved", async () => {
    show("d", "going_concern");
    const card = await drawn("[data-aud19='going-concern']");
    expect(card.getAttribute("aria-readonly")).toBe("true");
    expect(card.querySelector("button")).toBeNull();
    expect(card.querySelector("[data-selected]")?.getAttribute("data-option")).toBe(
      "no_substantial_doubt",
    );
    expect((await drawn("[data-aud19='decided']")).textContent).toContain(
      "Decided by Margaret Okonkwo · Sep 30",
    );
    expect(card.textContent).toContain("Reserved to Engagement Partner");
  });

  it("e: Granite Peak's DSCR and revolver", async () => {
    show("e", "going_concern");
    const card = await drawn("[data-aud19='going-concern']");
    expect(card.textContent).toContain("1.32×");
    expect(card.textContent).toContain("Front Range Bank matures Mar 2028");
  });

  it("f: all clear reads 17 of 17 and opens Issuance & release", async () => {
    const calls: string[] = [];
    show("f", "checklist", calls);
    expect((await drawn("[data-aud19='of']")).textContent).toBe("17 of 17");
    const clear = await drawn("[data-aud19='clear']");
    expect(clear.textContent).toBe("Nothing blocks the report — open Issuance & release");
    clear.click();
    expect(calls).toEqual(["AUD-24"]);
    expect(document.querySelector("[data-aud19='blockers']")).toBeNull();
  });

  it("the dock's runs are #4231 and the queued #4240", () => {
    const [checked, bringDown] = aud19Runs();
    expect(checked?.agent_label).toContain("#4231");
    expect(bringDown?.state).toBe("queued");
    expect(bringDown?.started_at).toBe("2026-10-09T09:00:00-05:00");
  });
});
