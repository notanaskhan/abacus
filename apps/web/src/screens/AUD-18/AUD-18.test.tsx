// A-07-T17 (TASK-5127): AUD-18 in fixture mode, every artboard. No Edit or Sign off for the EQR; only
// the assigned EQR concurs, with the attestation ticked; the agent evaluates nothing.
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { COMPLETION_WORK_ITEM } from "../../fixtures/seed/audit-completion";
import { newQueryClient } from "../../testing/support";
import { COPY } from "./copy";
import { type State, scenarios } from "./scenarios";
import { EqrWorkspacePage, type EqrWorkspaceProps } from "./Workspace";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

function show(state: State, props: Partial<EqrWorkspaceProps> = {}): void {
  restore = installFixtureMode(scenarios[state]);
  render(
    <QueryClientProvider client={newQueryClient()}>
      <EqrWorkspacePage auditId={COMPLETION_WORK_ITEM} {...props} />
    </QueryClientProvider>,
  );
}

const ready = async (): Promise<void> => {
  await waitFor(() => {
    expect(document.querySelector("[data-concurrence]")).not.toBeNull();
  });
};

describe("AUD-18", () => {
  it("a: 6 of 10, blocked, with no edit or sign-off control", async () => {
    show("a");
    await ready();
    expect(document.querySelector("[data-overview]")?.textContent).toContain("6 of 10 complete");
    expect(document.querySelector('[data-concurrence="blocked"]')?.textContent).toContain(
      "Blocked: 4 checklist items open · 2 EQR notes not cleared.",
    );
    const words = [...document.querySelectorAll("button")].map((b) => b.textContent);
    expect(words).not.toContain("Edit");
    expect(words).not.toContain("Sign off…");
  });

  it("a: a responded note offers Clear to the EQR", async () => {
    show("a");
    await ready();
    expect(document.querySelector('[data-note="EQR-1"]')?.textContent).toContain(COPY.note.clear);
    expect(document.querySelector('[data-note="EQR-2"]')?.textContent).not.toContain(
      COPY.note.clear,
    );
  });

  it("b, b2: ready, and Concur needs the attestation", async () => {
    show("b2", { concurring: true });
    await waitFor(() => {
      expect(document.querySelector('[data-sheet="concur"]')).not.toBeNull();
    });
    const button = [...document.querySelectorAll('[data-sheet="concur"] button')].find(
      (b) => b.textContent === COPY.sheet.concur,
    ) as HTMLButtonElement;
    expect(button.disabled).toBe(true);
    fireEvent.click(document.querySelector('[data-sheet="concur"] input') as Element);
    expect(button.disabled).toBe(false);
  });

  it("c: concurred reads who and G6", async () => {
    show("c");
    await ready();
    const card = document.querySelector('[data-concurrence="done"]')?.textContent;
    expect(card).toContain("Thomas Whitcombe");
    expect(card).toContain(COPY.concurrence.met);
  });

  it("d: the agent's line says it evaluated nothing", async () => {
    show("d", { dock: "agent" });
    await waitFor(() => {
      expect(document.querySelector("[data-agent]")?.textContent).toContain(
        "I have not evaluated them.",
      );
    });
  });

  it("e: not the EQR can't concur", async () => {
    show("e");
    await ready();
    expect(document.querySelector("[data-not-eqr]")?.textContent).toBe(COPY.notEqr);
    const words = [...document.querySelectorAll("button")].map((b) => b.textContent);
    expect(words).not.toContain(COPY.concurrence.action);
    expect(words).not.toContain(COPY.markReviewed);
  });
});
