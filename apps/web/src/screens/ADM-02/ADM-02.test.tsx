// ADM-02 · Users & roles (G-01-T10). One test per artboard (a–g) on its fixture scenario
// (G-01 AC3.1–AC3.4, AC4.1–AC4.6, AC5.1–AC5.4, AC6.3) plus the writes: the role change with its
// confirm, deactivation, the offshore refusal, the Office filter and the not-allowed answer.
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
import { newQueryClient } from "../../testing/support";
import { PeoplePage } from ".";
import { type Adm02State, OPENS, STATES, scenarios } from "./scenarios";

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

interface Call {
  method: string;
  path: string;
  body: unknown;
}

function show(
  state: Adm02State,
  initial: string = OPENS[state],
  scenario: Scenario = scenarios[state],
) {
  const calls: Call[] = [];
  const handlers = Object.fromEntries(
    Object.entries(scenario.handlers).map(([key, handler]) => [
      key,
      ((request) => {
        calls.push({ method: request.method, path: request.path, body: request.body });
        return handler(request);
      }) satisfies FixtureHandler,
    ]),
  );
  restore = installFixtureMode({ ...scenario, handlers });
  render(
    <QueryClientProvider client={newQueryClient()}>
      <PeoplePage initial={initial} />
    </QueryClientProvider>,
  );
  return calls;
}

const table = (): HTMLElement => screen.getByRole("table", { name: "People" });
const rowOf = (name: string): HTMLElement => {
  const row = table().querySelector<HTMLElement>(`tr[data-person="${name}"]`);
  if (row === null) throw new Error(`no row ${name}`);
  return row;
};
const band = (key: string): HTMLElement => {
  const el = table().querySelector<HTMLElement>(`tbody[data-band="${key}"]`);
  if (el === null) throw new Error(`no band ${key}`);
  return el;
};
const peopleRows = (): number => table().querySelectorAll("tr[data-person]").length;

