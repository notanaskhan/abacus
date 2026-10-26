// ENG-05 · Team & roles (P-07-T39). One test per artboard a–e on its fixture scenario (inside the
// ENG-02 record on its Team tab), the contract's acceptance bullets, the writes (add with the G2
// dialog, portal flag, reminders, replace the EQR, remove), loading, error, the walled 404 and the
// role without the add right, and the task's acceptance: "Scenarios a to e pass with axe and hours
// foot to 172.0 and 24.0" (axe: e2e/screens/ENG-05.spec.ts; 24.0 is the seed's footing test,
// fixtures/team-roles.foot.test.ts, since actual hours show "—" until I-04).
import { client } from "@abacus/api-client/client";
import { toastStore } from "@abacus/ui";
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { type JSX, useState } from "react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import {
  type FixtureHandler,
  type Scenario,
  installFixtureMode,
  json,
  never,
} from "../../app-core/fixture-mode";
import type { TeamSeen } from "../../fixtures/handlers/team-roles";
import { renderRoutes } from "../../testing/support";
import { ENG02, type Eng02Tab } from "../ENG-02";
import type { Eng05Open } from ".";
import {
  type Eng05State,
  KIRA,
  OPENS,
  OVERLAYS,
  STATES,
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
  team: TeamSeen;
}

function install(scenario: Scenario, team: TeamSeen, over: Record<string, FixtureHandler>): Seen {
  const seen: Seen = { calls: [], team };
  const handlers = Object.fromEntries(
    Object.entries({ ...scenario.handlers, ...over }).map(([key, handler]) => [
      key,
      ((request) => {
        seen.calls.push({ method: request.method, path: request.path, body: request.body });
        return handler(request);
      }) satisfies FixtureHandler,
    ]),
  );
  restore = installFixtureMode({ ...scenario, handlers });
  return seen;
}

function Harness({
  engagementId,
  opens,
}: {
  engagementId: string;
  opens?: Eng05Open | undefined;
}): JSX.Element {
  const [tab, setTab] = useState<Eng02Tab>("team");
  return <ENG02 engagementId={engagementId} tab={tab} onTab={setTab} teamOpen={opens} />;
}

function show(
  state: Eng05State,
  over: Record<string, FixtureHandler> = {},
  options: { overlay?: boolean } = {},
): Seen {
  const team: TeamSeen = { reminders: [] };
  const seen = install(freshScenario(state, team), team, over);
  const opens = options.overlay === false ? undefined : OVERLAYS[state];
  renderRoutes([
    { path: "/", component: () => <Harness engagementId={OPENS[state]} opens={opens} /> },
  ]);
  return seen;
}

function rows(): HTMLElement[] {
  return [...document.querySelectorAll<HTMLElement>("[data-screen='ENG-05'] tr[data-row]")];
}

function rowOf(name: string): HTMLElement {
  const found = rows().find((r) => r.querySelector("[data-name]")?.textContent === name);
  if (found === undefined) throw new Error(`no row ${name}`);
  return found;
}

function cell(row: HTMLElement, i: number): string {
  return row.querySelectorAll("td")[i]?.textContent ?? "";
}

const COL = { person: 0, role: 1, budget: 2, actual: 3, independence: 4, portal: 5 } as const;

async function loaded(count: number): Promise<void> {
  await waitFor(() => {
    expect(rows()).toHaveLength(count);
  });
}

function totals(): string {
  return document.querySelector("[data-totals]")?.textContent ?? "";
}

function inspector(): HTMLElement {
  const el = document.querySelector<HTMLElement>("[data-inspector]");
  if (el === null) throw new Error("no inspector");
  return el;
}

