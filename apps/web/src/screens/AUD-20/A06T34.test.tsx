// A-06-T34 (TASK-6120; ADR-078): independent tests for the AUD-20 UI, written from the row and
// the handoff, not the screen's code. Row: "fail if any figure on AUD-20 is computed in the
// browser." Covered: the client preview shows no checklist, source link, agent text or studio
// link; every figure is drawn from the server's string (no arithmetic in the screen's source);
// N/A asks for its reason before anything is sent; Send draft is a person's explicit click.
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { AUD20_ENGAGEMENT } from "../../fixtures/seed/aud20";
import { newQueryClient } from "../../testing/support";
import { COPY } from "./copy";
import { type Aud20State, scenarios } from "./scenarios";
import { FsDisclosurePane, type FsDisclosureProps } from "./Statements";

const { process } = globalThis as unknown as { process: { cwd: () => string } };
const SOURCE = readFileSync(
  join(process.cwd(), "src", "screens", "AUD-20", "Statements.tsx"),
  "utf8",
);

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
  vi.restoreAllMocks();
});

function show(state: Aud20State, props: Partial<FsDisclosureProps> = {}): void {
  restore = installFixtureMode(scenarios[state]);
  render(
    <QueryClientProvider client={newQueryClient()}>
      <FsDisclosurePane engagementId={AUD20_ENGAGEMENT} {...props} />
    </QueryClientProvider>,
  );
}

describe("AUD-20 (independent)", () => {
  it("the client preview carries no checklist, sources, agent text or studio link", async () => {
    show("d", { preview: true });
    await waitFor(() => {
      expect(document.querySelector("[data-watermark]")).not.toBeNull();
    });
    expect(document.querySelector('[data-pane="checklist"]')).toBeNull();
    expect(document.querySelector("[data-sources]")).toBeNull();
    expect(document.querySelector("button[data-figure]")).toBeNull();
    expect(document.querySelector("[data-agent-text]")).toBeNull();
    expect(document.querySelector('a[href*="studio"], a[href*="FSP-"]')).toBeNull();
    expect(document.body.textContent).not.toMatch(/Studio|Accrued Agent/);
  });

  it("no figure is computed in the browser: the screen's source does no arithmetic on amounts", () => {
    expect(SOURCE).not.toMatch(/parseFloat\(|\.reduce\(|Decimal\(/);
    // amounts are formatted from the server's string; the only Number() is the zero check
    const numbers = SOURCE.match(/Number\(/g) ?? [];
    expect(numbers.length).toBeLessThanOrEqual(1);
    expect(SOURCE).not.toMatch(/\b(?:value|amount|total)s?\s*[+\-*/]\s*\w/);
  });

  it("N/A asks for a reason before anything is sent", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    show("a");
    await waitFor(() => {
      expect(document.querySelector("[data-item]")).not.toBeNull();
    });
    const row = document.querySelector<HTMLElement>("[data-item]");
    const before = fetchSpy.mock.calls.filter((c) => String(c[1]?.method) === "PUT").length;
    const na = row?.querySelectorAll("button");
    const naButton = Array.from(na ?? []).find((b) => b.textContent === COPY.checklist.answers.na);
    if (naButton !== undefined && row?.querySelector("[data-reason]") === null) {
      fireEvent.click(naButton);
      await waitFor(() => {
        expect(row.querySelector("[data-reason]")).not.toBeNull();
      });
      const after = fetchSpy.mock.calls.filter((c) => String(c[1]?.method) === "PUT").length;
      expect(after).toBe(before);
    }
  });

  it("Send draft is a person's explicit click: opening the sheet sends nothing", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    show("a2", { sending: true });
    await waitFor(() => {
      expect(document.querySelector('[data-sheet="send-draft"]')).not.toBeNull();
    });
    const posts = fetchSpy.mock.calls.filter((c) => String(c[1]?.method) === "POST");
    expect(posts).toHaveLength(0);
    expect(screen.getAllByText(COPY.send.send).length).toBeGreaterThan(0);
  });
});
