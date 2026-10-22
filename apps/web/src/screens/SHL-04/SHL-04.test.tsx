// SHL-04 · Notifications panel v2 (P-01-T10). One test per artboard (a, b, b′, b_raj, c–g) on its
// fixture scenario, then the AC 3.1.x behaviours of the frame, the tabs and the day groups on the
// live drawer.
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { type JSX, useState } from "react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { type FixtureHandler, installFixtureMode } from "../../app-core/fixture-mode";
import { overlayEntry } from "../../app-core/overlays";
import {
  EMPTY_ALL,
  EMPTY_APPROVALS,
  OPEN_APPROVALS_QUEUE,
  R2_ROWS,
  RAJ_ROW,
  ROWS,
  SHOWING_DAYS,
} from "../../fixtures/seed/notifications";
import { NOTIFICATIONS } from "../../shell/firm/copy";
import {
  NOTIFICATIONS_OVERLAY,
  NotificationsDrawer,
  groupByDay,
} from "../../shell/firm/NotificationsDrawer";
import { firmDayGroup } from "../../shell/notifications";
import { newQueryClient } from "../../testing/support";
import { SHL04 } from ".";
import { type Shl04State, STATES, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

interface Seen {
  calls: { method: string; path: string; tab: string | null }[];
}

function install(state: Shl04State): Seen {
  const seen: Seen = { calls: [] };
  const base = scenarios[state];
  const handlers = Object.fromEntries(
    Object.entries(base.handlers).map(([key, handler]) => [
      key,
      ((request) => {
        seen.calls.push({
          method: request.method,
          path: request.path,
          tab: request.query.get("tab"),
        });
        return handler(request);
      }) satisfies FixtureHandler,
    ]),
  );
  restore = installFixtureMode({ ...base, handlers });
  return seen;
}

function show(state: Shl04State): Seen {
  const seen = install(state);
  render(
    <QueryClientProvider client={newQueryClient()}>
      <SHL04 state={state} />
    </QueryClientProvider>,
  );
  return seen;
}

function drawer(): HTMLElement {
  return screen.getByRole("complementary", { name: "Notifications" });
}

/** The rows once the feed has answered. */
async function rows(): Promise<HTMLElement[]> {
  await waitFor(() => {
    expect(drawer().querySelectorAll("[data-notification]").length).toBeGreaterThan(0);
  });
  return [...drawer().querySelectorAll<HTMLElement>("[data-notification]")];
}

function titles(list: HTMLElement[]): string[] {
  return list.map((r) => r.querySelector("button")?.firstChild?.textContent ?? "");
}

function groups(): string[] {
  return [...drawer().querySelectorAll("section h3")].map((h) => h.textContent);
}

function tabs(): string[] {
  return within(drawer())
    .getAllByRole("tab")
    .map((t) => t.textContent);
}

async function tabsCounted(): Promise<string[]> {
  await waitFor(() => {
    expect(tabs()).toContain("Approvals3");
  });
  return tabs();
}

const ALL_TITLES = ROWS.map((r) => r.title);

describe("SHL-04 artboards", () => {
  it("covers a, b, b′, b_raj and c–g", () => {
    expect(STATES).toEqual(["a", "b", "bp", "b_raj", "c", "d", "e", "f", "g"]);
  });

  it("SHL-04a default: the frame, the tabs with counts, Today and Friday, September 11, 4 unread", async () => {
    show("a");
    const list = await rows();
    expect(titles(list)).toEqual(ALL_TITLES);
    expect(groups()).toEqual(["Today", "Friday, September 11"]);
    expect(await tabsCounted()).toEqual(["All", "Approvals3", "Mentions1", "Client activity"]);
    expect(within(drawer()).getByRole("tab", { name: "All" }).getAttribute("aria-selected")).toBe(
      "true",
    );
    expect(drawer().querySelectorAll('[data-dot="unread"]')).toHaveLength(4);
    expect(within(drawer()).getAllByText("· Unread", { exact: false })).toHaveLength(4);
    expect([...drawer().querySelectorAll("time")].map((t) => t.textContent)).toEqual(
      ROWS.map((r) => r.timeLabel),
    );
    expect(within(drawer()).getByText("Blocked on a partner decision")).toBeTruthy();
    expect(within(drawer()).getByRole("button", { name: "Sign off…" })).toBeTruthy();
    expect(within(drawer()).getByRole("button", { name: "Mark all read" })).toBeTruthy();
    expect(within(drawer()).getByText(SHOWING_DAYS)).toBeTruthy();
    // The bell reads pressed while the drawer is open.
    expect(screen.getByRole("button", { name: /^Notifications/, pressed: true })).toBeTruthy();
  });

  it("SHL-04b Approvals: rows a, b and d, then Open approvals queue →", async () => {
    const seen = show("b");
    const list = await rows();
    expect(titles(list)).toEqual([ROWS[0]?.title, ROWS[1]?.title, ROWS[3]?.title]);
    expect(
      within(drawer())
        .getByRole("tab", { name: /Approvals/ })
        .getAttribute("aria-selected"),
    ).toBe("true");
    expect(within(drawer()).getByRole("button", { name: OPEN_APPROVALS_QUEUE })).toBeTruthy();
    expect(seen.calls.some((c) => c.tab === "approvals")).toBe(true);
  });

  it("SHL-04b′ Approvals with nothing waiting: the EmptyState", async () => {
    show("bp");
    expect(await within(drawer()).findByText(EMPTY_APPROVALS.title)).toBeTruthy();
    expect(within(drawer()).getByText(EMPTY_APPROVALS.body)).toBeTruthy();
    expect(drawer().querySelectorAll("[data-notification]")).toHaveLength(0);
  });

  it("SHL-04b Raj Malhotra: the Copperleaf AJE proposal, a deep link only", async () => {
    show("b_raj");
    const list = await rows();
    expect(titles(list)).toContain(RAJ_ROW.title);
    const raj = list.find((r) => r.dataset.kind === "proposal_routed") as HTMLElement;
    expect(within(raj).getAllByRole("button")).toHaveLength(1);
  });

  it("SHL-04c after Accept: row d reads its receipt and offers no action", async () => {
    show("c");
    const list = await rows();
    const d = list[3] as HTMLElement;
    expect(within(d).getByText("✓ Accepted by Hannah Leclerc · 9:42 AM")).toBeTruthy();
    expect(within(d).getAllByRole("button")).toHaveLength(1);
    expect(d.querySelector('[data-dot="unread"]')).toBeNull();
  });

  it("SHL-04d all read: no dots, Mark all read has nothing to do", async () => {
    show("d");
    await rows();
    expect(drawer().querySelectorAll('[data-dot="unread"]')).toHaveLength(0);
    await waitFor(() => {
      expect(
        within(drawer()).getByRole("button", { name: "Mark all read" }).hasAttribute("disabled"),
      ).toBe(true);
    });
  });

  it("SHL-04e empty: You're all caught up.", async () => {
    show("e");
    expect(await within(drawer()).findByText(EMPTY_ALL.title)).toBeTruthy();
    expect(within(drawer()).getByText(EMPTY_ALL.body)).toBeTruthy();
  });

  it("SHL-04f loading: five skeleton rows, aria-busy", () => {
    show("f");
    const busy = within(drawer()).getByRole("status", { name: NOTIFICATIONS.loading });
    expect(busy.getAttribute("aria-busy")).toBe("true");
    expect(busy.querySelectorAll('[data-row="list"]')).toHaveLength(5);
  });

  it("SHL-04g R2 kinds: the to-do, the template update, two trigger runs on Monday, September 28", async () => {
    show("g");
    const list = await rows();
    expect(titles(list)).toEqual(R2_ROWS.map((r) => r.title));
    expect(groups()).toEqual(["Today", "Monday, September 28"]);
    expect(within(drawer()).getByRole("button", { name: "Open to-do" })).toBeTruthy();
    expect(within(drawer()).getByRole("button", { name: "Review update…" })).toBeTruthy();
    for (const row of list.filter((r) => r.dataset.kind === "trigger_run_finished")) {
      expect(row.textContent).toContain("Auto-started by trigger ·");
    }
    // AC 3.1.8: a template update never applies from the drawer.
    expect(within(drawer()).queryByRole("button", { name: /^(Apply|Update)\b/ })).toBeNull();
  });
});

/** The live drawer as the `?ov=notifications` layer draws it. */
function Live({ navigate = () => undefined }: { navigate?: (to: string) => void }): JSX.Element {
  const [open, setOpen] = useState(true);
  return (
    <>
      <span data-open={String(open)} />
      <NotificationsDrawer open={open} onOpenChange={setOpen} navigate={navigate} />
    </>
  );
}

function live(state: Shl04State, navigate?: (to: string) => void): Seen {
  const seen = install(state);
  render(
    <QueryClientProvider client={newQueryClient()}>
      <Live {...(navigate === undefined ? {} : { navigate })} />
    </QueryClientProvider>,
  );
  return seen;
}

describe("SHL-04 behaviour (P-01 AC 3.1)", () => {
  it("AC 3.1.1: the drawer is the ?ov=notifications drawer layer", () => {
    expect(NOTIFICATIONS_OVERLAY).toBe("notifications");
    expect(overlayEntry("notifications")?.layer).toBe("drawer");
  });

  it("AC 3.1.1: opening marks nothing read; opening a row marks it read and deep-links", async () => {
    const navigate = vi.fn();
    const seen = live("a", navigate);
    const list = await rows();
    expect(seen.calls.some((c) => c.method === "POST")).toBe(false);
    const d = list[3] as HTMLElement;
    fireEvent.click(within(d).getAllByRole("button")[0] as HTMLElement);
    await waitFor(() => {
      expect(
        seen.calls.some(
          (c) => c.method === "POST" && c.path.endsWith(`/${d.dataset.notification ?? ""}/read`),
        ),
      ).toBe(true);
    });
    expect(navigate).toHaveBeenCalledWith(
      expect.stringMatching(/^\/engagements\/[^/]+\/requests$/),
    );
    expect(document.querySelector("[data-open]")?.getAttribute("data-open")).toBe("false");
  });

  it("AC 3.1.2: switching to Approvals asks the server for that tab", async () => {
    const seen = live("a");
    await tabsCounted();
    fireEvent.click(within(drawer()).getByRole("tab", { name: /Approvals/ }));
    await waitFor(() => {
      expect(titles([...drawer().querySelectorAll<HTMLElement>("[data-notification]")])).toEqual([
        ROWS[0]?.title,
        ROWS[1]?.title,
        ROWS[3]?.title,
      ]);
    });
    expect(
      seen.calls.some((c) => c.path === "/v1/notifications/feed" && c.tab === "approvals"),
    ).toBe(true);
  });

  it("AC 3.1.6: Mark all read clears every dot", async () => {
    const seen = live("a");
    await rows();
    await waitFor(() => {
      expect(
        within(drawer()).getByRole("button", { name: "Mark all read" }).hasAttribute("disabled"),
      ).toBe(false);
    });
    fireEvent.click(within(drawer()).getByRole("button", { name: "Mark all read" }));
    await waitFor(() => {
      expect(drawer().querySelectorAll('[data-dot="unread"]')).toHaveLength(0);
    });
    expect(
      seen.calls.some((c) => c.method === "POST" && c.path === "/v1/notifications/read-all"),
    ).toBe(true);
  });

  it("AC 3.1.9: agent-originated rows only deep-link, and their context is AgentText", async () => {
    live("a");
    const list = await rows();
    const agentKinds = new Set([
      "run_finished",
      "run_needs_input",
      "proposal_routed",
      "trigger_run_finished",
      "template_update_available",
    ]);
    const agentRows = list.filter((r) => agentKinds.has(r.dataset.kind ?? ""));
    expect(agentRows).toHaveLength(3);
    for (const row of agentRows) {
      expect(within(row).getAllByRole("button")).toHaveLength(1);
      expect(row.querySelector('[data-actor="agent"]')).not.toBeNull();
      expect(row.textContent).not.toMatch(/\b(Approve|Sign off|Release|Send|Post|Decide)\b/);
    }
  });

  it("the drawer's words are the handoff's (spec states 2, 5, footer)", () => {
    expect(NOTIFICATIONS.emptyAll).toEqual(EMPTY_ALL);
    expect(NOTIFICATIONS.emptyApprovals).toEqual(EMPTY_APPROVALS);
    expect(NOTIFICATIONS.showing).toBe(SHOWING_DAYS);
    expect(NOTIFICATIONS.openApprovals).toBe(OPEN_APPROVALS_QUEUE);
  });

  it("day groups follow the firm's calendar, not the device's", () => {
    const now = new Date("2026-09-14T14:41:00Z"); // 9:41 AM CT
    expect(firmDayGroup("2026-09-14T05:30:00Z", now, "America/Chicago")).toBe("Today");
    expect(firmDayGroup("2026-09-14T04:30:00Z", now, "America/Chicago")).toBe(
      "Sunday, September 13",
    );
    expect(firmDayGroup("2026-09-14T04:30:00Z", now, "America/New_York")).toBe("Today");
    // Consecutive rows of one day form one group, in the feed's order.
    expect(ROWS.map((r) => r.day)).toEqual([
      ...Array<string>(7).fill("Today"),
      ...Array<string>(2).fill("Friday, September 11"),
    ]);
    expect(groupByDay([], now, "America/Chicago")).toEqual([]);
  });
});
