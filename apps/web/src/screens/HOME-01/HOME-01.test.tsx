// HOME-01 · Home dashboard, main region (I-01-T05, T06). Every artboard and spec-only state
// renders from its fixture scenario; a, f and g are the acceptance: the badge, the header and the
// summary read one counts call, and no row renders a gate verb. Axe runs in e2e/screens (skipped
// in this lane, recorded in TASK-1428).
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import {
  type FixtureHandler,
  type Scenario,
  installFixtureMode,
} from "../../app-core/fixture-mode";
import { homeSegmentOptions } from "../../domain/home";
import { RUNNING_POLL_MS } from "../../domain/home/queries";
import { newQueryClient } from "../../testing/support";
import { HOME01 } from ".";
import { type Home01State, OFFICE, STATES, scenarios } from "./scenarios";

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
  calls: string[];
}

function show(state: Home01State, scenario: Scenario = scenarios[state]): Seen {
  const seen: Seen = { calls: [] };
  const handlers = Object.fromEntries(
    Object.entries(scenario.handlers).map(([key, handler]) => [
      key,
      ((request) => {
        seen.calls.push(`${request.method} ${request.path}`);
        return handler(request);
      }) satisfies FixtureHandler,
    ]),
  );
  restore = installFixtureMode({ ...scenario, handlers });
  render(
    <QueryClientProvider client={newQueryClient()}>
      <HOME01 initialOffice={OFFICE[state] ?? null} />
    </QueryClientProvider>,
  );
  return seen;
}

async function settled(): Promise<void> {
  await screen.findByText(/Good (morning|afternoon)/u);
  await waitFor(() => {
    expect(document.querySelector("[data-dashboard='loading']")).toBeNull();
  });
}

function pane(): HTMLElement {
  const title = screen.getAllByText("Waiting on you")[0];
  const section = title?.closest<HTMLElement>("section[data-shell='pane']");
  if (section == null) throw new Error("no Waiting on you pane");
  return section;
}

function summary(): string {
  return document.querySelector("[data-home='summary']")?.textContent ?? "";
}

function approvalsTab(): HTMLElement {
  return screen.getByRole("tab", { name: /Approvals/u });
}

function bandCounts(): Record<string, number> {
  const out: Record<string, number> = {};
  for (const h of document.querySelectorAll<HTMLElement>("[data-band-header]")) {
    out[h.dataset.bandHeader ?? ""] = Number(h.querySelector("span:last-child")?.textContent);
  }
  return out;
}

const GATE_VERBS = /\b(Approve|Sign off|Release|Send|Post|Decide)\b/u;

describe("HOME-01 a (Daniel Reyes at E0)", () => {
  it("reads 11 = 3 + 6 + 2 in the header, the summary and the Approvals badge, from one counts call", async () => {
    const seen = show("a");
    await settled();
    await waitFor(() => {
      expect(summary()).toBe(
        "3 decisions · 6 sign-offs · 2 approvals & sends · sorted by deadline",
      );
    });
    expect(screen.getByText("Good morning, Daniel")).toBeTruthy();
    expect(screen.getByText("Monday, September 14")).toBeTruthy();
    expect(approvalsTab().textContent).toContain("11");
    expect(pane().firstElementChild?.textContent).toContain("11");
    expect(bandCounts()).toEqual({ decisions: 3, sign_offs: 6, approvals_sends: 2 });
    expect(seen.calls.filter((c) => c === "GET /v1/human-gates/counts")).toHaveLength(1);
    expect(document.querySelectorAll("[data-gate]")).toHaveLength(11);
  });

  it("renders no gate verb on any control, and no row is a button", async () => {
    show("a");
    await settled();
    await waitFor(() => {
      expect(document.querySelectorAll("[data-gate]")).toHaveLength(11);
    });
    for (const control of within(pane()).queryAllByRole("button")) {
      expect(control.textContent).not.toMatch(GATE_VERBS);
    }
    for (const row of document.querySelectorAll("[data-gate]")) {
      expect(row.querySelector("button")).toBeNull();
    }
  });

  it("draws the tiles that foot: 17 · 15 · 11 · 7, audits 27, closes 11 of 22, notices 9 with 2 New", async () => {
    show("a");
    await settled();
    const single = [...document.querySelectorAll<HTMLElement>("[data-tile='single']")].map((t) =>
      t.getAttribute("aria-label"),
    );
    expect(single).toEqual(["17 Prepared", "15 In review", "11 Issues", "7 Ready"]);
    expect(screen.getByRole("region", { name: "Audits & assurance · 27" })).toBeTruthy();
    expect(screen.getByText("of 22 · August 2026")).toBeTruthy();
    expect(screen.getByText("2 New")).toBeTruthy();
    expect(screen.getByText("Tax returns · TY2025 · 79 open")).toBeTruthy();
    expect(screen.getByText("3 running")).toBeTruthy();
  });

  it("states the due tier in words: Sep 15 · 1 day red-tint, Sep 23 · 9 days amber", async () => {
    show("a");
    await settled();
    await waitFor(() => {
      expect(screen.getAllByText("Sep 15 · 1 day").length).toBeGreaterThan(0);
    });
    const soon = screen.getAllByText("Sep 15 · 1 day")[0];
    expect(soon?.closest("[data-risk]")?.getAttribute("data-risk")).toBe("due_soon");
    expect(
      screen.getByText("Sep 23 · 9 days").closest("[data-risk]")?.getAttribute("data-risk"),
    ).toBe("approaching");
  });

  it("marks a blocked row in words, not colour alone", async () => {
    show("a");
    await settled();
    await waitFor(() => {
      expect(screen.getAllByText("Blocked:").length).toBe(2);
    });
  });
});