describe("ENG-05 artboards", () => {
  it("defines a–e: Hannah Leclerc at E0 except b (Fri Sep 11) and c (Laura Kemp)", () => {
    expect(STATES).toEqual(["a", "b", "c", "d", "e"]);
    for (const s of STATES) {
      expect(scenarios[s].persona).toBe(s === "c" ? "laura-kemp" : "hannah-leclerc");
      expect(scenarios[s].clock).toBe(
        s === "b" ? "2026-09-11T09:24:00-05:00" : "2026-09-14T09:24:00-05:00",
      );
    }
    expect(OPENS.c).not.toBe(OPENS.a);
    expect(OPENS.e).not.toBe(OPENS.a);
  });

  it("ENG-05a default: five confirmed, Kira Ross proposed Sep 11 and pending, the EQR inspector", async () => {
    show("a");
    await loaded(6);
    expect(screen.getByRole("tab", { name: /^Team/ }).getAttribute("aria-selected")).toBe("true");
    expect(rows().map((r) => r.querySelector("[data-name]")?.textContent)).toEqual([
      "Margaret Okonkwo",
      "Thomas Whitcombe",
      "Hannah Leclerc",
      "Marcus Delaney",
      "Ana Cruz",
      "Kira Ross",
    ]);
    expect(cell(rowOf("Kira Ross"), COL.person)).toContain("added Sep 11");
    expect(rows().map((r) => cell(r, COL.role))).toEqual([
      "Engagement partner (EP)",
      "EQR reviewer",
      "Manager",
      "Senior (in-charge)",
      "Staff",
      "Staff (proposed)",
    ]);
    expect(rows().map((r) => cell(r, COL.budget))).toEqual([
      "10.0",
      "6.0",
      "37.0",
      "61.0",
      "40.0",
      "18.0",
    ]);
    expect(cell(rowOf("Margaret Okonkwo"), COL.independence)).toContain("Confirmed");
    expect(cell(rowOf("Kira Ross"), COL.independence)).toBe("Pending · requested Sep 11");
    expect(within(rowOf("Kira Ross")).getByRole("button", { name: "Remind" })).toBeTruthy();
    expect(document.querySelector("[data-banner='g2']")?.textContent).toBe(
      "G2 Independent: 5 of 5 assigned members confirmed. Kira Ross is pending — they can’t be assigned or sign off until they confirm.",
    );
    expect(totals()).toContain("6 people");
    expect(totals()).toContain("172.0");
    expect(totals()).toContain("5 of 6 confirmed");
    expect(totals()).toContain("3 shown");
    expect(document.querySelector("[data-footer='approval']")?.textContent).toBe(
      "Team approved by Margaret Okonkwo (EP) · Jun 1, 2026 · changes since: + Kira Ross (Sep 11, awaiting approval)",
    );
    const ins = inspector();
    await waitFor(() => {
      expect(within(ins).getAllByRole("listitem")).toHaveLength(5);
    });
    expect(within(ins).getByText("Thomas Whitcombe")).toBeTruthy();
    expect(within(ins).getByText("Eligible")).toBeTruthy();
    expect(
      within(ins)
        .getAllByRole("listitem")
        .map((li) => li.textContent),
    ).toEqual([
      expect.stringContaining("Not a member of the engagement team"),
      expect.stringContaining(
        "No cooling-off conflict — not EP on Northwind in the prior two years",
      ),
      expect.stringContaining("EBP audit competence — 3 EBP EQRs in 2025"),
      expect.stringContaining("Independence confirmed"),
      expect.stringContaining("Capacity"),
    ]);
    expect(
      within(ins).getByText("The EP cannot approve the EQR on her own engagement."),
    ).toBeTruthy();
    expect(within(ins).getByRole("button", { name: "Replace EQR…" })).toBeTruthy();
  });

  it("ENG-05b blocked assignment: Kira Ross opens the G2 dialog; Send confirmation request adds her", async () => {
    const seen = show("b");
    const dialog = await screen.findByRole("dialog", { name: "Assignment pending independence" });
    expect(dialog.textContent).toContain(
      "Kira Ross hasn’t confirmed independence for Northwind Robotics 401(k) Plan. They can view the engagement but can’t be assigned work or sign off.",
    );
    expect(dialog.textContent).toContain("Staff (proposed)");
    await loaded(5);
    expect(document.querySelector("[data-banner='g2']")).toBeNull();
    fireEvent.click(within(dialog).getByRole("button", { name: "Send confirmation request" }));
    await loaded(6);
    const post = seen.calls.find((c) => c.method === "POST" && c.path.endsWith("/team"));
    expect(post?.body).toEqual({ user_id: KIRA, role: "staff" });
    expect(cell(rowOf("Kira Ross"), COL.independence)).toBe("Pending · requested Sep 11");
    await waitFor(() => {
      expect(toastStore.list()[0]?.text).toBe("Confirmation request sent to Kira Ross");
    });
  });

  it("ENG-05c cooling-off: Thomas Whitcombe is not eligible as Fairhaven's EQR and Assign stays off", async () => {
    show("c");
    const dialog = await screen.findByRole("dialog", { name: "Replace EQR reviewer" });
    await waitFor(() => {
      expect(dialog.querySelectorAll("[data-candidate]")).toHaveLength(2);
    });
    const tw = dialog.querySelector<HTMLElement>("[data-candidate='Thomas Whitcombe']");
    const cm = dialog.querySelector<HTMLElement>("[data-candidate='Celia Marsh']");
    expect(tw?.textContent).toContain(
      "Not eligible — EP on this plan for PY2024 (cooling-off, 2 years)",
    );
    expect(cm?.textContent).toContain("Eligible");
    expect(cm?.textContent).toContain("Current EQR");
    expect(
      within(dialog).getByText(
        "SQMS 2 requires a two-year cooling-off before a former engagement partner can serve as EQR.",
      ),
    ).toBeTruthy();
    expect(
      within(dialog).getByRole<HTMLButtonElement>("button", { name: "Assign" }).disabled,
    ).toBe(true);
  });

  it("ENG-05d confirmed: Kira's row reads Confirmed in ink and the banner is gone", async () => {
    show("d");
    await loaded(6);
    expect(cell(rowOf("Kira Ross"), COL.independence)).toContain("Confirmed");
    expect(document.querySelector("[data-banner='g2']")).toBeNull();
    expect(totals()).toContain("6 of 6 confirmed");
    expect(within(rowOf("Kira Ross")).queryByRole("button", { name: "Remind" })).toBeNull();
  });

  it("ENG-05e empty: No team yet. and Add the engagement partner offers the partners", async () => {
    show("e");
    expect(await screen.findByText("No team yet.")).toBeTruthy();
    const add = screen.getByRole("button", { name: "Add the engagement partner" });
    add.focus();
    fireEvent.keyDown(add, { key: "ArrowDown" });
    const menu = await screen.findByRole("menu");
    expect(
      within(menu)
        .getAllByRole("menuitem")
        .map((m) => m.textContent),
    ).toEqual(["Margaret Okonkwo", "Thomas Whitcombe", "Celia Marsh"]);
    expect(document.querySelector("[data-totals]")).toBeNull();
  });
});

