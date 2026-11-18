import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import type { JSX, ReactNode } from "react";
import { afterEach, describe, expect, it } from "vitest";
import { ConfirmationsWorkspace, MANAGER_GRANTS } from ".";
import { AUD14_FIXTURE_NOTE } from "./fixture-note";
import { AUD14_SCENARIOS } from "./scenarios";

// A-08-T29 (AUD-14 a to e): every artboard renders; state e disables Send with the red helper;
// Accept reconciliation renders only for the manager role; the log keeps its four confirmations.

afterEach(cleanup);

function wrap(node: ReactNode): JSX.Element {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{node}</QueryClientProvider>;
}

describe("AUD-14 confirmations", () => {
  it.each(AUD14_SCENARIOS)("renders artboard %s", (st) => {
    const { container } = render(wrap(<ConfirmationsWorkspace st={st} />));
    const root = container.querySelector("[data-screen='AUD-14']");
    expect(root?.getAttribute("data-scenario")).toBe(st);
    expect(container.querySelectorAll("[data-confirmation]").length).toBe(4);
  });

  it("state e disables Send with the address helper", () => {
    render(wrap(<ConfirmationsWorkspace st="e" />));
    const send = screen.getByRole("button", { name: "Send" });
    expect(send).toHaveProperty("disabled", true);
    expect(document.body.textContent).toContain("Verify the address before sending");
  });

  it("renders Accept reconciliation only for the manager", () => {
    render(wrap(<ConfirmationsWorkspace st="a" />));
    expect(screen.queryByRole("button", { name: "Accept reconciliation" })).toBeNull();
    cleanup();
    render(wrap(<ConfirmationsWorkspace st="a" grants={MANAGER_GRANTS} />));
    expect(screen.getByRole("button", { name: "Accept reconciliation" })).toBeTruthy();
  });

  it("keeps C3 as the exception until accepted (a), then Closed (d)", () => {
    const status = (st: string): string | null => {
      const { container } = render(wrap(<ConfirmationsWorkspace st={st} />));
      const row = container.querySelector("[data-confirmation='C3']");
      const s = row?.getAttribute("data-status") ?? null;
      cleanup();
      return s;
    };
    expect([status("a"), status("d")]).toEqual(["exception", "closed"]);
  });

  it("shows the coverage line and the client-control note", () => {
    const { container } = render(
      wrap(<ConfirmationsWorkspace st="a" note={AUD14_FIXTURE_NOTE} />),
    );
    const coverage = container.querySelector("[data-aud14='coverage']")?.textContent ?? "";
    expect(coverage).toContain("$897,950.00 of $5,860,000.00 (15.3%)");
    expect(coverage).toContain("differences $4,300.00 · CT $7,750");
    const note = container.querySelector("[data-aud14='client-note']")?.textContent ?? "";
    expect(note).toContain("Granite Peak sees only the authorization it signs.");
  });
});