describe("HOME-01 a client activity (DEC-1001)", () => {
  it("draws the six rows of a, verbatim, newest first, with today's times and earlier dates", async () => {
    show("a");
    await settled();
    const list = await waitFor(() => {
      const found = document.querySelector<HTMLElement>("[data-home='activity']");
      expect(found).not.toBeNull();
      return found as HTMLElement;
    });
    const text = list.textContent;
    const rows: [string, string, string][] = [
      ["9:12 AM", "Claire Feld emailed 2 health insurance forms", "Waiting to be filed · Inbox"],
      [
        "8:40 AM",
        'You sent the engagement letter "Ridgeline cost segregation & §754 analysis" to Owen Calder',
        "Envelope · due Sep 24",
      ],
      ["Sep 11", 'Dana Whitley emailed "Re: estimated payments"', "Filed to 2025 Binder"],
      [
        "Sep 11",
        "Accrued Agent pre-screened the Estate of Walter Thornbury",
        "3 flags · awaiting your decision",
      ],
      [
        "Sep 9",
        "Paul Thornbury uploaded the asset summary",
        "New engagement intake · Estate of Walter Thornbury",
      ],
      [
        "Sep 9",
        "Eleanor Calloway uploaded the Harborline Trust Company custodial statements",
        "Calloway 2025 Binder",
      ],
    ];
    expect(list.querySelectorAll("li")).toHaveLength(6);
    let at = 0;
    for (const [when, line, context] of rows) {
      for (const part of [line, context]) {
        expect(text.indexOf(part, at), part).toBeGreaterThanOrEqual(0);
      }
      expect(text).toContain(when);
      at = text.indexOf(line);
    }
  });

  it("office-denver keeps only Denver's clients' rows", async () => {
    show("office-denver");
    await settled();
    await waitFor(() => {
      const text = document.querySelector("[data-home='activity']")?.textContent ?? "";
      expect(text).toContain("Dana Whitley");
      expect(text).not.toContain("Claire Feld");
    });
  });

  it("d: Kevin's Home draws no activity rows", async () => {
    show("d");
    await settled();
    expect(document.querySelector("[data-home='activity']")).toBeNull();
  });
});

describe("HOME-01 f and g", () => {
  it("f: the counts read 0, so the pane is the quiet day and no badge count shows", async () => {
    show("f");
    await settled();
    expect(await screen.findByText("Nothing waiting on you.")).toBeTruthy();
    expect(approvalsTab().textContent).not.toMatch(/[1-9]/u);
    expect(document.querySelectorAll("[data-gate]")).toHaveLength(0);
  });

  it("g: the reads never answer, so tiles and rows are skeletons, busy", async () => {
    show("g");
    await waitFor(() => {
      expect(document.querySelector("[data-dashboard='tiles'][aria-busy='true']")).not.toBeNull();
    });
    expect(document.querySelector("[data-dashboard='loading'][aria-busy='true']")).not.toBeNull();
    expect(document.querySelectorAll("[data-gate]")).toHaveLength(0);
  });
});

