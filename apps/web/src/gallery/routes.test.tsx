// F-05-T09 (SPEC-048): the /components subtree renders from fixtures with no API calls, the
// tokens page lists every token under both ladders, /components/screens/:id passes its query
// parameters through, and /_ds no longer routes. Axe on /components/** is in e2e/components.spec.ts.
import { ICON_NAMES, TooltipProvider } from "@abacus/ui";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "@tanstack/react-router";
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { FixtureParams } from "./fixture-mode";
import { colorRows, parseTokens } from "./tokens";

const fetchSpy = vi.fn();

// The first visit compiles the lazy gallery chunk.
vi.setConfig({ testTimeout: 30_000 });

beforeEach(() => {
  vi.stubGlobal("fetch", fetchSpy);
  fetchSpy.mockReset();
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  delete document.documentElement.dataset.contrast;
});

// The router reads the URL when it is created, so each visit gets a fresh module graph. `setup`
// runs against that graph's fixture-mode registry before anything renders.
async function visit(
  url: string,
  setup?: (fixture: typeof import("./fixture-mode")) => void,
): Promise<void> {
  vi.resetModules();
  window.history.pushState({}, "", url);
  setup?.(await import("./fixture-mode"));
  const { router } = await import("../router");
  render(
    <QueryClientProvider client={new QueryClient()}>
      <TooltipProvider>
        <RouterProvider router={router} />
      </TooltipProvider>
    </QueryClientProvider>,
  );
}

describe("ac10 gallery routes", () => {
  it("renders the index from the specimen registry with no API calls", async () => {
    await visit("/components");
    expect(await screen.findByRole("heading", { name: "Components" })).toBeTruthy();
    expect(await screen.findByRole("region", { name: "Components in use" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "C-00 Components in use" })).toBeTruthy();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("keeps the existing gallery content: buttons, overlays and the example table", async () => {
    await visit("/components");
    expect(await screen.findByRole("button", { name: "Open drawer" })).toBeTruthy();
    expect(screen.getByRole("table", { name: "Example requests" })).toBeTruthy();
    expect(fetchSpy).not.toHaveBeenCalled();
  });
});

describe("ac11 tokens page", () => {
  it("lists every colour token with contrast on card, shell and nested under both ladders", async () => {
    await visit("/components/tokens");
    const table = await screen.findByRole("table", { name: /Every colour token/ });
    const rows = parseTokens().filter((t) => t.group === "color");
    expect(rows.length).toBeGreaterThan(40);
    for (const t of rows) {
      expect(table.querySelector(`[data-token="color-${t.name}"]`), t.name).not.toBeNull();
    }
    for (const col of ["AA on card", "AA on shell", "AA on nested", "Reference on card"]) {
      expect(within(table).getByRole("columnheader", { name: col })).toBeTruthy();
    }
  });

  it("lists the non-colour tokens too", async () => {
    await visit("/components/tokens");
    const table = await screen.findByRole("table", { name: "Every non-colour token" });
    for (const t of parseTokens().filter((x) => x.group !== "color")) {
      expect(table.querySelector(`[data-token="${t.group}-${t.name}"]`), t.name).not.toBeNull();
    }
  });

  it("shows the AA ladder passing and the handoff's ink-3 failing 4.5:1 and its match text lighter", () => {
    const by = (n: string) => colorRows().find((r) => r.name === n);
    expect(by("ink-2")?.contrast.aa.nested).toBeGreaterThanOrEqual(4.5);
    expect(by("ink-3")?.contrast.aa.nested).toBeGreaterThanOrEqual(4.5);
    expect(by("ink-3")?.contrast.reference.card).toBeLessThan(4.5);
    expect(by("match-ink")?.contrast.aa.card).toBeGreaterThanOrEqual(4.5);
    expect(by("match-ink")?.contrast.reference.card).toBeLessThan(
      by("match-ink")?.contrast.aa.card ?? 0,
    );
  });
});

describe("F-05-T13 icons page", () => {
  it("lists every registered icon name with its glyph, and the custom glyphs, with no API calls", async () => {
    await visit("/components/icons");
    const table = await screen.findByRole("table", { name: /Every registered icon name/ });
    expect(ICON_NAMES).toHaveLength(252);
    for (const name of ICON_NAMES) {
      const row = table.querySelector(`tr[data-icon-name="${name}"]`);
      expect(row, name).not.toBeNull();
      expect(row?.querySelectorAll(`svg[data-icon="${name}"]`)).toHaveLength(2);
    }
    expect(table.querySelectorAll("tbody tr")).toHaveLength(ICON_NAMES.length);
    const custom = screen.getByRole("region", { name: "Custom glyphs" });
    for (const id of ["agent-monogram", "atom-mark", "half-disc", "vendor-tile"]) {
      expect(custom.querySelector(`svg[data-glyph="${id}"]`), id).not.toBeNull();
    }
    expect(screen.getByRole("link", { name: "Icons" })).toBeTruthy();
    expect(fetchSpy).not.toHaveBeenCalled();
  });
});

describe("ac11 screens/:id", () => {
  it("shows Not built for an unregistered ID", async () => {
    await visit("/components/screens/NO-SUCH-SCREEN");
    expect(await screen.findByText("Not built")).toBeTruthy();
    expect(screen.getByText(/NO-SUCH-SCREEN/)).toBeTruthy();
  });

  it("mounts a registered screen and passes the query parameters through", async () => {
    let seen: FixtureParams | undefined;
    await visit(
      "/components/screens/TEST-01?st=b&as=jonah-feld&clock=2026-09-14T09:24:00-05:00&latency=250&frame=1&static=1&contrast=reference",
      ({ registerScreen }) => {
        registerScreen("TEST-01", {
          title: "Test screen",
          Component: ({ params }) => {
            seen = params;
            return <p>Test screen body</p>;
          },
        });
      },
    );
    expect(await screen.findByText("Test screen body")).toBeTruthy();
    expect(seen).toEqual({
      st: "b",
      as: "jonah-feld",
      clock: "2026-09-14T09:24:00-05:00",
      latency: "250",
      frame: true,
      static: true,
      contrast: "reference",
    });
    // frame=1 drops the gallery's own chrome.
    expect(screen.queryByRole("navigation", { name: "Components" })).toBeNull();
  });
});

describe("ac4 contrast parameter", () => {
  it("sets data-contrast=reference on <html> in the gallery, and only then", async () => {
    await visit("/components/tokens");
    await screen.findByRole("table", { name: /Every colour token/ });
    expect(document.documentElement.dataset.contrast).toBeUndefined();
    cleanup();
    await visit("/components/tokens?contrast=reference");
    await screen.findByRole("table", { name: /Every colour token/ });
    expect(document.documentElement.dataset.contrast).toBe("reference");
  });
});

describe("ac15 /_ds", () => {
  it("no longer routes", async () => {
    await visit("/_ds");
    expect(await screen.findByText("Page not found")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Open drawer" })).toBeNull();
  });
});
