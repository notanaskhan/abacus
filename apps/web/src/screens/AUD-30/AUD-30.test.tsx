// Q-05-T24 (TASK-8934; DEC-5936): AUD-30 a–f render from their scenarios (the Python slice's
// cases, additions and analysis) at Mon Jan 25, 2027. Acceptance: "AUD-30a to f match at Tier C,
// no alarm styling appears for the below-CT difference, and Reopen for reissue lands on AUD-23 g
// with the dual date" (AUD-23 g's dual date: AUD-23/LiveReport.test.tsx). The decision is the
// engagement partner's; the agent shows its analysis and a recommendation tag only.
import { client } from "@abacus/api-client/client";
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { type Scenario, installFixtureMode, never } from "../../app-core/fixture-mode";
import { cases } from "../../fixtures/seed/aud30";
import { renderRoutes } from "../../testing/support";
import { COPY as C } from "./copy";
import { AUD30, type AUD30Props, caseText } from "./index";
import { AUD30_AUDIT_ID, type Aud30State, railLine, scenarios } from "./scenarios";

let restore: (() => void) | null = null;

beforeAll(() => {
  client.setConfig({ baseUrl: "http://localhost" });
});

afterEach(() => {
  cleanup();
  restore?.();
  restore = null;
});

function show(sc: Scenario, props: Partial<AUD30Props> = {}): void {
  restore = installFixtureMode(sc);
  renderRoutes([{ path: "/", component: () => <AUD30 auditId={AUD30_AUDIT_ID} {...props} /> }]);
}

function state(s: Aud30State, props: Partial<AUD30Props> = {}): void {
  show(scenarios[s], props);
}

async function caseList(): Promise<HTMLElement> {
  return waitFor(() => {
    const list = document.querySelector<HTMLElement>("[data-aud30='cases']");
    expect(list?.querySelectorAll("[data-case]").length).toBe(2);
    return list as HTMLElement;
  });
}

function caseButton(ref: string): HTMLElement {
  return document.querySelector<HTMLElement>(`[data-case='${ref}']`) as HTMLElement;
}

