// A-06-T12 (TASK-3025): the Evaluation chrome in fixture mode. Row acceptance: "All four routes
// render in fixture mode with tab counts from the server, Back closes each new overlay, and
// planned links render Not built yet in fixture builds and nothing in production."
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { encodeRef } from "../../app-core/overlays";
import { NORTHWIND_AUDIT } from "../../fixtures/scenarios/AUD-06";
import { scenarios } from "../../fixtures/scenarios/AUD-02";
import { newQueryClient } from "../../testing/support";
import { type EvaluationTab, EvaluationPage } from "./EvaluationPage";
import { PlannedSheet } from "./PlannedSheet";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

function show(tab: EvaluationTab, onTab = vi.fn()): void {
  restore = installFixtureMode(scenarios.a);
  render(
    <QueryClientProvider client={newQueryClient()}>
      <EvaluationPage auditId={NORTHWIND_AUDIT} tab={tab} onTab={onTab} />
    </QueryClientProvider>,
  );
}

describe.each(["findings", "misstatements", "review-notes", "fs-disclosure"] as const)(
  "/audits/$auditId/%s",
  (tab) => {
    it("renders the audit bar and the planned body, Not built yet", async () => {
      show(tab);
      await waitFor(() => {
        expect(
          document.querySelector(`[data-screen='evaluation'][data-tab='${tab}']`),
        ).not.toBeNull();
        expect(document.body.textContent).toContain("Not built yet");
      });
    });
  },
);

describe("Evaluation tabs", () => {
  it("show the server's counts: Findings 9, Misstatements 2", async () => {
    show("findings");
    await waitFor(() => {
      const tabs = document.querySelector("[data-evaluation-tabs]");
      expect(tabs?.textContent).toContain("9");
      expect(tabs?.textContent).toContain("2");
    });
  });

  it("move between the routes", async () => {
    const onTab = vi.fn();
    show("findings", onTab);
    const misstatements = await waitFor(() => {
      const found = [...document.querySelectorAll<HTMLElement>("[role='tab']")].find((t) =>
        t.textContent.startsWith("Misstatements"),
      );
      expect(found).toBeDefined();
      return found as HTMLElement;
    });
    fireEvent.click(misstatements);
    expect(onTab).toHaveBeenCalledWith("misstatements");
  });
});

describe.each(["convert", "send-entries", "send-fs-draft"])("?ov=%s", (key) => {
  it("opens Not built yet and Back (Escape) closes it", async () => {
    const close = vi.fn();
    const ref = { key, args: ["00000000-0000-4000-8000-000000000001"] };
    render(<PlannedSheet ref={ref} index={0} close={close} />);
    await waitFor(() => {
      expect(document.querySelector(`[data-planned-overlay='${key}']`)).not.toBeNull();
    });
    expect(encodeRef(ref)).toContain(key);
    fireEvent.keyDown(document.activeElement ?? document.body, { key: "Escape" });
    await waitFor(() => {
      expect(close).toHaveBeenCalled();
    });
  });
});
