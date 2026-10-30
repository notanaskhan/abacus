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
import { type Cli05State, ENTITY, scenarios } from "./scenarios";

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
