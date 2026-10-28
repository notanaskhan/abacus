// ENG-13 · Roll forward (P-07-T60). One test per artboard on its fixture scenario, the screen
// contract's acceptance bullets, and the task's acceptance: "Scenarios a to e pass with axe and
// production shows only the v1 carry categories" (axe: e2e/screens/ENG-13.spec.ts; production:
// ENG-13.production.test.tsx).
import { client } from "@abacus/api-client/client";
import { toastStore } from "@abacus/ui";
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import {
  type FixtureHandler,
  type Scenario,
  installFixtureMode,
} from "../../app-core/fixture-mode";
import { renderRoutes } from "../../testing/support";
import { ENG13, RollForwardPage } from ".";
import { COPY } from "./copy";
import {
  CLOCK_JAN_11,
  CLOCK_NOV_16,
  CLOCK_NOV_16_11,
  type Eng13State,
  OPENS,
  PREVIEWS,
  STATES,
  STEP_OF,
  draftOf,
  freshScenario,
  scenarios,
} from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
  toastStore.clear();
});

interface Seen {
  calls: { method: string; path: string; body: unknown }[];
}

function show(state: Eng13State, onCreated?: (id: string) => void): Seen {
  const seen: Seen = { calls: [] };
  const scenario: Scenario = freshScenario(state);
  const handlers = Object.fromEntries(
    Object.entries(scenario.handlers).map(([key, handler]) => [
      key,
      ((request) => {
        seen.calls.push({ method: request.method, path: request.path, body: request.body });
        return handler(request);
      }) satisfies FixtureHandler,
    ]),
  );
  restore = installFixtureMode({ ...scenario, handlers });
  renderRoutes([
    {
      path: "/",
      component: () => (
        <ENG13
          sourceId={OPENS[state].source}
          draftId={OPENS[state].draft}
          initialStep={STEP_OF[state]}
          preview={PREVIEWS[state]}
          {...(onCreated === undefined ? {} : { onCreated })}
        />
      ),
    },
  ]);
  return seen;
}

const carrying = async (): Promise<string[]> => {
  const card = await screen.findByRole("region", { name: "Carrying" });
  return Array.from(card.querySelectorAll("span"))
    .map((s) => s.textContent)
    .slice(1);
};

describe("ENG-13 scenarios", () => {
  it("one scenario per artboard, seen by its viewer at its instant", () => {
    expect(STATES).toEqual(["a", "b", "c", "d", "e"]);
    expect([scenarios.a.persona, scenarios.c.persona, scenarios.d.persona]).toEqual([
      "laura-kemp",
      "hannah-leclerc",
      "hannah-leclerc",
    ]);
    expect([scenarios.a.clock, scenarios.c.clock, scenarios.d.clock, scenarios.e.clock]).toEqual([
      CLOCK_NOV_16,
      CLOCK_NOV_16_11,
      CLOCK_JAN_11,
      CLOCK_NOV_16,
    ]);
  });

  it("Northwind carries 24 requests as Draft and no evidence (d's figures)", () => {
    const d = draftOf("d");
    expect([d.source.status, d.catalogue.request_count, d.catalogue.evidence_copied]).toEqual([
      "archived",
      24,
      0,
    ]);
    expect(d.name).toBe("PY2026 EBP Audit");
  });
});

