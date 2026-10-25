// AUD-02 · Audit cockpit (A-01-T12). One test per artboard this task builds (a–e, g) on its
// fixture scenario, the acceptance checklist (11 of 24 = 3 + 4 + 3 + 1; sub-lines exactly; the
// agent never decides), A-01 Stories 2.1–2.3 (no Run, Begin…, Sign off run or Auto mode control
// without its capability; the Viewer tab on a document row; DF-04; "Pause agent" → "Paused by …"),
// the 404 and the AVOID list. f is A-01-T31's, h A-09's, i K-04's.
import type { ActivityOut, AuditCockpitOut } from "@abacus/api-client";
import { client } from "@abacus/api-client/client";
import { toastStore } from "@abacus/ui";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import {
  type FixtureHandler,
  type Scenario,
  installFixtureMode,
  json,
} from "../../app-core/fixture-mode";
import type { JSX } from "react";
import { auditRoute } from "../../routes/firm/audits";
import { newQueryClient, renderRoutes } from "../../testing/support";
import { AuditCockpitPage } from ".";
import { AUDIT_ID, type Aud02State, OPENS, STATES, scenarios } from "./scenarios";

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
  calls: { method: string; path: string; query: string }[];
}

function install(scenario: Scenario): Seen {
  const seen: Seen = { calls: [] };
  const handlers = Object.fromEntries(
    Object.entries(scenario.handlers).map(([key, handler]) => [
      key,
      ((request) => {
        seen.calls.push({
          method: request.method,
          path: request.path,
          query: request.query.toString(),
        });
        return handler(request);
      }) satisfies FixtureHandler,
    ]),
  );
  restore = installFixtureMode({ ...scenario, handlers });
  return seen;
}

function show(
  state: Aud02State,
  scenario: Scenario = scenarios[state],
  auditId: string = AUDIT_ID,
): Seen {
  const seen = install(scenario);
  render(
    <QueryClientProvider client={newQueryClient()}>
      <AuditCockpitPage auditId={auditId} initial={OPENS[state]} />
    </QueryClientProvider>,
  );
  return seen;
}

/** A scenario whose cockpit read is rewritten. */
function withCockpit(
  state: Aud02State,
  edit: (c: AuditCockpitOut) => AuditCockpitOut,
  extra: Record<string, FixtureHandler> = {},
): Scenario {
  const base = scenarios[state];
  const read = base.handlers["GET /v1/audits/{work_item_id}/cockpit"];
  return {
    ...base,
    handlers: {
      ...base.handlers,
      "GET /v1/audits/{work_item_id}/cockpit": async (request) => {
        const answer = await read?.(request);
        if (answer === undefined) return json({}, 500);
        return json(edit((await answer.json()) as AuditCockpitOut));
      },
      ...extra,
    },
  };
}

const phaseText = (id: string): string =>
  document.querySelector(`[data-phase="${id}"]`)?.textContent ?? "";

async function ready(): Promise<void> {
  await screen.findByText("PY2025 Employee Benefit Plan Audit");
  await waitFor(() => {
    expect(document.querySelectorAll('[data-source-docs="row"]').length).toBe(24);
  });
}

function bands(): string[] {
  return [...document.querySelectorAll<HTMLElement>('[data-source-docs="group"] > button')].map(
    (b) => b.textContent,
  );
}

function canvasRows(): HTMLElement[] {
  return [...document.querySelectorAll<HTMLElement>('[data-source-docs="row"]')];
}

const PHASES = [
  "trial_balance",
  "materiality",
  "risk_assessment",
  "general_audit_planning",
  "internal_control",
  "service_organizations",
  "sample_selection",
  "testing",
];

