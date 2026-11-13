// P-02-T10 / T11 (TASK-7620, TASK-7619): SHL-02 "Go…" renders every artboard from its fixture
// scenario. a lists the designed groups with the matched words at 500; e is a without the walled
// rows and draws no note, glyph or count (DEC-43); d offers one visible-only suggestion; b shows
// Recent and Create; ⌘↵ opens a row in a new tab and keeps the palette open; the search text
// travels only in the POST body.
import { client } from "@abacus/api-client/client";
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { renderRoutes } from "../../testing/support";
import { Go } from ".";
import { COPY } from "./copy";
import { QUERIES, type Shl02State, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

const opened: { href: string; newTab: boolean }[] = [];

async function mount(state: Shl02State): Promise<HTMLInputElement> {
  restore = installFixtureMode(scenarios[state]);
  opened.length = 0;
  renderRoutes([
    {
      path: "/",
      component: () => (
        <Go
          open
          onOpenChange={() => undefined}
          onOpen={(href, newTab) => {
            opened.push({ href, newTab });
          }}
        />
      ),
    },
  ]);
  const input = await screen.findByRole<HTMLInputElement>("combobox");
  fireEvent.change(input, { target: { value: QUERIES[state] } });
  return input;
}

const groupLabels = (): string[] =>
  screen.queryAllByRole("group").map((g) => g.getAttribute("aria-label") ?? "");

describe("SHL-02 Go…", () => {
  it("a: the designed groups for 'feld', the matched words at 500", async () => {
    await mount("a");
    await waitFor(() => {
      expect(groupLabels()).toEqual([
        "Clients",
        "Returns",
        "Binders",
        "Files",
        "Inbox",
        "Actions",
      ]);
    });
    // P-02 AC: the actions bound to the top Clients result (DEC-4631).
    expect(screen.getByText("New engagement for Jonah & Claire Feld…")).toBeTruthy();
    expect(screen.getByText("New to-do on Jonah & Claire Feld…")).toBeTruthy();
    expect(screen.getByText("Jonah Feld, limited partner 25%", { exact: false })).toBeTruthy();
    expect(document.querySelectorAll("[data-match]").length).toBeGreaterThan(0);
    expect(screen.getByRole("status").textContent).toBe(COPY.results(6));
  });

  it("e: a without the walled rows, and no note, glyph or count", async () => {
    await mount("e");
    await waitFor(() => {
      expect(groupLabels()).toEqual(["Clients", "Returns", "Binders", "Actions"]);
    });
    expect(document.body.textContent).not.toMatch(/hidden|ethical wall/i);
  });

  it("d: the empty state and one suggestion from visible documents", async () => {
    await mount("d");
    await waitFor(() => {
      expect(screen.getByText(COPY.empty("pellstret"))).toBeTruthy();
    });
    expect(screen.getByText(COPY.emptyHint)).toBeTruthy();
    // The suggestion arrives with the debounced response, after the empty line.
    await waitFor(() => {
      expect(
        screen.getByText(
          COPY.suggestion("Pell Street II LLC", "partner in Ridgeline Property Partners, LP"),
        ),
      ).toBeTruthy();
    });
  });

  it("b: Recent and Create with nothing typed", async () => {
    await mount("b");
    await waitFor(() => {
      expect(groupLabels()).toEqual(["Recent", "Create"]);
    });
    expect(screen.getByText("New Workbench session…")).toBeTruthy();
  });

  it("f: Clients, Audits and To-dos for 'granite'", async () => {
    await mount("f");
    await waitFor(() => {
      expect(groupLabels()).toEqual(["Clients", "Audits", "To-dos", "Actions"]);
    });
    expect(screen.getByText("New to-do on Granite Peak Outdoor Supply, Inc.…")).toBeTruthy();
  });

  it("error: the designed words when search is unavailable", async () => {
    await mount("error");
    await waitFor(() => {
      expect(screen.getByText(COPY.error)).toBeTruthy();
    });
  });

  it("⌘↵ opens in a new tab and keeps the palette open; ↵ opens here", async () => {
    const input = await mount("a");
    await waitFor(() => {
      expect(groupLabels()[0]).toBe("Clients");
    });
    fireEvent.keyDown(input, { key: "Enter", metaKey: true });
    expect(opened.at(-1)?.newTab).toBe(true);
    expect(screen.getByRole("combobox")).toBeTruthy();
    fireEvent.keyDown(input, { key: "Enter" });
    expect(opened.at(-1)?.newTab).toBe(false);
  });

  it("sends the search text only in the POST body", async () => {
    const seen: string[] = [];
    const spy = vi.spyOn(window, "fetch");
    await mount("a");
    await waitFor(() => {
      expect(groupLabels().length).toBeGreaterThan(0);
    });
    for (const call of spy.mock.calls)
      seen.push(String(call[0] instanceof Request ? call[0].url : call[0]));
    expect(seen.some((u) => u.includes("feld"))).toBe(false);
    spy.mockRestore();
  });
});
