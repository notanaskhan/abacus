// CLI-05 · Tax profile (T-01-T14, part 1). Scenario tests for the built artboards d and f
// (SPEC-501 AC-11; T-01 §3.1), plus the row's acceptance: the consent row reads "Use · AI
// disclosure" with two signed-document sub-rows, the identity band carries the last four only,
// and a reveal leaves nothing of the value in the DOM once it re-masks. axe runs in the walk.
import { client } from "@abacus/api-client/client";
import { toastStore } from "@abacus/ui";
import { QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { newQueryClient } from "../../testing/support";
import { CLI05 } from ".";
import { AGENT_NOTE, type Cli05State, ENTITY, SECTION, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
  toastStore.clear();
  vi.useRealTimers();
});

function show(state: Cli05State): void {
  restore = installFixtureMode(scenarios[state]);
  render(
    <QueryClientProvider client={newQueryClient()}>
      <CLI05 clientEntityId={ENTITY[state]} section="consents" />
    </QueryClientProvider>,
  );
}

describe("CLI-05 d · consents · Whitley", () => {
  it("reads Use · AI disclosure with one sub-row per signed document", async () => {
    show("d");
    const set = (await screen.findByText("Use · AI disclosure (§7216, 2 consents)")).closest("tr");
    expect(set?.textContent).toContain("Jan 20, 2026 · Marcus ✓ · Dana ✓");
    expect(set?.textContent).toContain(
      "Return information disclosed to Amazon Web Services (Bedrock) · model inference · US",
    );
    expect(set?.textContent).toContain("Signed");
    const docs = document.querySelectorAll('[data-row="document"]');
    expect(docs).toHaveLength(2);
    expect(docs[0]?.textContent).toContain(
      "Consent to use tax return information · BH §7216 Consent to Use v2 · Marcus ✓ · Dana ✓",
    );
    expect(docs[1]?.textContent).toContain(
      "Consent to disclose tax return information to AI service providers",
    );
    const offshore = document.querySelector('[data-row="offshore"]');
    expect(offshore?.textContent).toContain("Disclosure to offshore preparers");
    expect(offshore?.textContent).toContain("Not requested");
    expect(screen.getByText(/Rev\. Proc\. 2013-14 §§5\.04–5\.05/)).toBeTruthy();
  });

  it("shows the rail with discs and the identity band's last four only", async () => {
    show("d");
    const rail = await screen.findByRole("navigation", { name: "Tax profile sections" });
    expect(within(rail).getByText("Form 8821 · 2022–2026 · on file")).toBeTruthy();
    expect(
      within(rail).getByText(
        "§7216 use · AI disclosure (2 consents) · Signed · expires Dec 31 2026",
      ),
    ).toBeTruthy();
    const identity = screen.getByRole("region", { name: "Identity" });
    expect(within(identity).getByText("Marcus Whitley")).toBeTruthy();
    expect(identity.textContent).not.toMatch(/\d{3}-\d{2}-\d{4}/);
  });

  it("reveals for 10 seconds and leaves nothing of the value once re-masked", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    show("d");
    const identity = await screen.findByRole("region", { name: "Identity" });
    const reveal = await within(identity).findByRole("button", { name: "Reveal (logged)" });
    fireEvent.click(reveal);
    const dialog = await screen.findByRole("dialog", { name: "Reveal taxpayer ID" });
    fireEvent.click(within(dialog).getByRole("button", { name: "Reveal" }));
    expect(await within(identity).findByText("000-00-0426")).toBeTruthy();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000);
    });
    await waitFor(() => {
      expect(within(identity).queryByText("000-00-0426")).toBeNull();
    });
    expect(document.body.innerHTML).not.toContain("000-00-0426");
  });
});

describe("CLI-05 f · partially signed · Ferris", () => {
  it("warns that Kai Ferris has not signed, with Resend…", async () => {
    show("f");
    const banner = await screen.findByText(
      "§7216 consents (use · AI disclosure) partially signed — Kai Ferris has not signed. Agents cannot read return information until both sign (firm policy).",
    );
    const row = banner.closest('[role="status"]');
    expect(row).not.toBeNull();
    if (row === null) return;
    expect(within(row as HTMLElement).getByRole("button", { name: "Resend…" })).toBeTruthy();
    expect(screen.getByText("Requested · 1 of 2 signed")).toBeTruthy();
  });
});