describe("AUD-30 Post-issuance", () => {
  it("AUD-30a default: PI-01 under evaluation with the code's comparison and evaluation", async () => {
    state("a");
    await caseList();
    expect(caseButton("PI-01").textContent).toContain("Under evaluation");
    expect(caseButton("PI-01").textContent).toContain(
      "Subsequently discovered facts · AU-C 560 · received Jan 19, 2027",
    );
    expect(caseButton("PI-02").textContent).toContain("Concluded Jan 15");
    expect(caseButton("PI-01").getAttribute("aria-current")).toBe("true");
    const table = (await waitFor(() => {
      const t = document.querySelector("[data-aud30='comparison']");
      expect(t).not.toBeNull();
      return t;
    })) as HTMLElement;
    const rows = [...table.querySelectorAll("tbody tr")].map((r) =>
      [...r.querySelectorAll("td")].map((td) => td.textContent),
    );
    expect(rows).toEqual([
      ["Harborline Stable Value Fund", "1,163,480", "1,151,230", "(12,250)"],
      ["Total investments at fair value", "16,500,000", "16,487,750", "(12,250)"],
      ["Net assets available for benefits", "16,861,000", "16,848,750", "(12,250)"],
    ]);
    expect(screen.getByText("12,610 — difference is below CT")).toBeTruthy();
    expect(screen.getByText("4.9% of 252,200")).toBeTruthy();
    const detail = document.querySelector("[data-aud30='detail']") as HTMLElement;
    expect(detail.textContent).toContain("Harborline Corrected Certification 2025.pdf");
    expect(detail.textContent).toContain("Hannah Leclerc");
    expect(detail.textContent).toContain("Oct 9, 2026");
  });

  it("AUD-30 acceptance: no alarm styling appears for the below-CT difference", async () => {
    state("a");
    await caseList();
    const cells = await waitFor(() => {
      const found = document.querySelectorAll("[data-difference='neg']");
      expect(found.length).toBe(3);
      return [...found];
    });
    for (const cell of cells) {
      expect(cell.className).not.toMatch(/\btext-red\b|\bbg-red/);
    }
    expect(document.querySelector("[data-aud30='detail'] .text-red")).toBeNull();
  });

  it("AUD-30a the agent's analysis renders through AgentBlocks with its run number", async () => {
    state("a");
    await caseList();
    const block = await waitFor(() => {
      const b = document.querySelector<HTMLElement>("[data-aud30='analysis']");
      expect(b).not.toBeNull();
      return b as HTMLElement;
    });
    expect(block.textContent).toContain("Accrued Agent · run #4511");
    expect(block.querySelector("[data-agent-blocks='v1']")).not.toBeNull();
    expect(block.textContent).toContain("I have not decided whether this needs action.");
  });

  it("AUD-30a the decision card: three options, the recommendation tag, reserved to the EP", async () => {
    state("a");
    await caseList();
    const card = await screen.findByRole("region", { name: C.question.facts });
    expect(card.textContent).toContain(C.options.facts.no_action.label);
    expect(card.textContent).toContain(C.options.facts.revise_and_reissue.label);
    expect(card.textContent).toContain(C.options.facts.notify_users.label);
    expect(card.textContent).toContain(C.recommendation);
    expect(card.textContent).toContain(C.reserved);
    const decide = within(card).getByRole("button", { name: /Decide/ });
    expect((decide as HTMLButtonElement).disabled).toBe(true);
  });

  it("AUD-30 Decide records the decision and logs the archive addition (b)", async () => {
    state("a");
    await caseList();
    const card = await screen.findByRole("region", { name: C.question.facts });
    fireEvent.click(
      within(card).getByRole("radio", { name: new RegExp(C.options.facts.no_action.label) }),
    );
    fireEvent.change(screen.getByRole("textbox", { name: C.rationaleLabel }), {
      target: { value: "Below clearly trivial." },
    });
    fireEvent.click(within(card).getByRole("button", { name: /Decide/ }));
    await waitFor(() => {
      expect(caseButton("PI-01").textContent).toContain("Concluded · no action");
    });
    fireEvent.click(screen.getByRole("tab", { name: /Archive additions/ }));
    const table = await waitFor(() => {
      const t = document.querySelector<HTMLElement>("[data-aud30='additions']");
      expect(t?.querySelectorAll("[data-addition]").length).toBe(2);
      return t as HTMLElement;
    });
    expect(table.textContent).toContain("Corrected certification and evaluation (PI-01)");
    expect(table.textContent).toContain("Awaiting partner approval");
  });

  it("AUD-30b decided · no action: the read-only card and the logged addition", async () => {
    state("b");
    await caseList();
    expect(caseButton("PI-01").textContent).toContain("Concluded · no action");
    const card = await screen.findByRole("region", { name: C.question.facts });
    expect(card.textContent).toContain("Margaret Okonkwo");
    expect(within(card).queryByRole("button", { name: /Decide/ })).toBeNull();
    fireEvent.click(screen.getByRole("tab", { name: /Archive additions/ }));
    await waitFor(() => {
      expect(document.querySelectorAll("[data-addition]").length).toBe(2);
    });
  });

  it("AUD-30c reissue chosen: the bar reads Reissue in progress and Reopen lands on AUD-23", async () => {
    const reissued = vi.fn();
    state("c", { onReissued: reissued });
    await caseList();
    expect(caseButton("PI-01").textContent).toContain("Reissue in progress");
    await waitFor(() => {
      expect(document.querySelector("[data-aud30='bar-right']")?.textContent).toContain(
        "Reissue in progress",
      );
    });
    fireEvent.click(await screen.findByRole("button", { name: C.reopen }));
    await waitFor(() => {
      expect(reissued).toHaveBeenCalledTimes(1);
    });
  });

  it("AUD-30d PI-02: the omitted procedure, its alternative procedure and its two options", async () => {
    state("d", { caseRef: "PI-02" });
    await caseList();
    expect(caseButton("PI-02").getAttribute("aria-current")).toBe("true");
    const detail = await waitFor(() => {
      const d = document.querySelector<HTMLElement>("[data-aud30='detail']");
      expect(d?.textContent).toContain("Monitoring inspection · Jan 11, 2027");
      return d as HTMLElement;
    });
    expect(detail.textContent).toContain("Jan 15, 2027 · Margaret Okonkwo");
    expect(detail.textContent).toContain(
      "The completion file has no documented inquiry of the benefits committee",
    );
    expect(detail.querySelector("[data-aud30='resolution']")?.textContent).toContain(
      "obtained benefits committee minutes of Oct 8, 2026",
    );
    expect(detail.querySelector("[data-aud30='comparison']")).toBeNull();
    const card = await screen.findByRole("region", { name: C.question.omitted });
    expect(card.textContent).toContain(C.options.omitted.no_action.label);
  });

  it("AUD-30e archive additions: who added and approved it, why, and its hash", async () => {
    state("e", { view: "additions" });
    const table = await waitFor(() => {
      const t = document.querySelector<HTMLElement>("[data-aud30='additions']");
      expect(t?.querySelectorAll("[data-addition]").length).toBe(1);
      return t as HTMLElement;
    });
    const row = table.querySelector("[data-addition]") as HTMLElement;
    expect(row.textContent).toContain("Jan 15, 2027");
    expect(row.textContent).toContain(
      "Memo — alternative procedure for the omitted bring-down inquiry",
    );
    expect(row.textContent).toContain("sha256 7c41…e2a9");
    expect(row.textContent).toContain("Hannah Leclerc");
    expect(row.textContent).toContain("Margaret Okonkwo");
    expect(row.textContent).toContain("Omitted procedure · AU-C 585 (PI-02)");
    expect(table.textContent).toContain(C.additions.footer);
  });

  it("AUD-30f New case…: type, source and description open a case", async () => {
    state("f", { newCase: true });
    await caseList();
    const sheet = await screen.findByRole("dialog", { name: C.sheet.title });
    expect(within(sheet).getByText(C.sheet.note)).toBeTruthy();
    fireEvent.change(within(sheet).getByRole("textbox", { name: C.sheet.description }), {
      target: { value: "Plan sponsor reported a late contribution remittance" },
    });
    fireEvent.click(within(sheet).getByRole("button", { name: C.sheet.open }));
    await waitFor(() => {
      expect(document.querySelectorAll("[data-case]").length).toBe(3);
    });
    expect(caseButton("PI-03").textContent).toContain(
      "Plan sponsor reported a late contribution remittance",
    );
  });

  it("AUD-30 the rail's Post-issuance row is the server's line", () => {
    expect(railLine(cases(null))).toBe("2 cases · 1 awaiting decision");
    expect(railLine(cases("revise_and_reissue"))).toBe("2 cases · reissue in progress");
    expect(railLine(cases("no_action"))).toBe("2 cases · all concluded");
  });

  it("AUD-30 a case's first line is its title, the rest its description", () => {
    expect(caseText("Title\nBody text.")).toEqual({ title: "Title", body: "Body text." });
    expect(caseText("Only a title")).toEqual({ title: "Only a title", body: null });
  });

  it("AUD-30 no agent-owned control approves, signs off, releases, sends or posts", async () => {
    state("a");
    await caseList();
    for (const b of screen.getAllByRole("button")) {
      expect(b.textContent).not.toMatch(/^(Approve|Sign off|Release|Send|Post)(\s|…|$)/);
    }
  });

  it("AUD-30 loading", async () => {
    show({
      ...scenarios.a,
      handlers: {
        ...scenarios.a.handlers,
        "GET /v1/audits/{work_item_id}/post-issuance/cases": never,
      },
    });
    await waitFor(() => {
      expect(document.querySelector("[data-screen='AUD-30']")).not.toBeNull();
    });
    expect(document.querySelector("[data-aud30='cases']")).toBeNull();
  });

  it("AUD-30 error", async () => {
    show({
      ...scenarios.a,
      handlers: {
        ...scenarios.a.handlers,
        "GET /v1/audits/{work_item_id}/post-issuance/cases": () =>
          new Response("{}", { status: 503 }),
      },
    });
    await waitFor(() => {
      expect(document.querySelector("[data-screen='AUD-30'] [role='alert']")).not.toBeNull();
    });
  });
});
