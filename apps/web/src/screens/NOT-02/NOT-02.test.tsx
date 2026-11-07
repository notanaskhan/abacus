// N-04-T14 (TASK-3275): NOT-02 a, b, c, d and a2 in fixture mode. Row acceptance: "Scenario tests for
// a, b, c, d and a2 pass, a lit payer lights in all three panes, and Kevin Osei sees the decision
// radios disabled with the reason in text." Figures are the handoff's (N-04-T04 goldens).
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { NOT02_NOTICE } from "../../fixtures/seed/not02";
import { newQueryClient } from "../../testing/support";
import { type Not02State, scenarios } from "./scenarios";
import { type NoticeTab, NoticeWorkspace } from "./Workspace";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

function show(state: Not02State, tab: NoticeTab = "analysis", lit = false): void {
  restore = installFixtureMode(scenarios[state]);
  render(
    <QueryClientProvider client={newQueryClient()}>
      <NoticeWorkspace noticeId={NOT02_NOTICE} tab={tab} initialLit={lit} />
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

describe("NOT-02", () => {
  it("a: the server's figures foot: +3,120.00, +686.40, 66.61, 753.01", async () => {
    show("a");
    const table = await drawn("[data-not02='statement']");
    expect(table.querySelector("[data-row='taxable_interest']")?.textContent).toContain(
      "+3,120.00",
    );
    expect(table.querySelector("[data-row='tax']")?.textContent).toContain("+686.40");
    expect(table.querySelector("[data-row='interest']")?.textContent).toContain("66.61");
    expect(table.querySelector("[data-row='total_due']")?.textContent).toContain("753.01");
    const info = await drawn("[data-not02='info-returns']");
    expect(info.textContent).toContain("Front Range Bank");
    expect(info.textContent).toContain("Lakeview Credit Union");
    expect(info.textContent).toContain("4 others agree");
    const why = await drawn("[data-not02='why'][data-stage='live']");
    expect(why.textContent).toContain("3,120.00 at the 22% bracket = 686.40");
    expect(document.querySelector("[data-not02='subbar']")?.textContent).toContain(
      "CP2000 · TY2024 · Marcus & Dana Whitley",
    );
    expect(document.querySelector("[data-not02='source-row']")?.textContent).toContain(
      "1099 corrections2 documents · 4 citations",
    );
  });

  it("a: Kevin Osei sees the radios disabled with the reason in text", async () => {
    show("a");
    const card = await drawn("[data-not02='decision'][data-reserved='false']");
    const radios = [...card.querySelectorAll<HTMLInputElement>("input[type='radio']")];
    expect(radios.length).toBe(3);
    expect(radios.every((r) => r.disabled)).toBe(true);
    expect(card.textContent).toContain("Recommended by Accrued Agent");
    expect(card.querySelector("[data-not02='reserved']")?.textContent).toBe(
      "Reserved to Daniel Reyes (signing partner). Sent to their Approvals queue.",
    );
    const decide = [...card.querySelectorAll("button")].find((b) => b.textContent === "Decide");
    expect((decide as HTMLButtonElement).disabled).toBe(true);
  });

  it("b: analyzing shows the progress line, spinners and a skeleton action", async () => {
    show("b");
    const progress = await drawn("[data-not02='progress']");
    expect(progress.textContent).toBe("Comparing 6 information returns with the 2024 return…");
    expect(document.querySelector("[data-not02='analysis'] [data-live]")).not.toBeNull();
    expect(document.querySelector("[data-not02='proposed']")).toBeNull();
    expect(document.querySelector("[data-not02='why']")).toBeNull();
  });

  it("c: decided reads Agree · decided by Daniel Reyes", async () => {
    show("c");
    const decided = await drawn("[data-not02='decided']");
    expect(decided.textContent).toContain("Agree — pay $753.01 · decided by Daniel Reyes");
    expect(document.querySelectorAll("[data-not02='decision'] input[type='radio']").length).toBe(
      0,
    );
  });

  it("d: a lit payer lights in all three panes; the viewer stacks two sources", async () => {
    show("d", "analysis", true);
    await drawn("[data-not02='info-returns']");
    const payer = await drawn("[data-payer='Front Range Bank']");
    fireEvent.mouseEnter(payer);
    await waitFor(() => {
      expect(document.querySelector("[data-not02='analysis'] [data-lit='true']")).not.toBeNull();
      expect(document.querySelector("[data-not02='action'] [data-lit='true']")).not.toBeNull();
      expect(document.querySelector("[data-not02='stack']")?.textContent).toBe("1 / 2");
    });
  });

  it("a2: the Activity timeline", async () => {
    show("a2", "activity");
    const list = await drawn("[data-not02='activity']");
    await waitFor(() => {
      expect(list.querySelectorAll("[data-event]").length).toBe(5);
    });
    expect(list.textContent).toContain("Uploaded via portal");
    expect(list.textContent).toContain("Dana Whitley");
    expect(list.textContent).toContain("Decision requested");
  });

  it("draws with no notices flag: notices.workspace is retired (DEC-2602)", async () => {
    show("a");
    await waitFor(
      () => {
        expect(document.body.textContent).not.toContain("not turned on");
        expect(document.body.textContent).toContain("Whitley");
      },
      { timeout: 6000 },
    );
  });
});

describe("N-04-T22: NOT-02 e and f", () => {
  it("e: Collins reads Disagree with the zero-gain reason, Awaiting IRS", async () => {
    show("e");
    const why = await drawn("[data-not02='why']");
    expect(why.textContent).toContain("13,200.00");
    expect(why.textContent).toContain("so the gain is zero");
    expect(document.querySelector("[data-not02='subbar']")?.textContent).toContain("Awaiting IRS");
    expect(document.querySelector("[data-not02='proposed']")?.textContent).toContain("Disagree");
  });

  it("f: Santos reads None on file with Form 2848 to send", async () => {
    show("f");
    const card = await drawn("[data-not02='authorization']");
    expect(card.textContent).toContain("None on file");
    expect(card.querySelector("[data-not02='authorization-banner']")?.textContent).toBe(
      "Form 2848 to send",
    );
  });
});