// T-01-T34 (part 2, fixture mode): "Scenario tests for b, c, e and g pass, and no full CAF number
// or SSN appears in the DOM."
function showAt(state: Cli05State): void {
  restore = installFixtureMode(scenarios[state]);
  render(
    <QueryClientProvider client={newQueryClient()}>
      <CLI05 clientEntityId={ENTITY[state]} section={SECTION[state]} />
    </QueryClientProvider>,
  );
}

/** Nine or more digits in a row, or an SSN or CAF shape, anywhere in the page's text. */
function fullNumbers(): string[] {
  const text = document.body.textContent;
  return [...text.matchAll(/\b\d{3}-\d{2}-\d{4}\b|\b\d{4}-\d{5}[A-Z]?\b|\b\d{9,}\b/gu)].map(
    (m) => m[0],
  );
}

describe("CLI-05 part 2 (T-01-T34)", () => {
  it("b · transcripts, none yet: the empty state with Upload transcript…", async () => {
    showAt("b");
    expect(await screen.findByText("No transcripts yet.")).toBeTruthy();
    expect(
      screen.getByText(
        "Pull them from IRS e-Services (TDS) under the 8821 on file, then upload here.",
      ),
    ).toBeTruthy();
    // The header's and the empty state's (CLI-05b draws both), until the upload dialog lands.
    const uploads = screen.getAllByRole("button", { name: "Upload transcript…" });
    expect(uploads).toHaveLength(2);
    for (const u of uploads) expect(u).toHaveProperty("disabled", true);
    expect(screen.getByRole("button", { name: "Compare to return" })).toHaveProperty(
      "disabled",
      true,
    );
    expect(fullNumbers()).toEqual([]);
  });

  it("c · authorizations: the 8821 with CAF last four only, the 8821-versus-2848 note and State", async () => {
    showAt("c");
    expect(await screen.findByText("Tax information authorization")).toBeTruthy();
    const designees = document.querySelector("[data-designees]");
    expect(designees?.textContent).toBe("Daniel Reyes (CAF ••••0912) · Kevin Osei (CAF ••••4471)");
    expect(screen.getByText("Income · Form 1040")).toBeTruthy();
    expect(screen.getByText("2022–2026")).toBeTruthy();
    expect(screen.getByText("Feb 3, 2026")).toBeTruthy();
    expect(screen.getByText("On file")).toBeTruthy();
    expect(
      screen.getByText(
        "An 8821 lets us receive transcripts and notices, not represent. The CP2000 response will be signed by Marcus and Dana, or file Form 2848 to represent them.",
      ),
    ).toBeTruthy();
    expect(screen.getByRole("button", { name: "Draft Form 2848…" })).toBeTruthy();
    expect(screen.getByText("Colorado · not on file")).toBeTruthy();
    expect(screen.getByRole("button", { name: "+ Add" })).toBeTruthy();
    expect(fullNumbers()).toEqual([]);
  });

  it("e · elections on Ridgeline: §754 pending, PTET IL, CO and NY, BBA, §163(j), accrual", async () => {
    showAt("e");
    expect(
      await screen.findByText("Not made — decision pending (due with the TY2025 return)"),
    ).toBeTruthy();
    const ptet = document.querySelector("[data-election='ptet']");
    expect(ptet?.textContent).toContain("IL Elected · 28,044");
    expect(ptet?.textContent).toContain("CO Elected · 17,070");
    expect(ptet?.textContent).toContain("NY Elected · 18,982");
    expect(screen.getByText("Partnership representative (BBA)")).toBeTruthy();
    expect(screen.getByText(/^Not eligible — /u)).toBeTruthy();
    expect(
      screen.getByText("Exempt — small business (average gross receipts under $31M)"),
    ).toBeTruthy();
    expect(document.querySelector("[data-election='accounting_method']")?.textContent).toBe(
      "Accrual",
    );
    expect(fullNumbers()).toEqual([]);
  });

  it("g · none on file (Santos): No 8821 or 2848 on file with Request Form 8821…", async () => {
    showAt("g");
    const empties = await screen.findAllByText("No 8821 or 2848 on file");
    expect(empties.length).toBeGreaterThanOrEqual(1);
    expect(screen.getByRole("button", { name: "Request Form 8821…" })).toBeTruthy();
    expect(fullNumbers()).toEqual([]);
  });

  it("the section control switches the canvas", async () => {
    showAt("c");
    await screen.findByText("Tax information authorization");
    fireEvent.click(screen.getByRole("tab", { name: "Transcripts" }));
    expect(await screen.findByRole("table", { name: "Transcripts register" })).toBeTruthy();
  });
});