describe("AUD-02 artboards", () => {
  it("has a scenario for a–e and g, all Hannah Leclerc at the state labels' times", () => {
    expect(STATES).toEqual(["a", "b", "c", "d", "e", "g"]);
    const clocks = Object.fromEntries(STATES.map((s) => [s, scenarios[s].clock]));
    expect(clocks).toEqual({
      a: "2026-09-14T09:41:00-05:00",
      b: "2026-09-14T09:20:00-05:00",
      c: "2026-09-14T09:23:00-05:00",
      d: "2026-09-14T09:41:00-05:00",
      e: "2026-09-14T09:58:00-05:00",
      g: "2026-09-14T09:41:00-05:00",
    });
    for (const s of STATES) expect(scenarios[s].persona).toBe("hannah-leclerc");
  });

  it("AUD-02a run: the sub-lines read exactly, the pill Processing, Started 9:24 AM, Begin… on Testing", async () => {
    show("a");
    await ready();
    expect(phaseText("trial_balance")).toContain("Complete · 9:26 AM");
    expect(phaseText("materiality")).toContain("Blocked on a partner decision");
    expect(phaseText("risk_assessment")).toContain("Running");
    expect(phaseText("general_audit_planning")).toContain("Waiting on inputs");
    expect(phaseText("internal_control")).toContain("Waiting on inputs");
    expect(phaseText("service_organizations")).toContain("Queued");
    expect(phaseText("sample_selection")).toContain("Waiting on inputs");
    expect(phaseText("testing")).toContain("Not started");
    expect(screen.getByText("Processing")).toBeTruthy();
    expect(screen.getByText("Started 9:24 AM")).toBeTruthy();
    expect(screen.getByRole("button", { name: /Begin/ })).toBeTruthy();
  });

  it("AUD-02b no run: every phase Not started, pill Planning, the bar and overview card", async () => {
    show("b");
    await ready();
    for (const id of PHASES) expect(phaseText(id)).toContain("Not started");
    // The band and the overview pill.
    expect(screen.getAllByText("Planning").length).toBe(2);
    expect(screen.queryByText("Processing")).toBeNull();
    // The bar chip and the Overview band's Methodology row.
    expect(screen.getAllByText("BH Audit Methodology · EBP v3").length).toBe(2);
    expect(screen.getByText("All Audits")).toBeTruthy();
    expect(screen.getAllByText("Northwind Robotics 401(k) Plan").length).toBeGreaterThan(0);
    expect(screen.getByText("PY2025 · Northwind Robotics, Inc.")).toBeTruthy();
    expect(screen.getByText("11 of 24 received")).toBeTruthy();
    expect(screen.getByText("MO · TW · HL · MD · AC")).toBeTruthy();
    expect(screen.getByText("GAAS nonissuer · AU-C 703")).toBeTruthy();
    expect(screen.queryByText("Started 9:24 AM")).toBeNull();
  });

  it("AUD-02c plan proposed: the rail is still Not started and the pill Planning", async () => {
    show("c");
    await ready();
    for (const id of PHASES) expect(phaseText(id)).toContain("Not started");
    expect(screen.queryByText("Processing")).toBeNull();
  });

  it("AUD-02d Materiality selected: Waiting on Margaret Okonkwo, reserved to the engagement partner", async () => {
    show("d");
    expect(await screen.findByText("Waiting on Margaret Okonkwo")).toBeTruthy();
    expect(
      screen.getByText("Planning materiality is reserved to the engagement partner."),
    ).toBeTruthy();
    const open = screen.getByRole("button", { name: "Open decision" });
    expect(open.hasAttribute("disabled")).toBe(true);
    expect(open.getAttribute("aria-description")).toBe("Not built yet");
  });

  it("AUD-02e failed step: Internal Control reads Failed — see run", async () => {
    show("e");
    await ready();
    expect(phaseText("internal_control")).toContain("Failed — see run");
    expect(phaseText("risk_assessment")).toContain("Running");
  });

  it("AUD-02g audit-program grammar: Ready and In progress pills replace the sub-lines", async () => {
    show("g");
    await ready();
    expect(phaseText("trial_balance")).toContain("Ready");
    expect(phaseText("materiality")).toContain("In progress");
    expect(phaseText("trial_balance")).not.toContain("Complete");
    expect(screen.getAllByText("Planning").length).toBe(2);
    expect(screen.queryByText("Processing")).toBeNull();
  });

  it("loading: the cockpit read never answers", () => {
    show("b", {
      ...scenarios.b,
      handlers: {
        ...scenarios.b.handlers,
        "GET /v1/audits/{work_item_id}/cockpit": () => new Promise<Response>(() => undefined),
      },
    });
    expect(document.querySelector("[data-screen='AUD-02']")).toBeTruthy();
    expect(screen.queryByText("PY2025 Employee Benefit Plan Audit")).toBeNull();
  });

  it("not found: a work item outside the tenant, behind a wall or not assurance is a 404 with no hint", async () => {
    show("b", scenarios.b, "00000000-0000-4000-8000-000000000000");
    await waitFor(() => {
      expect(document.querySelector("[data-screen='AUD-02']")?.textContent).not.toBe("");
    });
    expect(screen.queryByText("PY2025 Employee Benefit Plan Audit")).toBeNull();
    expect(screen.queryByText(/Northwind/)).toBeNull();
  });
});