describe("ENG-05 acceptance", () => {
  it("ENG-05 acceptance: budget hours foot to 172.0; actuals show — until I-04 and the agent's minutes stay out", async () => {
    show("a");
    await loaded(6);
    expect(document.querySelector("[data-total='budget']")?.textContent).toBe("172.0");
    expect(document.querySelector("[data-total='actual']")?.textContent).toBe("—");
    const agent = document.querySelector<HTMLElement>("[data-agent-row]");
    expect(agent?.textContent).toContain(
      "Acts with the invoking user’s permissions · never signs off",
    );
    expect(agent?.textContent).not.toMatch(/minute/);
  });

  it("ENG-05 acceptance: Kira Ross can view the engagement but cannot be assigned or sign off until she confirms", async () => {
    show("a");
    await loaded(6);
    expect(document.querySelector("[data-banner='g2']")?.textContent).toContain(
      "Kira Ross is pending — they can’t be assigned or sign off until they confirm.",
    );
    // The engagement itself is not blocked: the record and its tabs stay usable.
    expect(screen.getByRole("tab", { name: /^Overview/ })).toBeTruthy();
  });

  it("ENG-05 acceptance: no agent-owned control offers Approve, Sign off, Release, Send, Post or Decide", async () => {
    show("a");
    await loaded(6);
    const agent = document.querySelector<HTMLElement>("[data-agent-row]");
    expect(agent).not.toBeNull();
    expect(agent?.querySelectorAll("button")).toHaveLength(0);
    fireEvent.click(agent as HTMLElement);
    const ins = inspector();
    expect(within(ins).getByText("Never signs off")).toBeTruthy();
    expect(ins.textContent).not.toMatch(/\b(Approve|Sign off|Release|Send|Post|Decide)\b/);
  });
});

