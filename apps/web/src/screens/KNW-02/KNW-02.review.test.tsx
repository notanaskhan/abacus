// KNW-02 c, d and the draft review (K-01-T19; K-01 §3.6 AC6.1 to AC6.4). Acceptance: "KNW-02c and
// d pass Tier C, and Hannah's v4 draft opens in KNW-02 with the viewer empty state and a working
// diff against v3." Tier C is the visual suite's; here the tiles and rows the server computed,
// the struck-over-green changed rows, the standards rows and the default toggle's write, the
// Activity tab's named actors, Compare with, and the draft-review mode.
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { type JSX, useState } from "react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { type FixtureHandler, installFixtureMode } from "../../app-core/fixture-mode";
import { V2 } from "../../fixtures/handlers/methodology-versions";
import { newQueryClient } from "../../testing/support";
import { KNW02, type Knw02Search } from ".";
import { type Knw02State, OPENS, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

interface Call {
  method: string;
  path: string;
  body: unknown;
  query: string;
}

function Page({ state, initial }: { state: Knw02State; initial: Knw02Search }): JSX.Element {
  const [search, setSearch] = useState<Knw02Search>(initial);
  return <KNW02 versionId={OPENS[state].versionId} search={search} onSearch={setSearch} />;
}

function show(state: Knw02State, initial: Knw02Search = {}): Call[] {
  const calls: Call[] = [];
  const scenario = scenarios[state];
  const handlers = Object.fromEntries(
    Object.entries(scenario.handlers).map(([key, handler]) => [
      key,
      ((request) => {
        calls.push({
          method: request.method,
          path: request.path,
          body: request.body,
          query: request.query.toString(),
        });
        return handler(request);
      }) satisfies FixtureHandler,
    ]),
  );
  restore = installFixtureMode({ ...scenario, handlers });
  const opens = OPENS[state];
  render(
    <QueryClientProvider client={newQueryClient()}>
      <Page
        state={state}
        initial={{ ...(opens.tab === undefined ? {} : { tab: opens.tab }), ...initial }}
      />
    </QueryClientProvider>,
  );
  return calls;
}

describe("KNW-02 c · Diff vs v2", () => {
  it("tiles 4 · 9 · 1 · 54, the tab's count 14, and the row grammar", async () => {
    show("c");
    const diff = await waitFor(() => {
      const found = document.querySelector<HTMLElement>('[data-knw02="diff"]');
      if (found === null) throw new Error("no diff");
      return found;
    });
    const tiles: Record<string, string> = {};
    for (const t of diff.querySelectorAll("[data-tile]")) {
      tiles[t.getAttribute("data-tile") ?? ""] = t.textContent;
    }
    expect(tiles).toEqual({
      added: "Added4",
      changed: "Changed9",
      removed: "Removed1",
      unchanged: "Unchanged54",
    });
    expect(diff.textContent).toContain("v3 = 67 steps · v2 = 64 steps");
    expect(screen.getByRole("tab", { name: /Diff vs v2/u }).textContent).toContain("14");
    const rows = diff.querySelectorAll("[data-diff]");
    expect(rows).toHaveLength(14);
    expect(rows[0]?.textContent).toContain("New");
    expect(rows[0]?.textContent).toContain("110 · step 15");
    const changed = [...rows].find((r) => r.textContent.includes("110 · step 7"));
    expect(changed?.querySelector("del")?.textContent).toBe(
      "Materiality: total plan assets, 1.0%–2.0%; PM 60%–75%",
    );
    expect(changed?.querySelector("ins")?.textContent).toBe(
      "Materiality: net assets available for benefits, 1.0%–2.0%; PM 50%–75%; clearly trivial 5%",
    );
  });

  it("Compare with v2 diffs against the version picked", async () => {
    const calls = show("c");
    fireEvent.click(await screen.findByRole("button", { name: /Compare with v2/u }));
    fireEvent.click(await screen.findByRole("menuitemradio", { name: /Compare with v2/u }));
    await waitFor(() => {
      expect(calls.some((c) => c.path.endsWith("/diff") && c.query.includes(V2))).toBe(true);
    });
  });
});

describe("KNW-02 d · Standards mapping", () => {
  it("the set, QM reference, three EBP types and the default; the toggle writes at the row version seen", async () => {
    const calls = show("d");
    const panel = await waitFor(() => {
      const found = document.querySelector<HTMLElement>('[data-knw02="standards"]');
      if (found === null) throw new Error("no standards");
      return found;
    });
    expect(panel.textContent).toContain(
      "GAAS nonissuer · AU-C 703 · plan years ending on or after Dec 31, 2025",
    );
    expect(panel.textContent).toContain("SQMS 1 (effective Dec 15, 2025)");
    expect(panel.textContent).toContain("EBP DC §103(a)(3)(C) · EBP DC full scope · EBP DB");
    expect(panel.textContent).toContain("Yes · new EBP audits start on v3");
    expect(panel.textContent).toContain(
      "New EBP audits accepted on or after the effective date use this version and standards set. Engagements already in progress keep v2.",
    );
    fireEvent.click(within(panel).getByRole("switch", { name: "Default for new EBP audits" }));
    await waitFor(() => {
      expect(calls.some((c) => c.method === "PUT" && c.path.endsWith("/standards-mapping"))).toBe(
        true,
      );
    });
    const body = calls.find((c) => c.path.endsWith("/standards-mapping"))?.body as Record<
      string,
      unknown
    >;
    expect(body.default_for_new_engagements).toBe(false);
    expect(body.row_version).toBe(1);
    expect(body.engagement_types).toEqual(["ebp_dc_limited_scope", "ebp_dc_full_scope", "ebp_db"]);
  });
});

describe("KNW-02 Activity and draft review", () => {
  it("Activity names each actor", async () => {
    show("c", { tab: "activity" });
    const list = await screen.findByRole("list", { name: "Activity" });
    expect(list.textContent).toContain("Margaret Okonkwo imported this version");
    expect(list.textContent).toContain("Margaret Okonkwo mapped the standards");
  });

  it("Hannah's v4 draft: the program-editor empty state and a working diff against v3", async () => {
    show("draft");
    expect(
      await screen.findByText(
        "This version was edited in the program editor. There is no source document.",
      ),
    ).toBeTruthy();
    const tab = await screen.findByRole("tab", { name: /Diff vs v3/u });
    fireEvent.click(tab);
    const diff = await waitFor(() => {
      const found = document.querySelector<HTMLElement>('[data-knw02="diff"]');
      if (found === null) throw new Error("no diff");
      return found;
    });
    expect(diff.querySelectorAll("[data-diff]")).toHaveLength(2);
    expect(diff.textContent).toContain("v4 = 68 steps · v3 = 67 steps");
  });
});