describe("HOME-01 role states and interactions", () => {
  it("b: Margaret's 4 = 2 decisions + 2 approvals & sends", async () => {
    show("b");
    await settled();
    await waitFor(() => {
      expect(summary()).toBe(
        "2 decisions · 0 sign-offs · 2 approvals & sends · sorted by deadline",
      );
    });
  });

  it("c: Samuel's summary reads 0 decisions · 4 sign-offs · 2 agent outputs", async () => {
    show("c");
    await settled();
    await waitFor(() => {
      expect(summary()).toBe("0 decisions · 4 sign-offs · 2 agent outputs · sorted by deadline");
    });
    expect(bandCounts()).toEqual({ decisions: 0, sign_offs: 4, agent_outputs: 2 });
  });

  it("d: Kevin has no gate and his work band reads My work 4", async () => {
    show("d");
    await settled();
    expect(await screen.findByText("Nothing waiting on you.")).toBeTruthy();
    const work = await screen.findByRole("region", { name: "My work" });
    expect(within(work).getAllByRole("listitem")).toHaveLength(4);
  });

  it("e: Grace sees counts-only admin tiles and her 2 sends", async () => {
    show("e");
    await settled();
    expect(screen.getByRole("region", { name: "17 Signatures out" })).toBeTruthy();
    expect(screen.getByRole("region", { name: "241 Binders" })).toBeTruthy();
    await waitFor(() => {
      expect(bandCounts()).toEqual({ decisions: 0, sign_offs: 0, approvals_sends: 2 });
    });
  });

  it("a2: Your returns 6 sits below the bands", async () => {
    show("a2");
    await settled();
    const work = await screen.findByRole("region", { name: "Your returns" });
    expect(within(work).getAllByRole("listitem")).toHaveLength(6);
  });

  it("h and i: the afternoon greeting at 12:40 PM", async () => {
    show("h");
    await settled();
    expect(screen.getByText("Good afternoon, Hannah")).toBeTruthy();
    cleanup();
    restore?.();
    show("i");
    await settled();
    expect(screen.getByText("Good afternoon, Marcus")).toBeTruthy();
  });

  it("office-denver: the tiles and caption recompute for Denver", async () => {
    show("office-denver");
    await settled();
    expect(await screen.findByText("Denver · 64 returns")).toBeTruthy();
    const single = [...document.querySelectorAll<HTMLElement>("[data-tile='single']")].map((t) =>
      t.getAttribute("aria-label"),
    );
    expect(single).toEqual(["5 Prepared", "4 In review", "3 Issues", "2 Ready"]);
  });

  it("tile-popover: a tile's by-office popover opens by keyboard and lists the offices (I-01-T11)", async () => {
    show("tile-popover");
    await settled();
    const [tile] = await screen.findAllByRole("button", { name: /by office$/u });
    expect(tile).toBeDefined();
    if (tile === undefined) return;
    // A native button: Enter and Space activate it, so the keyboard opens it as a click does.
    expect(tile.tagName).toBe("BUTTON");
    tile.focus();
    expect(document.activeElement).toBe(tile);
    fireEvent.click(tile);
    const pop = await screen.findByRole("dialog");
    expect(within(pop).getAllByRole("listitem").length).toBe(3);
    fireEvent.keyDown(pop, { key: "Escape" });
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).toBeNull();
    });
  });

  it("a: the running pill reads the home read's running count (polled every 30 s, I-01-T11)", async () => {
    show("a");
    await settled();
    expect(document.querySelector("[data-dashboard='running']")?.textContent).toMatch(/running/u);
    expect(RUNNING_POLL_MS).toBe(30_000);
  });

  it("today-brief-off: no Open Today after the date; a has it", async () => {
    show("today-brief-off");
    await settled();
    expect(document.querySelector("[data-home='open-today']")).toBeNull();
    cleanup();
    restore?.();
    show("a");
    await settled();
    expect(document.querySelector("[data-home='open-today']")).not.toBeNull();
  });

  it("walled: Lena's set holds nothing of Ashford", async () => {
    show("walled");
    await settled();
    expect(document.body.textContent).not.toMatch(/Ashford/u);
  });

  it("every state renders", async () => {
    for (const state of STATES) {
      show(state);
      if (state === "g") {
        await waitFor(() => {
          expect(document.querySelector("[aria-busy='true']")).not.toBeNull();
        });
      } else {
        await settled();
      }
      cleanup();
      restore?.();
      restore = undefined;
    }
  });
});

describe("HOME-01 segmented (DF-39)", () => {
  it("only Approvals carries a count; planned segments hide in production", () => {
    const segments = {
      deadlines: "planned",
      capacity: "planned",
      insights: "entitlement_missing",
    } as const;
    expect(homeSegmentOptions(11, segments, true).map((o) => [o.label, o.count])).toEqual([
      ["My work", undefined],
      ["Approvals", 11],
      ["Deadlines", undefined],
      ["Capacity", undefined],
    ]);
    expect(homeSegmentOptions(11, segments, false).map((o) => o.label)).toEqual([
      "My work",
      "Approvals",
    ]);
  });
});

describe("HOME-01 avoid", () => {
  it("no KPI numeral above 22px, no 600/700 weight, no Accrual or ACME", async () => {
    show("a");
    await settled();
    const html = document.body.innerHTML;
    expect(html).not.toMatch(/text-\[(2[3-9]|[3-9]\d)px\]/u);
    expect(html).not.toMatch(/font-(semibold|bold)/u);
    expect(document.body.textContent).not.toMatch(/\b(Accrual|ACME|Arc)\b/u);
  });
});