describe("ENG-05 writes", () => {
  it("the portal toggle PUTs the flag; a pending person's toggle is disabled", async () => {
    const seen = show("a");
    await loaded(6);
    const kira = within(rowOf("Kira Ross")).getByRole<HTMLButtonElement>("switch");
    expect(kira.disabled).toBe(true);
    fireEvent.click(within(rowOf("Ana Cruz")).getByRole("switch"));
    await waitFor(() => {
      expect(toastStore.list()[0]?.text).toBe("Ana Cruz shown on the client’s team card (POR-02)");
    });
    const put = seen.calls.find((c) => c.path.endsWith("/portal-visibility"));
    expect(put?.body).toEqual({ shown_on_portal: true });
    await waitFor(() => {
      expect(totals()).toContain("4 shown");
    });
  });

  it("Request confirmations… sends to the pending people", async () => {
    const seen = show("a");
    await loaded(6);
    fireEvent.click(screen.getByRole("button", { name: "Request confirmations…" }));
    const sheet = await screen.findByRole("dialog", { name: "Request confirmations" });
    expect(sheet.textContent).toContain("Staff (proposed) · requested Sep 11");
    expect(sheet.textContent).toContain(
      "Each person confirms independence for Northwind Robotics 401(k) Plan in their Inbox.",
    );
    fireEvent.click(within(sheet).getByRole("button", { name: "Send" }));
    await waitFor(() => {
      expect(toastStore.list()[0]?.text).toBe("Confirmation request sent to Kira Ross");
    });
    expect(seen.team.reminders).toEqual([KIRA]);
  });

  it("Remind on a pending row sends one reminder and turns to Reminded", async () => {
    const seen = show("a");
    await loaded(6);
    fireEvent.click(within(rowOf("Kira Ross")).getByRole("button", { name: "Remind" }));
    await waitFor(() => {
      expect(toastStore.list()[0]?.text).toBe("Reminder sent to Kira Ross · Inbox");
    });
    expect(seen.team.reminders).toEqual([KIRA]);
    expect(
      within(rowOf("Kira Ross")).getByRole<HTMLButtonElement>("button", { name: "Reminded" })
        .disabled,
    ).toBe(true);
  });

  it("Remove from team… confirms, then DELETEs the member", async () => {
    const seen = show("a");
    await loaded(6);
    const trigger = within(rowOf("Ana Cruz")).getByRole("button", { name: "Ana Cruz actions" });
    trigger.focus();
    fireEvent.keyDown(trigger, { key: "ArrowDown" });
    fireEvent.click(await screen.findByRole("menuitem", { name: "Remove from team…" }));
    const confirm = await screen.findByRole("alertdialog");
    fireEvent.click(within(confirm).getByRole("button", { name: "Remove" }));
    await loaded(5);
    expect(seen.calls.some((c) => c.method === "DELETE")).toBe(true);
  });

  it("a row click inspects that person: role, budget and the portal flag", async () => {
    show("a");
    await loaded(6);
    fireEvent.click(rowOf("Marcus Delaney"));
    const ins = inspector();
    await waitFor(() => {
      expect(within(ins).getByText("Marcus Delaney")).toBeTruthy();
    });
    expect(ins.textContent).toContain("Senior (in-charge)");
    expect(ins.textContent).toContain("61.0 h");
  });
});

describe("ENG-05 states", () => {
  it("loading draws the skeleton", () => {
    show("a", { "GET /v1/engagements/{engagement_id}/team": () => never() });
    return waitFor(() => {
      expect(screen.getAllByRole("status", { name: /Loading/ }).length).toBeGreaterThan(0);
    });
  });

  it("the error state retries", async () => {
    show("a", { "GET /v1/engagements/{engagement_id}/team": () => json({}, 500) });
    expect(await screen.findByRole("button", { name: "Retry" })).toBeTruthy();
  });

  it("a walled engagement's team answers 404 and nothing about why is shown (INV-3)", async () => {
    show("a", {
      "GET /v1/engagements/{engagement_id}/team": () => json({ detail: "not_found" }, 404),
    });
    await waitFor(() => {
      expect(document.querySelector("[data-screen='ENG-05']")).not.toBeNull();
    });
    expect(rows()).toHaveLength(0);
    expect(screen.queryByText("Kira Ross")).toBeNull();
  });

  it("without engagement.member_add the add controls are hidden", async () => {
    show("a", {
      "GET /v1/engagements/{engagement_id}/record": async (request) => {
        const base = freshScenario("a").handlers["GET /v1/engagements/{engagement_id}/record"];
        const answer = await (base as FixtureHandler)(request);
        const body = (await answer.json()) as { allowed_actions: string[] };
        return json({ ...body, allowed_actions: ["engagement.read_metadata", "engagement.read"] });
      },
    });
    await loaded(6);
    expect(screen.queryByRole("button", { name: "Add person" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Request confirmations…" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Replace EQR…" })).toBeNull();
  });
});