describe("AUD-02 acceptance", () => {
  it("AUD-02 acceptance: 11 of 24 received equals the Received ✓ pills (3 + 4 + 3 + 1); the groups sum to 24", async () => {
    show("b");
    await ready();
    expect(bands()).toEqual([
      "Plan documents3 of 5",
      "Trust / Recordkeeper Reports4 of 6",
      "Census & Payroll3 of 7",
      "Form 5500 & SOC 11 of 4",
      "Cash0 of 1",
      "Compliance & other0 of 1",
    ]);
    const received = canvasRows().filter((r) => r.dataset.status === "received");
    expect(received.length).toBe(11);
    expect(canvasRows().filter((r) => r.dataset.status === "review").length).toBe(1);
    expect(canvasRows().filter((r) => r.dataset.status === "requested").length).toBe(12);
    const harborline = canvasRows().find((r) =>
      r.textContent.includes("Summary of net trust assets"),
    );
    expect(harborline?.textContent).toContain(
      "initial-input/Harborline Net Trust Assets 12-31-2025.pdf",
    );
  });

  it("AUD-02 acceptance: Missing first orders needs review, requested, received; the toggle asks the server", async () => {
    const seen = show("b");
    await ready();
    const trust = (): string[] =>
      [
        ...document.querySelectorAll<HTMLElement>(
          '[data-source-docs="group"][aria-label="Trust / Recordkeeper Reports"] [data-source-docs="row"]',
        ),
      ].map((r) => r.dataset.status ?? "");
    expect(trust()).toEqual([
      "review",
      "requested",
      "received",
      "received",
      "received",
      "received",
    ]);
    fireEvent.click(screen.getByRole("button", { name: "Missing first" }));
    await waitFor(() => {
      expect(trust()[0]).toBe("received");
    });
    expect(seen.calls.some((c) => c.query.includes("sort=received_first"))).toBe(true);
  });

  it("AUD-02 acceptance: the agent never decides: Margaret Okonkwo is named as the decider", async () => {
    show("d");
    await screen.findByText("Waiting on Margaret Okonkwo");
    expect(
      /\b(I approved|I decided|approved by Accrued Agent|Auto sign-off)\b/u.test(
        document.body.textContent,
      ),
    ).toBe(false);
  });

  it("A-01 Story 2.1: no Run, Begin…, Sign off run or Auto mode control without its capability", async () => {
    show("b");
    await ready();
    expect(screen.queryByRole("button", { name: /^Run$/ })).toBeNull();
    expect(screen.queryByRole("button", { name: /Begin/ })).toBeNull();
    expect(screen.queryByText("Sign off run")).toBeNull();
    expect(screen.queryByText("Auto mode")).toBeNull();
    expect(screen.queryByRole("button", { name: "Agent actions" })).toBeNull();
  });

  it("A-01 Story 2.1: a document row switches the dock to Viewer on its file", async () => {
    const seen = show("b");
    await ready();
    const row = canvasRows().find((r) => r.textContent.includes("Summary of net trust assets"));
    if (row === undefined) throw new Error("no Harborline row");
    fireEvent.click(row);
    await waitFor(() => {
      expect(document.querySelector("[data-audit-dock='viewer']")).toBeTruthy();
    });
    expect(document.querySelector("[data-audit-viewer]")).toBeTruthy();
    await waitFor(() => {
      expect(seen.calls.some((c) => /\/v1\/evidence-versions\/[^/]+\/viewer$/u.test(c.path))).toBe(
        true,
      );
    });
    expect(row.getAttribute("aria-current")).toBe("true");
  });

  it("A-01 Story 2.1 (DF-04): the Agent tab says AI isn't available when the data boundary refuses", async () => {
    const refused: ActivityOut[] = [
      {
        id: "0b0e5b42-0b8f-4d52-9a4e-3d1b8f1c00a1",
        action: "upload_review.start",
        created_at: "2026-09-14T14:20:00.000Z",
        item_count: null,
        outcome: "failed",
        policy: "upload_review",
        policy_version: 1,
        reason: "data_boundary",
        record_id: null,
        record_type: null,
      },
    ];
    show("b", {
      ...scenarios.b,
      handlers: {
        ...scenarios.b.handlers,
        "GET /v1/engagements/{engagement_id}/activity": () => json(refused),
      },
    });
    expect(await screen.findByText("AI isn't available for real client data yet")).toBeTruthy();
  });

  it("A-01 Story 2.3: Pause agent in the dock header menu runs as Hannah and reads Paused by Hannah Leclerc", async () => {
    const seen = show(
      "b",
      withCockpit("b", (c) => ({ ...c, allowed_actions: ["agent.pause"] })),
    );
    await ready();
    expect(await screen.findByText("Nothing yet")).toBeTruthy();
    const trigger = screen.getByRole("button", { name: "Agent actions" });
    trigger.focus();
    fireEvent.keyDown(trigger, { key: "ArrowDown" });
    const menu = screen.getByRole("menu");
    fireEvent.click(within(menu).getByRole("menuitem", { name: "Pause agent" }));
    expect(await screen.findByText("Paused by Hannah Leclerc")).toBeTruthy();
    expect(seen.calls.some((c) => c.method === "POST" && c.path.endsWith("/agent/pause"))).toBe(
      true,
    );
  });
});