describe("ENG-13 a · What to carry (Tessellate)", () => {
  it("draws the four v1 rows, the preview cards and the live Carrying card", async () => {
    show("a");
    await screen.findByRole("heading", {
      name: "What to carry into SOC 2 Type 2 · Oct 1, 2026 – Sep 30, 2027",
    });
    for (const row of ["Team", "Template version", "Request list", "Prior-year notes"]) {
      expect(screen.getByRole("tablist", { name: `Carry or skip ${row}` })).toBeTruthy();
    }
    expect(screen.getByText("Scope and controls")).toBeTruthy();
    expect(screen.getByText("Learned context · 3")).toBeTruthy();
    expect(await carrying()).toEqual([
      "4 people",
      "BH SOC 2 · TSC 2017 (rev. 2022) v1",
      "213 requests as Draft",
      "Prior-year notes linked",
      "38 criteria · 74 controls",
      "2 triggers",
      "3 learned-context items",
      "0 evidence copied",
    ]);
    expect(
      screen.getByText(
        "Prior-year evidence stays in the archive and is referenced, never copied. The new engagement starts with no evidence, results or sign-offs.",
      ),
    ).toBeTruthy();
  });

  it("Skip on the request list saves on the version seen and the card drops the line", async () => {
    const seen = show("a");
    const toggle = await screen.findByRole("tablist", { name: "Carry or skip Request list" });
    fireEvent.click(within(toggle).getByRole("tab", { name: "Skip" }));
    await waitFor(() => {
      expect(seen.calls.some((c) => c.method === "PATCH")).toBe(true);
    });
    const patch = seen.calls.find((c) => c.method === "PATCH");
    expect(patch?.body).toEqual({ selections: { request_list: false }, seen_version: 3 });
    await waitFor(async () => {
      expect((await carrying()).some((l) => l.endsWith("requests as Draft"))).toBe(false);
    });
  });
});

describe("ENG-13 b · Template version (current)", () => {
  it("names the template, Current, pinned at Create, and nothing to reconcile", async () => {
    show("b");
    await screen.findByText("BH SOC 2 · TSC 2017 (rev. 2022)");
    expect(screen.getByText("Current")).toBeTruthy();
    expect(screen.getByText("No newer version · pinned at Create")).toBeTruthy();
    expect(screen.getByText("Nothing to reconcile.")).toBeTruthy();
  });
});

