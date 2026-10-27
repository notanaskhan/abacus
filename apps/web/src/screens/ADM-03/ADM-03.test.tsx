// ADM-03 · Offices, teams, walls & offshore (G-01-T14). One test per artboard (a–h) on its fixture
// scenario (G-01 AC7.1–AC7.3, AC8.1–AC8.7, AC9.1–AC9.3, AC10.1–AC10.2, AC11.2) plus the writes
// (an office save with its version, the service-line save, a new wall, a partner's Lift), the
// walls step-up row and the not-allowed answer.
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
import { OfficesPage } from ".";
import { ASHFORD_CLIENT, LENA } from "../../fixtures/scenarios/ADM-03";
import { type Adm03State, OPENS, STATES, scenarios } from "./scenarios";

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
  state: Adm03State,
  initial: string = OPENS[state],
  extra: Record<string, FixtureHandler> = {},
): Call[] {
  const scenario: Scenario = scenarios[state];
  const calls: Call[] = [];
  const handlers = Object.fromEntries(
    Object.entries({ ...scenario.handlers, ...extra }).map(([key, handler]) => [
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
      <OfficesPage initial={initial} />
    </QueryClientProvider>,
  );
  return calls;
}

const fieldset = (title: string): HTMLElement => {
  const heading = screen.getByRole("heading", { name: title });
  const section = heading.closest("section");
  if (section === null) throw new Error(`no fieldset ${title}`);
  return section;
};
const wallRows = (): HTMLElement[] => [
  ...screen
    .getByRole("table", { name: "Ethical walls" })
    .querySelectorAll<HTMLElement>("tr[data-wall]"),
];
const wallRow = (person: string): HTMLElement => {
  const row = wallRows().find((r) => r.textContent.includes(person));
  if (row === undefined) throw new Error(`no wall on ${person}`);
  return row;
};

async function toasted(text: string): Promise<void> {
  await waitFor(() => {
    expect(toastStore.list().map((t) => t.text)).toContain(text);
  });
}

async function pick(trigger: HTMLElement, option: string): Promise<void> {
  trigger.focus();
  fireEvent.keyDown(trigger, { key: "ArrowDown" });
  fireEvent.click(await screen.findByRole("menuitemradio", { name: option }));
}

describe("ADM-03 artboards", () => {
  it("has a scenario for every artboard a–h with its persona and clock", () => {
    expect(STATES).toEqual(["a", "b", "c", "d", "e", "f", "g", "h"]);
    expect(scenarios.e.persona).toBe("daniel-reyes");
    for (const s of ["b", "f"] as const) {
      expect(scenarios[s].clock).toBe("2026-09-14T09:20:00-05:00");
    }
    for (const s of ["a", "c", "d", "g", "h"] as const) {
      expect(scenarios[s].persona).toBe("grace-holloway");
      expect(scenarios[s].clock).toBe("2026-09-14T09:24:00-05:00");
    }
  });

  it("ADM-03a: offices, teams 16 + 21 + 7 + 2, groups, service lines, three walls, offshore 0", async () => {
    show("a");
    expect(await screen.findByRole("button", { name: "Show or hide Chicago" })).toBeTruthy();
    expect(screen.getByText("Chicago · HQ")).toBeTruthy();
    expect(
      screen.getByRole("button", { name: "Show or hide Chicago" }).getAttribute("aria-expanded"),
    ).toBe("true");
    expect(
      screen.getByRole("button", { name: "Show or hide Denver" }).getAttribute("aria-expanded"),
    ).toBe("false");
    expect(
      screen.getByText("311 West Brannock Street, Suite 1700, Chicago, IL 60606"),
    ).toBeTruthy();
    const offices = fieldset("Offices");
    expect(
      within(offices).getByRole("button", { name: "Time zone: Central Time (CT)" }),
    ).toBeTruthy();
    expect(within(offices).getByText("Used in CCH Axcess office mapping (ADM-08).")).toBeTruthy();
    expect(within(offices).getByDisplayValue("CHI")).toBeTruthy();
    expect(await within(offices).findByText("Tax reviewers in Chicago (YK)")).toBeTruthy();
    expect(
      within(offices).getByRole("button", { name: "Office lead: Margaret Okonkwo" }),
    ).toBeTruthy();
    expect(within(offices).getByText("22 seats")).toBeTruthy();
    expect(within(offices).getByText("· 98 TY2025 returns")).toBeTruthy();
    expect(within(offices).getByText("14 seats")).toBeTruthy();
    expect(within(offices).getByText("10 seats")).toBeTruthy();
    expect(within(offices).getByText("46 seats · 224 returns")).toBeTruthy();

    const teams = fieldset("Teams & groups");
    expect(within(teams).getByText("16 + 21 + 7 + 2 = 46 seats")).toBeTruthy();
    expect(within(teams).getByText("Client accounting (CAS)")).toBeTruthy();
    expect(within(teams).getByText("Groups")).toBeTruthy();
    expect(within(teams).getByText("EQR pool")).toBeTruthy();
    expect(
      within(teams).getByText(
        "Eligible EQR reviewers; cannot be EQR on their own engagements (SQMS No. 2).",
      ),
    ).toBeTruthy();
    expect(within(teams).getByText("Objective inspectors for ADM-12.")).toBeTruthy();
    expect(within(teams).queryByText("Tax reviewers in Chicago")).toBeNull(); // pools aren't groups
    expect(await within(teams).findByText("Oct 31, 2026")).toBeTruthy();

    const lines = screen.getByRole("table", { name: "Service lines" });
    const audit = lines.querySelector<HTMLElement>('tr[data-line="audit"]');
    expect(audit?.textContent).toContain("Audit & assurance (incl. SOC & IT, internal audit)");
    expect(audit?.textContent).toContain("Engagement team only");
    expect(audit?.textContent).toContain("Hand-offs only (AUD-38)");
    expect(within(lines).getByRole("button", { name: "Tax: Service line" })).toBeTruthy();
    expect(
      within(lines).getByRole("button", { name: "Advisory: Engagement team only" }),
    ).toBeTruthy();
    expect(within(lines).queryByRole("button", { name: /Audit & assurance/ })).toBeNull(); // locked
    expect(screen.getByText(/Granite Peak Outdoor Supply, Inc\. — FY2026 audit/)).toBeTruthy();

    await waitFor(() => {
      expect(wallRows()).toHaveLength(3);
    });
    expect(wallRow("Lena Park").textContent).toContain("Ashford Manufacturing Co.");
    expect(wallRow("Lena Park").textContent).toContain(
      "Personal relationship (family member employed at Ashford)",
    );
    expect(wallRow("Lena Park").textContent).toContain("Today 9:20 AM by GH");
    expect(wallRow("Lena Park").textContent).toContain("Awaiting Margaret Okonkwo");
    expect(wallRow("Victor Hammond").textContent).toContain("Feb 3, 2026 by GH");
    expect(wallRow("Paige Sutton").textContent).toContain("Daniel Reyes");
    // DEC-43: the helper names no count; Grace holds no wall action.
    expect(
      screen.getByText(
        "Walled people cannot open, search, be assigned to, or run agents on these clients.",
      ),
    ).toBeTruthy();
    expect(screen.queryByText(/count in Go/)).toBeNull();
    expect(screen.queryByRole("button", { name: /^Lift the wall/ })).toBeNull();

    const offshore = fieldset("Offshore & restricted access (§7216)");
    expect(within(offshore).getByText("0 members")).toBeTruthy();
    const block = within(offshore).getByRole("switch", {
      name: "Block offshore assignment without consent",
    });
    expect(block.getAttribute("aria-checked")).toBe("true");
    expect((block as HTMLButtonElement).disabled).toBe(true);
    const mask = within(offshore).getByRole("switch", {
      name: "Mask TINs for restricted members",
    });
    expect((mask as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByRole<HTMLButtonElement>("button", { name: "Save" }).disabled).toBe(true);
  });

  it("ADM-03b: the new wall sheet with Lena Park ✕ Ashford, then Save asks Margaret to approve", async () => {
    const calls = show("b");
    expect(await screen.findByRole("dialog", { name: "New ethical wall" })).toBeTruthy();
    const sheet = screen.getByRole("dialog", { name: "New ethical wall" });
    expect(await within(sheet).findByRole("button", { name: "Person: Lena Park" })).toBeTruthy();
    expect(
      within(sheet).getByRole("button", { name: "Walled from: Ashford Manufacturing Co." }),
    ).toBeTruthy();
    expect(await within(sheet).findByText("Remove from 0 current assignments")).toBeTruthy();
    expect(within(sheet).getByText("Block agent runs she starts on this client")).toBeTruthy();
    fireEvent.change(within(sheet).getByRole("textbox", { name: "Details" }), {
      target: { value: "Family member employed at Ashford" },
    });
    await pick(
      within(sheet).getByRole("button", { name: /^Requires a partner/ }),
      "Margaret Okonkwo",
    );
    const save = within(sheet).getByRole("button", { name: "Save" });
    await waitFor(() => {
      expect((save as HTMLButtonElement).disabled).toBe(false);
    });
    fireEvent.click(save);
    await toasted("Wall added · approval requested from Margaret Okonkwo");
    const post = calls.find((c) => c.method === "POST" && c.path === "/v1/walls");
    expect(post?.body).toMatchObject({
      user_id: LENA,
      client_id: ASHFORD_CLIENT,
      reason_code: "personal_relationship",
      reason_text: "Family member employed at Ashford",
    });
    expect((post?.body as { approver_user_id?: string }).approver_user_id).toBeTruthy();
    await waitFor(() => {
      expect(screen.queryByRole("dialog", { name: "New ethical wall" })).toBeNull();
    });
  });

  it("ADM-03c: walling Neil Ashcroft from Ashford shows the red-ink row and Save stays off", async () => {
    show("c");
    const sheet = await screen.findByRole("dialog", { name: "New ethical wall" });
    expect(
      await within(sheet).findByText(
        "Neil Ashcroft leads this relationship. Reassign the relationship partner first.",
      ),
    ).toBeTruthy();
    expect(within(sheet).getByRole<HTMLButtonElement>("button", { name: "Save" }).disabled).toBe(
      true,
    );
  });

  it("ADM-03d: Remy Vidal in the offshore group: the banner (DEC-352) and 1 member", async () => {
    show("d");
    const banner = await screen.findByText(
      "Remy Vidal can't be assigned to a client until its offshore consent is signed. SSNs stay masked.",
    );
    expect(banner.getAttribute("role")).toBe("status");
    expect(screen.getByText("1 member")).toBeTruthy();
    expect(
      screen.getByText(/Members can be assigned only to clients with a valid §7216 consent/),
    ).toBeTruthy();
  });

  it("ADM-03e: Daniel Reyes manages service lines, adds walls and lifts others' walls; the rest is locked", async () => {
    const calls = show("e");
    // ADR-183 condition 4 (Ayush, 2026-10-26): partners manage service lines, so Daniel's form
    // is not read-only; offices, teams and offshore stay locked for him.
    const lines = await screen.findByRole("table", { name: "Service lines" });
    expect(await within(lines).findByRole("button", { name: "Tax: Service line" })).toBeTruthy();
    expect(screen.queryByText("Only firm admins can edit these settings.")).toBeNull();
    expect(screen.getByRole<HTMLButtonElement>("button", { name: "Save" }).disabled).toBe(true);
    expect(screen.queryByRole("button", { name: "Time zone: Central Time (CT)" })).toBeNull();
    expect(within(fieldset("Offices")).getByLabelText("Locked")).toBeTruthy();
    expect(await screen.findByRole("button", { name: "Wall" })).toBeTruthy();
    await waitFor(() => {
      expect(wallRows()).toHaveLength(3);
    });
    // Daniel names no awaiting wall, so no Approve; he lifts each wall not on himself.
    expect(screen.queryByRole("button", { name: /^Approve the wall/ })).toBeNull();
    expect(screen.getAllByRole("button", { name: /^Lift the wall/ })).toHaveLength(3);
    fireEvent.click(screen.getByRole("button", { name: "Lift the wall on Lena Park" }));
    const confirm = await screen.findByRole("alertdialog");
    fireEvent.click(within(confirm).getByRole("button", { name: "Lift" }));
    await toasted("Wall lifted");
    expect(calls.some((c) => c.method === "POST" && c.path.endsWith("/remove"))).toBe(true);
  });

  it("ADM-03f: the wall added at 9:20 AM is tinted, then not after two seconds", async () => {
    show("f");
    await waitFor(() => {
      expect(wallRow("Lena Park").getAttribute("data-tint")).toBe("on");
    });
    expect(wallRow("Victor Hammond").getAttribute("data-tint")).toBeNull();
    await waitFor(
      () => {
        expect(wallRow("Lena Park").getAttribute("data-tint")).toBeNull();
      },
      { timeout: 3500 },
    );
  });

  it("ADM-03g: a wall row opens its log in the ADM-07 grammar", async () => {
    show("g");
    const drawer = await screen.findByRole("dialog", { name: "Ethical wall" });
    expect(await within(drawer).findByText("Ethical wall added by Grace Holloway")).toBeTruthy();
    expect(within(drawer).getByText("Approved by Margaret Okonkwo")).toBeTruthy();
    expect(within(drawer).getByText("Family member employed at Ashford")).toBeTruthy();
    expect(within(drawer).getByText("Today 9:20 AM by Grace Holloway")).toBeTruthy();
  });

  it("ADM-03h: narrowing Tax shows the confirm row and Save sends the version read", async () => {
    const calls = show("h");
    const lines = await screen.findByRole("table", { name: "Service lines" });
    await pick(
      within(lines).getByRole("button", { name: "Tax: Service line" }),
      "Engagement team only",
    );
    expect(
      await screen.findByText(
        "Tax staff lose access to tax engagements they are not staffed on. Save to apply.",
      ),
    ).toBeTruthy();
    expect(screen.getByText("Unsaved changes")).toBeTruthy();
    const save = screen.getByRole("button", { name: "Save" });
    expect((save as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(save);
    await toasted("Firm settings saved");
    const put = calls.find((c) => c.method === "PUT" && c.path === "/v1/firm/service-lines/tax");
    expect(put?.body).toMatchObject({ version: 1, content_visible_to: "engagement_team_only" });
  });
});

describe("ADM-03 writes and edges", () => {
  it("an office change saves with its version (AC7.2)", async () => {
    const calls = show("a");
    const zone = await screen.findByRole("button", { name: "Time zone: Central Time (CT)" });
    await pick(zone, "Eastern Time (ET)");
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await toasted("Firm settings saved");
    const patch = calls.find(
      (c) => c.method === "PATCH" && c.path.startsWith("/v1/firm/offices/"),
    );
    expect(patch?.body).toMatchObject({ time_zone: "America/New_York", code: "CHI", version: 1 });
  });

  it("an office code that isn't 2–6 capitals blocks Save", async () => {
    show("a");
    const code = await screen.findByDisplayValue("CHI");
    fireEvent.change(code, { target: { value: "C1" } });
    expect(screen.getByRole<HTMLButtonElement>("button", { name: "Save" }).disabled).toBe(true);
  });

  it("a security admin reads the service lines locked (ADR-183 condition 4)", async () => {
    const base: FixtureHandler = scenarios.a.handlers["GET /v1/me/capabilities"];
    show("a", OPENS.a, {
      "GET /v1/me/capabilities": async (request) => {
        const answer = await Promise.resolve(base(request));
        const body = (await answer.json()) as { capabilities: string[] };
        return json({
          ...body,
          capabilities: body.capabilities.filter((c) => c !== "service_line_policy.manage"),
        });
      },
    });
    const lines = await screen.findByRole("table", { name: "Service lines" });
    await waitFor(() => {
      expect(within(lines).queryByRole("button")).toBeNull();
    });
  });

  it("walls without a fresh second factor show the step-up row and no count", async () => {
    show("a", OPENS.a, { "GET /v1/walls": () => json({ detail: "forbidden" }, 403) });
    expect(await screen.findByText("Confirm it's you to view walls")).toBeTruthy();
    expect(screen.queryByRole("table", { name: "Ethical walls" })).toBeNull();
  });

  it("collapsing Chicago and expanding Denver moves the expanded office", async () => {
    show("a");
    fireEvent.click(await screen.findByRole("button", { name: "Show or hide Denver" }));
    expect(
      await screen.findByText("1820 Coalbank Street, Suite 400, Denver, CO 80202"),
    ).toBeTruthy();
    expect(
      screen.queryByText("311 West Brannock Street, Suite 1700, Chicago, IL 60606"),
    ).toBeNull();
  });

  it("someone with no settings role sees the not-allowed answer", async () => {
    show("a", OPENS.a, {
      "GET /v1/firm/settings/overview": () => json({ detail: "not found" }, 404),
    });
    expect(await screen.findByText("You don't have access to firm settings.")).toBeTruthy();
  });
});

// G-01-T17 (DEC-594): the retired Walls screen's tests (legacy/spec019 "ac6 walls" and "ac7 …
// no walls"), carried here where ADM-03 has the behaviour; the rest map to ADM-03b, c, e and the
// step-up test above (SPEC table in DEC-594).
describe("ADM-03 carries the retired Walls tests (DEC-594)", () => {
  it("spec019 ac7: a firm with no walls reads empty", async () => {
    show("a", OPENS.a, { "GET /v1/walls": () => json([]) });
    expect(await screen.findByText("No ethical walls.")).toBeTruthy();
  });

  it("spec019 ac6: a lift the server refuses says so, and the wall stays", async () => {
    show("e", OPENS.e, {
      "POST /v1/walls/{wall_id}/remove": () => json({ detail: "own_wall" }, 409),
    });
    await waitFor(() => {
      expect(wallRows()).toHaveLength(3);
    });
    fireEvent.click(screen.getByRole("button", { name: "Lift the wall on Lena Park" }));
    const confirm = await screen.findByRole("alertdialog");
    fireEvent.click(within(confirm).getByRole("button", { name: "Lift" }));
    await toasted("Couldn't load this section. Try again.");
    expect(wallRows()).toHaveLength(3);
  });
});
