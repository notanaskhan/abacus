import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render } from "@testing-library/react";
import type { JSX, ReactNode } from "react";
import { afterEach, describe, expect, it } from "vitest";
import { TestingWorkspace } from ".";
import { AUD12_SCENARIOS } from "./scenarios";

// A-08-T27 (AUD-12 a to h): every artboard renders in fixture mode, and the value chips are the
// only clickable source links (no other element opens the viewer).

afterEach(cleanup);

function wrap(node: ReactNode): JSX.Element {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{node}</QueryClientProvider>;
}

describe("AUD-12 testing workspace", () => {
  it.each(AUD12_SCENARIOS)("renders artboard %s", (st) => {
    const { container } = render(wrap(<TestingWorkspace st={st} />));
    const root = container.querySelector("[data-screen='AUD-12']");
    expect(root?.getAttribute("data-scenario")).toBe(st);
  });

  it("offers source links only through value chips", () => {
    const { container } = render(wrap(<TestingWorkspace st="a" />));
    const sourceLinks = container.querySelectorAll("[data-source-link]");
    const chips = container.querySelectorAll("[data-value-chip]");
    expect(sourceLinks.length).toBe(chips.length);
  });
});