describe("ADM-02 artboards", () => {
  it("has a scenario for every artboard a–g with its persona and clock", () => {
    expect(STATES).toEqual(["a", "b", "c", "d", "e", "f", "g"]);
    expect(scenarios.g.persona).toBe("margaret-okonkwo");
    expect(scenarios.e.clock).toBe("2026-11-02T09:24:00-06:00");
    expect(scenarios.f.clock).toBe("2026-01-05T10:12:00-06:00");
    for (const s of ["a", "b", "c", "d"] as const) {
      expect(scenarios[s].clock).toBe("2026-09-14T09:24:00-05:00");
    }
  });

  it("ADM-02a users: 46 rows in six bands, the tallies, wall tags on VH, LP and PS only", async () => {
    show("a");
    expect(await screen.findByText("46 of 46")).toBeTruthy();
    expect(screen.getByText("Full")).toBeTruthy();
    expect(screen.getByText("7 partners · 37 professionals · 2 operations")).toBeTruthy();
    expect(screen.getByText("SSO + MFA 46 of 46")).toBeTruthy();
    expect(screen.getByText("3 active")).toBeTruthy();
    expect(screen.getByText("5 · access ends Oct 31")).toBeTruthy();
    expect(await screen.findByText("46 people")).toBeTruthy();
    expect(peopleRows()).toBe(46);
    const sizes = ["partners", "managers", "seniors", "staff", "seasonal", "operations"].map(
      (b) => band(b).querySelectorAll("tr[data-person]").length,
    );
    expect(sizes).toEqual([7, 7, 11, 14, 5, 2]);
    expect(within(band("partners")).getByText("PARTNERS")).toBeTruthy();
    expect(within(band("managers")).getByText("MANAGERS & REVIEWERS")).toBeTruthy();
    const margaret = rowOf("Margaret Okonkwo");
    expect(within(margaret).getByText("margaret.okonkwo@brightwaterhale.com")).toBeTruthy();
    expect(within(margaret).getByText("Partner")).toBeTruthy();
    expect(within(margaret).getByText("Chicago")).toBeTruthy();
    expect(within(margaret).getByText("Audit & assurance")).toBeTruthy();
    expect(within(margaret).getByText("Today 9:10 AM")).toBeTruthy();
    expect(within(rowOf("Thomas Whitcombe")).getByText("Fri Sep 11")).toBeTruthy();
    expect(
      within(rowOf("Thomas Whitcombe")).getByText("· EQR pool · Monitoring reviewers"),
    ).toBeTruthy();
    await waitFor(() => {
      expect(screen.getAllByText("Wall 1")).toHaveLength(3);
    });
    for (const name of ["Victor Hammond", "Lena Park", "Paige Sutton"]) {
      expect(within(rowOf(name)).getByText("Wall 1")).toBeTruthy();
    }
    // Segments: Users 46 · Role templates 8 · Invitations 0.
    const tabs = screen.getByRole("tablist", { name: "People" });
    expect(within(tabs).getByRole("tab", { name: /Users/ }).textContent).toContain("46");
    expect(within(tabs).getByRole("tab", { name: /Invitations/ }).textContent).toContain("0");
  });

  it("ADM-02a filters: Office = Denver lists 14 people (AC3.1)", async () => {
    const calls = show("a");
    expect(await screen.findByText("46 people")).toBeTruthy();
    const chip = screen.getByRole("button", { name: "Office: All offices" });
    chip.focus();
    fireEvent.keyDown(chip, { key: "ArrowDown" });
    fireEvent.click(await screen.findByRole("menuitemradio", { name: "Denver" }));
    expect(await screen.findByText("14 people")).toBeTruthy();
    expect(peopleRows()).toBe(14);
    // The chip turns amber once set.
    const set = screen.getByRole("button", { name: "Office: Denver" });
    expect(set.getAttribute("data-active")).toBe("true");
    expect(calls.some((c) => c.path === "/v1/firm/staff" && c.method === "GET")).toBe(true);
  });

  it("ADM-02a search: 'park' finds Lena Park only (AC3.2)", async () => {
    show("a", "?q=park");
    expect(await screen.findByText("1 person")).toBeTruthy();
    expect(rowOf("Lena Park")).toBeTruthy();
  });

  it("ADM-02b role templates: counts foot to 46, 16 rows, Partner highlighted, the agent locked", async () => {
    show("b");
    const grid = await screen.findByRole("table", { name: "Capabilities by role template" });
    expect(grid.querySelectorAll("tr[data-capability-row]")).toHaveLength(16);
    const highlighted = grid.querySelectorAll("th[data-highlight]");
    expect([...highlighted].map((h) => h.textContent)).toEqual(["Partner"]);
    const list = screen.getByRole("navigation", { name: "Role templates" });
    const counts = within(list)
      .getAllByRole("button")
      .map((b) => b.textContent);
    expect(counts.slice(0, 8).map((t) => Number(/(\d+)$/.exec(t)?.[1]))).toEqual([
      7, 4, 6, 8, 8, 11, 1, 1,
    ]);
    expect(within(list).getByText("Sign-off L4, release, final approval")).toBeTruthy();
    expect(
      screen.getByText(
        "Default policy from 01 §2.4. Firms may only make it stricter. Hard limits are locked.",
      ),
    ).toBeTruthy();
    // Text alternatives: Tax Reviewer exports "after approval", Partner releases "EP only".
    expect(within(grid).getAllByRole("img", { name: "Allowed: after approval" })).toHaveLength(1);
    expect(within(grid).getAllByRole("img", { name: "Allowed: EP only" })).toHaveLength(1);
    expect(within(grid).getAllByRole("img", { name: "Draft or propose only" }).length).toBe(3);
    // The agent is a locked row, never a column, and says what it never does (AC5.3).
    expect(within(grid).queryByRole("columnheader", { name: /Agent/ })).toBeNull();
    fireEvent.click(within(list).getByRole("button", { name: /Accrued Agent/ }));
    expect(
      await screen.findByText(
        "Accrued Agent — Draft · Test · Propose · Chase within the invoking user's scope. Never approves, signs off, releases, sends final, posts or exports.",
      ),
    ).toBeTruthy();
    expect(within(grid).queryAllByText("Partner").length).toBe(1);
  });

  it("ADM-02b: a ◐ names its condition (AC5.4)", async () => {
    show("b");
    const grid = await screen.findByRole("table", { name: "Capabilities by role template" });
    expect(
      within(grid).getByRole("button", { name: "Allowed with a condition: staff work only" }),
    ).toBeTruthy();
    expect(
      within(grid).getByRole("button", {
        name: "Allowed with a condition: if delegated (BH-TAX-02)",
      }),
    ).toBeTruthy();
  });

  it("ADM-02c invite with every seat held: the banner and Send invite off (AC3.3)", async () => {
    show("c");
    expect(
      await screen.findByText("All 46 seats are assigned. Add seats or deactivate a user first."),
    ).toBeTruthy();
    const dialog = screen.getByRole("dialog", { name: "Invite user" });
    expect(within(dialog).getByText("Person")).toBeTruthy();
    expect(within(dialog).getByText("Offshore / restricted")).toBeTruthy();
    expect(
      within(dialog).getByText(
        "Members are assigned only to clients with a valid §7216 offshore consent; SSNs masked.",
      ),
    ).toBeTruthy();
    fireEvent.change(within(dialog).getByPlaceholderText("First and last name"), {
      target: { value: "Lena Park" },
    });
    fireEvent.change(within(dialog).getByPlaceholderText("name@example.com"), {
      target: { value: "lena.park@brightwaterhale.com" },
    });
    const send = within(dialog).getByRole<HTMLButtonElement>("button", { name: "Send invite" });
    expect(send.disabled).toBe(true);
  });

  it("ADM-02d Lena Park: access, the Ashford wall, assignments and sign-ins (AC4.1)", async () => {
    show("d");
    const dialog = await screen.findByRole("dialog", { name: "Lena Park" });
    expect(await within(dialog).findByText("Tax Preparer · seasonal")).toBeTruthy();
    expect(within(dialog).getByText("Denver")).toBeTruthy();
    expect(within(dialog).getByText("Oct 31, 2026")).toBeTruthy();
    expect(within(dialog).getByText("lena.park@brightwaterhale.com")).toBeTruthy();
    expect(
      await within(dialog).findByText("Ashford Manufacturing Co. (added today 9:20 AM)"),
    ).toBeTruthy();
    expect(within(dialog).getByText("3 assignments")).toBeTruthy();
    expect(
      within(dialog).getByText("Today 8:18 AM · Microsoft SSO · MFA · 198.51.100.62"),
    ).toBeTruthy();
    expect(
      within(dialog).getByText("Fri Sep 11, 4:40 PM · Microsoft SSO · MFA · 198.51.100.62"),
    ).toBeTruthy();
    expect(within(dialog).getByRole("button", { name: "Change role…" })).toBeTruthy();
    expect(within(dialog).getByRole("button", { name: "Deactivate…" })).toBeTruthy();
    const offshore = within(dialog).getByRole("switch", { name: "Offshore / restricted" });
    expect(offshore.getAttribute("aria-checked")).toBe("false");
  });

  it("ADM-02d offshore over assignments is refused, and says so (AC4.6)", async () => {
    const calls = show("d");
    const dialog = await screen.findByRole("dialog", { name: "Lena Park" });
    fireEvent.click(await within(dialog).findByRole("switch", { name: "Offshore / restricted" }));
    await waitFor(() => {
      expect(calls.some((c) => c.method === "PATCH")).toBe(true);
    });
    expect(calls.find((c) => c.method === "PATCH")?.body).toEqual({ version: 1, offshore: true });
    await waitFor(() => {
      expect(toastStore.list().map((t) => t.text)).toContain(
        "Offshore can't be turned on while they're assigned to clients without an offshore consent.",
      );
    });
  });

  it("changes a role after a confirm, with the template and its level (AC4.2)", async () => {
    const calls = show("a", "?q=osei");
    fireEvent.click(await screen.findByRole("button", { name: "Open Kevin Osei" }));
    const dialog = await screen.findByRole("dialog", { name: "Kevin Osei" });
    const trigger = await within(dialog).findByRole("button", { name: "Change role…" });
    trigger.focus();
    fireEvent.keyDown(trigger, { key: "ArrowDown" });
    fireEvent.click(await screen.findByRole("menuitemradio", { name: "Senior" }));
    expect(await screen.findByText("Change Kevin Osei's role to Senior?")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Change role" }));
    await waitFor(() => {
      expect(toastStore.list().map((t) => t.text)).toContain("Role changed");
    });
    const put = calls.find((c) => c.method === "PUT");
    expect(put?.path).toMatch(/^\/v1\/firm\/staff\/[^/]+\/role$/);
    expect(put?.body).toEqual({ role_template: "senior", level: "senior" });
  });

  it("deactivates after a confirm (AC4.4)", async () => {
    const calls = show("a", "?q=osei");
    fireEvent.click(await screen.findByRole("button", { name: "Open Kevin Osei" }));
    const dialog = await screen.findByRole("dialog", { name: "Kevin Osei" });
    fireEvent.click(await within(dialog).findByRole("button", { name: "Deactivate…" }));
    expect(await screen.findByText("Deactivate Kevin Osei?")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Deactivate" }));
    await waitFor(() => {
      expect(toastStore.list().map((t) => t.text)).toContain("Deactivated");
    });
    const post = calls.find((c) => c.method === "POST" && c.path.endsWith("/deactivate"));
    expect(post?.body).toEqual({ reason: "manual" });
  });

  it("ADM-02e after season: five rows Deactivated Oct 31, 41 of 46", async () => {
    show("e");
    expect(await screen.findByText("41 of 46")).toBeTruthy();
    expect(screen.queryByText("Full")).toBeNull();
    expect(screen.getByText("7 partners · 32 professionals · 2 operations")).toBeTruthy();
    expect(screen.getByText("SSO + MFA 41 of 41")).toBeTruthy();
    expect(screen.getByText("5 · access ended Oct 31")).toBeTruthy();
    await waitFor(() => {
      expect(within(band("seasonal")).getAllByText("Deactivated Oct 31")).toHaveLength(5);
    });
    expect(peopleRows()).toBe(46);
  });

  it("ADM-02f pending invite: Lena Park, expires Jan 19, 46 of 46 · 1 pending (AC3.4)", async () => {
    show("f");
    expect(await screen.findByText("46 of 46 · 1 pending")).toBeTruthy();
    const lena = await waitFor(() => rowOf("Lena Park"));
    expect(within(lena).getByText("Invite pending · expires Jan 19")).toBeTruthy();
    expect(within(lena).getAllByText("—").length).toBeGreaterThanOrEqual(2);
    expect(peopleRows()).toBe(46);
    const tabs = screen.getByRole("tablist", { name: "People" });
    const invitations = within(tabs).getByRole("tab", { name: /Invitations/ });
    expect(invitations.textContent).toContain("1");
    fireEvent.click(invitations);
    expect(await screen.findByText("1 person")).toBeTruthy();
    expect(peopleRows()).toBe(1);
  });

  it("ADM-02g independence: Margaret sees every seat holder's status; counts foot (AC6.3)", async () => {
    show("g");
    expect(await screen.findByText("Independence · 2026")).toBeTruthy();
    expect(screen.getByText("0 confirmed · 46 not yet · 0 declined")).toBeTruthy();
    const rows = await screen.findByRole("table", { name: "Annual independence confirmations" });
    await waitFor(() => {
      expect(rows.querySelector('tr[data-person="Kevin Osei"]')).not.toBeNull();
    });
    expect(rows.querySelectorAll("tbody tr")).toHaveLength(46);
    expect(within(rows).getAllByText("Not yet")).toHaveLength(46);
    // DEC-286: a partner doesn't read the people list, so Users and Invitations are absent.
    const tabs = screen.getByRole("tablist", { name: "People" });
    expect(
      within(tabs)
        .getAllByRole("tab")
        .map((t) => t.textContent.replace(/\d+$/, "")),
    ).toEqual(["Role templates", "Independence"]);
    expect(screen.queryByRole("button", { name: "Invite user…" })).toBeNull();
  });

  it("answers not-allowed to someone without a settings role", async () => {
    const base = scenarios.a;
    show("a", "", {
      ...base,
      persona: "kevin-osei",
      handlers: {
        ...base.handlers,
        "GET /v1/firm/settings/overview": () => json({ detail: "not found" }, 404),
      },
    });
    expect(await screen.findByText("You don't have access to firm settings.")).toBeTruthy();
  });
});
