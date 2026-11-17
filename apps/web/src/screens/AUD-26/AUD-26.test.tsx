import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render } from "@testing-library/react";
import type { JSX, ReactNode } from "react";
import { afterEach, describe, expect, it } from "vitest";
import { SsarsWorkspace } from ".";
import { AUD26_SCENARIOS } from "./scenarios";

// A-08-T31 (AUD-26 a to e): each mode renders from its engagement type, and review mode shows no
// risk register, sampling, confirmations or control testing.

afterEach(cleanup);

function wrap(node: ReactNode): JSX.Element {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{node}</QueryClientProvider>;
}

const MODE = { a: "review", b: "review", c: "compilation", d: "preparation", e: "review" };

describe("AUD-26 SSARS workspace", () => {
  it.each(AUD26_SCENARIOS)("renders artboard %s in its engagement's mode", (st) => {
    const { container } = render(wrap(<SsarsWorkspace st={st} />));
    const root = container.querySelector("[data-screen='AUD-26']");
    expect(root?.getAttribute("data-scenario")).toBe(st);
    expect(root?.getAttribute("data-mode")).toBe(MODE[st]);
    expect(
      container.querySelector("[data-fieldwork='ssars-rail']")?.getAttribute("data-mode"),
    ).toBe(MODE[st]);
  });

  it.each(["a", "b", "e"])("review mode (%s) shows no audit-only work", (st) => {
    const { container } = render(wrap(<SsarsWorkspace st={st} />));
    const text = container.textContent.toLowerCase();
    for (const banned of ["risk register", "sampling", "confirmation", "control testing"]) {
      expect(text).not.toContain(banned);
    }
  });

  it("preparation prints 'No assurance is provided.' on every page", () => {
    const { container } = render(wrap(<SsarsWorkspace st="d" />));
    const pages = container.querySelectorAll("[data-page]");
    expect(pages.length).toBeGreaterThan(0);
    for (const page of pages) {
      expect(page.querySelector("[data-page-footer]")?.textContent).toContain(
        "No assurance is provided.",
      );
    }
    expect(container.textContent).toContain("No report — AR-C 70");
    expect(container.textContent).toContain("Approved by Carla Juniper (POR-08)");
  });

  it("state e leaves Grants unexplained with Ask client…; a shows the explanation", () => {
    const { container } = render(wrap(<SsarsWorkspace st="e" />));
    expect(container.textContent).toContain("Ask client…");
    expect(container.querySelector("[data-aud26='explanation']")).toBeNull();
    cleanup();
    const a = render(wrap(<SsarsWorkspace st="a" />));
    expect(a.container.querySelector("[data-aud26='explanation']")).not.toBeNull();
  });

  it("shows no dollar sign in the statement table", () => {
    const { container } = render(wrap(<SsarsWorkspace st="a" />));
    expect(container.querySelector("[data-aud26='statement']")?.textContent).not.toContain("$");
  });
});