describe("CLI-05 a · transcripts · 2 differences (T-01-T50)", () => {
  function showA(note: boolean, latencyMs = 0): void {
    restore = installFixtureMode(scenarios.a, latencyMs > 0 ? { latencyMs } : {});
    render(
      <QueryClientProvider client={newQueryClient()}>
        <CLI05
          clientEntityId={ENTITY.a}
          section={SECTION.a}
          {...(note ? { agentNote: AGENT_NOTE } : {})}
        />
      </QueryClientProvider>,
    );
  }

  it("lists the four pulls with their results and opens the TY2024 comparison", async () => {
    showA(true);
    const register = await screen.findByRole("table", { name: "Transcripts register" });
    const rows = within(register).getAllByRole("row").slice(1);
    expect(rows.map((r) => r.textContent)).toEqual([
      expect.stringContaining(
        "Wage & Income2024Sep 14, 9:05 AM · Kevin OseiForm 88212 differences",
      ),
      expect.stringContaining(
        "Account2024Sep 14, 9:05 AM · Kevin OseiForm 8821TC 922 · Aug 24, 2026",
      ),
      expect.stringContaining(
        "Wage & Income2025Sep 14, 9:06 AM · Kevin OseiForm 8821Agrees to return",
      ),
      expect.stringContaining("TC 150 · Apr 10, 2026 · balance 0.00"),
    ]);
    expect(rows[0]?.getAttribute("aria-selected")).toBe("true");
    const card = await screen.findByRole("region", {
      name: "Wage & Income · TY2024 vs return as filed",
    });
    expect(within(card).getByText("off 3,120")).toBeTruthy();
    const lines = card.querySelectorAll("tbody tr");
    expect(lines[0]?.textContent).toBe(
      "Form 1099-INTFront Range Bank1,870.00—1,870.00Not on return",
    );
    expect(lines[1]?.textContent).toBe(
      "Form 1099-INTLakeview Credit Union1,250.00—1,250.00Not on return",
    );
    expect(lines[2]?.textContent).toBe("Total difference3,120.000.003,120.00");
    expect(card.querySelector("[data-agreeing]")?.textContent).toBe(
      "4 other information returns agree to the return (Forms W-2 × 2, Form 1098, Form 1099-INT × 1).",
    );
    expect(within(card).getByRole("heading", { name: /Why This Was Surfaced/ })).toBeTruthy();
    expect(card.textContent).toContain("3,120.00 × 22% = 686.40");
    expect(card.textContent).toContain("IRS CP2000 · Aug 24, 2026 · 2 citations");
    expect(screen.getByText("TY2024 · 2 differences")).toBeTruthy();
  });

  it("shows no agent note without the fixture's (production) and no full identifier", async () => {
    showA(false);
    await screen.findByRole("region", { name: "Wage & Income · TY2024 vs return as filed" });
    expect(document.querySelector("[data-agent-note]")).toBeNull();
    expect(screen.queryByText(/Why This Was Surfaced/)).toBeNull();
    expect(document.body.textContent).not.toMatch(/\b\d{9,}\b|\b\d{3}-\d{2}-\d{4}\b/);
  });

  it("re-runs Compare to return with Comparing… in the selected row's Result", async () => {
    showA(false, 60);
    await screen.findByRole("region", { name: "Wage & Income · TY2024 vs return as filed" });
    const compare = screen.getByRole("button", { name: "Compare to return" });
    await waitFor(() => {
      expect((compare as HTMLButtonElement).disabled).toBe(false);
    });
    fireEvent.click(compare);
    expect(await screen.findByText("Comparing…")).toBeTruthy();
    await waitFor(() => {
      expect(screen.queryByText("Comparing…")).toBeNull();
    });
    expect(screen.getByText("2 differences")).toBeTruthy();
  });

  it("selecting the TY2025 pull shows its result and no TY2024 card", async () => {
    showA(false);
    const register = await screen.findByRole("table", { name: "Transcripts register" });
    fireEvent.click(
      within(register).getAllByRole("button", { name: "Wage & Income" })[1] as HTMLElement,
    );
    await waitFor(() => {
      expect(
        screen.queryByRole("region", { name: "Wage & Income · TY2024 vs return as filed" }),
      ).toBeNull();
    });
  });
});