describe("AUD-02 route /audits/$auditId", () => {
  it("the rail row lives in the URL: ?section=materiality opens the blocked card", async () => {
    install(scenarios.d);
    const Page = auditRoute.options.component as () => JSX.Element;
    renderRoutes([{ path: "/audits/$auditId", component: Page }], {
      at: `/audits/${AUDIT_ID}?section=materiality`,
    });
    expect(await screen.findByText("Waiting on Margaret Okonkwo")).toBeTruthy();
  });
});

describe("AUD-02 avoid", () => {
  it("AUD-02 avoid: coloured row backgrounds for status, 600/700 weights, the banned words, task for a to-do", async () => {
    show("a");
    await ready();
    const html = document.body.innerHTML;
    for (const row of canvasRows()) {
      expect(/bg-(green|amber|red)/u.test(row.className)).toBe(false);
    }
    expect(/font-(semibold|bold)/u.test(html)).toBe(false);
    expect(/\b(Accrual|Arc|ACME|LSA|Living Robotics)\b/u.test(document.body.textContent)).toBe(
      false,
    );
    expect(/\btasks?\b/iu.test(document.body.textContent)).toBe(false);
    // No Group band on a non-group engagement (R2).
    expect(screen.queryByText("Group")).toBeNull();
  });
});