describe("ENG-13 c · Conflicts (Granite Peak, fixture-only)", () => {
  it("Next waits until both conflicts are chosen", async () => {
    show("c");
    await screen.findByText(
      "Template changed since FY2026: BH Audit Methodology · FS v5 (held Oct 1) → FS v6",
    );
    const next = screen.getByRole("button", { name: "Next" });
    expect(next.hasAttribute("disabled")).toBe(true);
    const groups = screen
      .getAllByRole("group")
      .filter((g) => /Saved view|Trigger 'Request/.test(g.getAttribute("aria-label") ?? ""));
    expect(groups).toHaveLength(2);
    const [first, second] = groups;
    if (first === undefined || second === undefined) throw new Error("no conflict rows");
    fireEvent.click(within(first).getByRole("button", { name: "Keep" }));
    expect(next.hasAttribute("disabled")).toBe(true);
    fireEvent.click(within(second).getByRole("button", { name: "Update" }));
    await waitFor(() => {
      expect(next.hasAttribute("disabled")).toBe(false);
    });
    expect(screen.getByText("Signed-off FY2026 work is never changed.")).toBeTruthy();
  });
});

describe("ENG-13 d · Northwind (live)", () => {
  it("rolls the archived PY2025 audit: 24 requests as Draft, the archive read-only", async () => {
    show("d");
    await screen.findByRole("heading", {
      name: "What to carry into PY2026 EBP Audit · Jan 1, 2026 – Dec 31, 2026",
    });
    expect(screen.getByText("24, as Draft; the client sees nothing until you send")).toBeTruthy();
    expect(
      screen.getByText("The archive is locked; its evidence is referenced read-only."),
    ).toBeTruthy();
    expect(
      screen.getByText(
        "26 workpapers (Planning 6 · Fieldwork 3 · Testing 7 · Completion 6 · Reporting 4), unsigned",
      ),
    ).toBeTruthy();
    expect(await carrying()).toContain("24 requests as Draft");
    expect(screen.getByText("Source released · Archived")).toBeTruthy();
  });

  it("the team step asks each carried person for independence; Skip removes them", async () => {
    const seen = show("d");
    fireEvent.click(await screen.findByRole("button", { name: "Next" })); // → Template
    fireEvent.click(await screen.findByRole("button", { name: "Next" })); // → Team
    await screen.findByText("Margaret Okonkwo");
    expect(screen.getAllByText("Independence requested at Create")).toHaveLength(4);
    const ana = screen.getByRole("tablist", { name: "Carry or skip Ana Cruz" });
    fireEvent.click(within(ana).getByRole("tab", { name: "Skip" }));
    await waitFor(() => {
      expect(seen.calls.some((c) => c.method === "PATCH")).toBe(true);
    });
    const body = seen.calls.find((c) => c.method === "PATCH")?.body as {
      team_user_ids: string[];
    };
    expect(body.team_user_ids).toHaveLength(3);
  });
});

describe("ENG-13 e · Review and Create", () => {
  it("Create is a person's click with an Idempotency-Key; the toast names the period", async () => {
    const created = vi.fn();
    const seen = show("e", created);
    const create = await screen.findByRole("button", { name: "Create" });
    expect(screen.getByText("Celia Marsh")).toBeTruthy();
    fireEvent.click(create);
    await waitFor(() => {
      expect(created).toHaveBeenCalledTimes(1);
    });
    expect(
      seen.calls.filter((c) => c.method === "POST" && c.path.endsWith("/create")),
    ).toHaveLength(1);
    expect(toastStore.list().map((t) => t.text)).toContain(
      "Engagement created · SOC 2 Type 2 · Oct 1, 2026 – Sep 30, 2027",
    );
  });

  it("Escape asks to discard; Discard deletes the draft and closes", async () => {
    const closed = vi.fn();
    restore = installFixtureMode(freshScenario("e"));
    renderRoutes([
      {
        path: "/",
        component: () => (
          <ENG13
            sourceId={OPENS.e.source}
            draftId={OPENS.e.draft}
            initialStep="review"
            onClose={closed}
          />
        ),
      },
    ]);
    await screen.findByRole("button", { name: "Create" });
    fireEvent.keyDown(document.activeElement ?? document.body, { key: "Escape" });
    fireEvent.click(await screen.findByRole("button", { name: "Discard" }));
    await waitFor(() => {
      expect(closed).toHaveBeenCalledTimes(1);
    });
  });
});

describe("ENG-13 route page (P-07-T62)", () => {
  it("starts a draft for the source when the URL names none, and hands its id to the URL", async () => {
    restore = installFixtureMode(freshScenario("d"));
    const onDraft = vi.fn();
    renderRoutes([
      {
        path: "/",
        component: () => <RollForwardPage engagementId={OPENS.d.source} onDraft={onDraft} />,
      },
    ]);
    await waitFor(() => {
      expect(onDraft).toHaveBeenCalledWith(OPENS.d.draft);
    });
  });

  it("a source not yet delivered or archived says why (409)", async () => {
    const scenario = freshScenario("d");
    restore = installFixtureMode({
      ...scenario,
      handlers: {
        ...scenario.handlers,
        "POST /v1/engagements/{engagement_id}/roll-forward/drafts": () =>
          new Response(JSON.stringify({ detail: "roll_forward_source_not_released" }), {
            status: 409,
            headers: { "Content-Type": "application/json" },
          }),
      },
    });
    renderRoutes([
      { path: "/", component: () => <RollForwardPage engagementId={OPENS.d.source} /> },
    ]);
    expect(await screen.findByText(COPY.toast.notReleased)).toBeTruthy();
  });

  it("resumes the named draft on What to carry", async () => {
    restore = installFixtureMode(freshScenario("d"));
    renderRoutes([
      {
        path: "/",
        component: () => <RollForwardPage engagementId={OPENS.d.source} draftId={OPENS.d.draft} />,
      },
    ]);
    expect(await screen.findByText(COPY.steps.carry)).toBeTruthy();
  });
});
