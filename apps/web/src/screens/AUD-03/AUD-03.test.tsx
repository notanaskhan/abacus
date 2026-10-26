// AUD-03 · Source documents / PBC with viewer (A-01-T15, A-01-T16). One test per artboard (a–g) on
// its fixture scenario, the loading, error, not-found, staff-accept-off and offshore states, the
// acceptance checklist (spec.md and revision.md R2), A-01 Stories 3.3, 3.4 and 4.1, the figures
// that must foot, the logged reveal, the third-party request, the legacy redirect and the AVOID
// list. Nothing on this screen accepts, returns or sends by itself.
import { client } from "@abacus/api-client/client";
import { toastStore } from "@abacus/ui";
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import type { JSX } from "react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import {
  type FixtureHandler,
  type Scenario,
  installFixtureMode,
  json,
  never,
} from "../../app-core/fixture-mode";
import { WHITFIELD_ACCOUNT_VALUE, WHITFIELD_HOLDINGS } from "../../fixtures/seed/aud03";
import { boardRoute } from "../../routes/firm/engagements";
import { renderRoutes } from "../../testing/support";
import { SourceDocumentsPage } from ".";
import {
  ANA_ACTIONS,
  AUDIT_ID,
  type Aud03Options,
  type Aud03State,
  ENGAGEMENT_ID,
  OPENS,
  STATES,
  scenarioFor,
} from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
  Object.assign(URL, {
    createObjectURL: vi.fn(() => "blob:page"),
    revokeObjectURL: vi.fn(),
  });
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

function install(scenario: Scenario, over: Record<string, FixtureHandler> = {}): Call[] {
  const calls: Call[] = [];
  const handlers = Object.fromEntries(
    Object.entries({ ...scenario.handlers, ...over }).map(([key, handler]) => [
      key,
      ((request) => {
        calls.push({ method: request.method, path: request.path, body: request.body });
        return handler(request);
      }) satisfies FixtureHandler,
    ]),
  );
  restore = installFixtureMode({ ...scenario, handlers });
  return calls;
}

function show(
  state: Aud03State,
  options: Aud03Options = {},
  over: Record<string, FixtureHandler> = {},
  auditId: string = AUDIT_ID,
): Call[] {
  const calls = install(scenarioFor(state, options), over);
  renderRoutes([
    {
      path: "/",
      component: () => <SourceDocumentsPage auditId={auditId} initial={OPENS[state]} />,
    },
  ]);
  return calls;
}

async function ready(): Promise<void> {
  await screen.findByText("PY2025 Employee Benefit Plan Audit");
  await waitFor(() => {
    expect(rows().length).toBe(24);
  });
}

function rows(): HTMLElement[] {
  return [...document.querySelectorAll<HTMLElement>("[data-aud03-row]")];
}

function rowOf(title: string): HTMLElement {
  const found = rows().find(
    (r) => r.querySelector("[data-aud03-open] span span")?.textContent === title,
  );
  if (found === undefined) throw new Error(`no row ${title}`);
  return found;
}

function subOf(title: string): string {
  return rowOf(title).querySelector("[data-row-sub]")?.textContent.trim() ?? "";
}

function bands(): string[] {
  return [...document.querySelectorAll<HTMLElement>('[data-source-docs="group"] > button')].map(
    (b) => b.textContent,
  );
}

/** Each band's "n of N", read from its own text node (a title can end in a digit). */
function counts(): (string | undefined)[] {
  return [...document.querySelectorAll<HTMLElement>('[data-source-docs="group"] > button')].map(
    (b) =>
      [...b.querySelectorAll("span")]
        .map((t) => t.textContent)
        .find((t) => /^\d+ of \d+$/.test(t)),
  );
}

function viewerPane(): HTMLElement {
  const pane = document.querySelector<HTMLElement>('[data-audit-dock="viewer"]');
  if (pane === null) throw new Error("no viewer");
  return pane;
}

const COUNTS = ["3 of 5", "4 of 6", "3 of 7", "1 of 4", "0 of 1", "0 of 1"];

describe("AUD-03 artboards", () => {
  it("has one scenario per artboard a–g", () => {
    expect(STATES).toEqual(["a", "b", "c", "d", "e", "f", "g"]);
  });

  it("AUD-03a default: Missing first, six counted bands, BrokerWindow selected with masked SSNs", async () => {
    show("a");
    await ready();
    expect(counts()).toEqual(COUNTS);
    expect(screen.getByText("Sample-driven · 0")).toBeTruthy();
    expect(screen.getByText("Item requests are generated after Sample Selection.")).toBeTruthy();
    expect(screen.getByRole("button", { name: /Missing first/ })).toBeTruthy();
    const selected = rowOf("Brokerage / SDBA asset detail — BrokerWindow");
    expect(selected.querySelector("[aria-current='true']")).not.toBeNull();
    expect(subOf("Brokerage / SDBA asset detail — BrokerWindow")).toBe(
      "initial-input/BrokerWindow Asset Detail 2025.pdf · matched 96%",
    );
    await waitFor(() => {
      expect(viewerPane().textContent).toContain("•••-••-2281");
    });
    expect(viewerPane().textContent).toContain("•••-••-6610");
    expect(screen.getByText("11 of 24 received")).toBeTruthy();
  });

  it("AUD-03b needs review: Match 94%, two passed checks above the page, Accept moves the rail to 12 of 24", async () => {
    const calls = show("b");
    await ready();
    expect(subOf("Certified trust report (full year, signed)")).toBe(
      "harborline-upload/Harborline Certification PY2025 signed.pdf · uploaded Sep 11 · matched 94%",
    );
    const pane = viewerPane();
    await within(pane).findByText("Match 94%");
    const card = await waitFor(() => {
      const found = pane.querySelector<HTMLElement>("[data-screening-card='passed']");
      expect(found).not.toBeNull();
      return found as HTMLElement;
    });
    expect(within(card).getByText("Does this answer the request?")).toBeTruthy();
    expect(within(card).getByText("Is it inside the expected period?")).toBeTruthy();
    expect(within(pane).getByRole("button", { name: "Return…" })).toBeTruthy();
    fireEvent.click(within(pane).getByRole("button", { name: "Accept" }));
    await waitFor(() => {
      expect(rowOf("Certified trust report (full year, signed)").dataset.status).toBe("received");
    });
    await screen.findByText("12 of 24 received");
    expect(bands()[1]).toContain("5 of 6");
    const accepted = calls.filter((c) => c.path.endsWith("/decision/accept"));
    expect(accepted).toHaveLength(1);
  });

  it("AUD-03c low-confidence match · Sep 9: the 62% proposal held, flagged with the domain reason", async () => {
    show("c");
    await ready();
    await screen.findByText("10 of 24 received");
    expect(subOf("Schedule of Account Balances")).toBe(
      "Schedule of Account Balances ← initial-input/BrokerWindow Asset Detail 2025.pdf · match 62%",
    );
    const row = rowOf("Schedule of Account Balances");
    expect(row.dataset.status).toBe("uploaded");
    expect(row.querySelector("[data-screening-glyph='flagged']")).not.toBeNull();
    expect(rowOf("Certified trust report (full year, signed)").dataset.status).toBe("requested");
    const pane = viewerPane();
    await within(pane).findByText("Match 62%");
    await waitFor(() => {
      expect(pane.querySelector("[data-screening-card='flagged']")).not.toBeNull();
    });
    await within(pane).findByText(
      "This file covers only the 31 participants in BrokerWindow; a schedule of account balances covers every participant.",
    );
    expect(within(pane).getAllByText("BrokerWindow Asset Detail 2025.pdf").length).toBeGreaterThan(
      0,
    );
  });

  it("AUD-03d Return dialog: Wrong document preselected; confirm is a send-back and the row reads Returned · wrong document", async () => {
    const calls = show("d");
    await ready();
    const dialog = await screen.findByRole("dialog", { name: "Return to client" });
    const wrong = await within(dialog).findByRole("radio", { name: "Wrong document" });
    expect(wrong.getAttribute("aria-checked")).toBe("true");
    expect(calls.some((c) => c.path.endsWith("/decision/send-back"))).toBe(false);
    fireEvent.click(within(dialog).getByRole("button", { name: "Return" }));
    await waitFor(() => {
      expect(rowOf("Schedule of Account Balances").dataset.status).toBe("returned");
    });
    expect(
      within(rowOf("Schedule of Account Balances")).getByText("Returned · wrong document"),
    ).toBeTruthy();
    const sent = calls.filter((c) => c.path.endsWith("/decision/send-back"));
    expect(sent).toHaveLength(1);
    expect((sent[0]?.body as { reason_code?: string }).reason_code).toBe("wrong_document");
    // A-01 Story 3.3: no message leaves with the return; only P-06's follow-up sends.
    expect(calls.some((c) => c.path === "/v1/follow-ups/send")).toBe(false);
  });

  it("AUD-03e requested row: Not received yet, who owes it and when, Remind and Request from third party…", async () => {
    show("e");
    await ready();
    const pane = viewerPane();
    await within(pane).findByText("Not received yet");
    expect(within(pane).getByText("Requested Sep 1 from Dana Kowalski · due Sep 18")).toBeTruthy();
    expect(within(pane).getByRole("button", { name: "Remind" })).toBeTruthy();
    expect(within(pane).getByRole("button", { name: "Request from third party…" })).toBeTruthy();
  });

  it("AUD-03f all received · late September: every band n of n and Nothing missing", async () => {
    show("f");
    await ready();
    expect(counts()).toEqual(["5 of 5", "6 of 6", "7 of 7", "4 of 4", "1 of 1", "1 of 1"]);
    expect(screen.getByRole("button", { name: /Nothing missing/ })).toBeTruthy();
    await screen.findByText("24 of 24 received");
    expect(subOf("Withdrawals / distributions report")).toBe(
      "client-upload/Withdrawals distributions report.pdf · uploaded Sep 24 · matched 97%",
    );
  });

  it("AUD-03g overdue · Sep 21: the 9 rows due Sep 18 read Overdue, the 3 due later keep the ring", async () => {
    show("g");
    await ready();
    const overdue = rows().filter((r) => r.querySelector("[data-row-status='overdue']") !== null);
    expect(overdue).toHaveLength(9);
    const ringed = rows().filter((r) => r.querySelector("[data-row-status='requested']") !== null);
    expect(ringed).toHaveLength(3);
    expect(within(rowOf("W-3 Form")).getByText("Overdue")).toBeTruthy();
    expect(within(viewerPane()).getByText(/due Sep 18 · overdue/)).toBeTruthy();
  });
});

describe("AUD-03 states", () => {
  it("loading: skeleton rows while the aggregate is pending", async () => {
    show("a", {}, { "GET /v1/audits/{work_item_id}/source-documents": () => never() });
    await screen.findByText("PY2025 Employee Benefit Plan Audit");
    expect(rows()).toHaveLength(0);
  });

  it("error: the read fails and the canvas offers a retry", async () => {
    show(
      "a",
      {},
      {
        "GET /v1/audits/{work_item_id}/source-documents": () => json({ detail: "boom" }, 500),
      },
    );
    await screen.findByText("PY2025 Employee Benefit Plan Audit");
    await screen.findByRole("button", { name: /Try again|Retry/ });
  });

  it("not found: another tenant's or a walled audit is a 404 with no hint (INV-3)", async () => {
    show("a", {}, {}, "00000000-0000-4000-8000-000000000000");
    await waitFor(() => {
      expect(document.querySelector("[data-screen='AUD-03']")).not.toBeNull();
    });
    await waitFor(() => {
      expect(screen.queryByText("PY2025 Employee Benefit Plan Audit")).toBeNull();
    });
    expect(rows()).toHaveLength(0);
  });

  it("staff accept off: the strip shows only Return…", async () => {
    show("b", { actions: ANA_ACTIONS.filter((a) => a !== "evidence.accept") });
    await ready();
    const pane = viewerPane();
    await within(pane).findByRole("button", { name: "Return…" });
    expect(within(pane).queryByRole("button", { name: "Accept" })).toBeNull();
  });

  it("offshore member: the masked text view, never page images, and no Reveal (logged)", async () => {
    const calls = show("a", { textOnly: true });
    await ready();
    const pane = viewerPane();
    await waitFor(() => {
      expect(pane.querySelector("[data-text-view]")).not.toBeNull();
    });
    await within(pane).findByText(/SSN: •••-••-2281/);
    expect(within(pane).queryByRole("button", { name: "Reveal (logged)" })).toBeNull();
    expect(calls.some((c) => /\/pages\/\d+$/.test(c.path))).toBe(false);
  });
});

describe("AUD-03 acceptance", () => {
  it("AUD-03 acceptance: group counts read 3 of 5 · 4 of 6 · 3 of 7 · 1 of 4 · 0 of 1 · 0 of 1, which sums to 11 of 24, and the rail matches", async () => {
    show("a");
    await ready();
    const pairs = COUNTS.map((c) => c.split(" of ").map(Number));
    const received = pairs.reduce((n, [a = 0]) => n + a, 0);
    const total = pairs.reduce((n, [, b = 0]) => n + b, 0);
    expect([received, total]).toEqual([11, 24]);
    expect(screen.getByText("11 of 24 received")).toBeTruthy();
  });

  it("AUD-03 acceptance: every open row names who owes it and when", async () => {
    show("a");
    await ready();
    const open = rows().filter((r) => r.dataset.status === "requested");
    expect(open).toHaveLength(12);
    const owners = new Set<string>();
    for (const r of open) {
      const sub = r.querySelector("[data-row-sub]")?.textContent ?? "";
      expect(sub).toMatch(/^Requested Sep 1 · due Sep (18|25|30) · .+$/);
      owners.add(sub.split(" · ")[2] ?? "");
    }
    expect(owners).toEqual(
      new Set([
        "Dana Kowalski",
        "Sam Ortiz, Keystone",
        "Harborline Trust Company",
        "PayGrid Payroll",
        "Summit Plan Administrators",
      ]),
    );
  });

  it("AUD-03 acceptance: the BrokerWindow participant's holdings foot to $214,380.50 and the SSNs are masked", async () => {
    const cents = WHITFIELD_HOLDINGS.map(([, value]) =>
      Math.round(Number(value.replace(/[$,]/g, "")) * 100),
    );
    expect(cents.reduce((a, b) => a + b, 0)).toBe(21_438_050);
    expect(WHITFIELD_ACCOUNT_VALUE).toBe("$214,380.50");
    show("a");
    await ready();
    await waitFor(() => {
      expect(viewerPane().textContent).toContain("•••-••-2281");
    });
    expect(document.body.textContent).not.toMatch(/\b\d{3}-\d{2}-\d{4}\b/);
  });

  it("AUD-03 acceptance: accepting the certified trust report needs a human click; nothing is accepted on load", async () => {
    const calls = show("b");
    await ready();
    await within(viewerPane()).findByRole("button", { name: "Accept" });
    expect(calls.some((c) => c.path.endsWith("/decision/accept"))).toBe(false);
    expect(screen.getByText("11 of 24 received")).toBeTruthy();
  });

  it("AUD-03 acceptance (R2): Linked (n) and the screening glyph on every upload row; requested rows show — and no glyph", async () => {
    show("a");
    await ready();
    for (const r of rows()) {
      const linked = r.querySelector<HTMLElement>("[data-linked]");
      if (r.dataset.status === "requested") {
        expect(linked?.textContent).toBe("—");
        expect(r.querySelector("[data-screening-glyph]")).toBeNull();
      } else {
        expect(linked?.getAttribute("aria-label")).toBe("Linked (1)");
        expect(r.querySelector("[data-screening-glyph='passed']")).not.toBeNull();
      }
    }
  });

  it("AUD-03 acceptance (R2): counts stay 24 requests · 11 received · 1 needs review · 12 requested", async () => {
    show("a");
    await ready();
    const by = (s: string): number => rows().filter((r) => r.dataset.status === s).length;
    expect([rows().length, by("received"), by("uploaded"), by("requested")]).toEqual([
      24, 11, 1, 12,
    ]);
  });

  it("A-01 Story 4.1: Remind… drafts Dana's 5 open items and sends only on a person's click", async () => {
    const calls = show("e");
    await ready();
    fireEvent.click(within(viewerPane()).getByRole("button", { name: "Remind" }));
    const sheet = await screen.findByRole("dialog");
    for (const title of [
      "IRS opinion letter on the pre-approved plan document",
      "W-3 Form",
      "Opt-Out Elections",
      "Pay Rate Authorizations",
      "Participant Complaints Log and Support",
    ]) {
      expect(within(sheet).getByText(title)).toBeTruthy();
    }
    expect(within(sheet).getByText("Nothing is sent until you click Send.")).toBeTruthy();
    expect(calls.some((c) => c.path === "/v1/follow-ups/send")).toBe(false);
    fireEvent.click(within(sheet).getByRole("button", { name: "Send 1 follow-up" }));
    await waitFor(() => {
      expect(calls.some((c) => c.path === "/v1/follow-ups/send")).toBe(true);
    });
  });

  it("A-01 Story 4.1: the header Remind… asks for every open request, one draft per contact", async () => {
    const calls = show("a");
    await ready();
    fireEvent.click(screen.getByRole("button", { name: "Remind…" }));
    await screen.findByRole("dialog");
    const drafted = calls.find((c) => c.path === "/v1/follow-ups/drafts");
    expect((drafted?.body as { request_item_ids?: string[] }).request_item_ids).toHaveLength(12);
  });

  it("A-01-T16: Request from third party… delegates the request to a chosen contact on a person's click", async () => {
    const calls = show("e", { actions: [...ANA_ACTIONS, "request_item.delegate"] });
    await ready();
    fireEvent.click(
      within(viewerPane()).getByRole("button", { name: "Request from third party…" }),
    );
    const dialog = await screen.findByRole("dialog", { name: "Request from a third party" });
    const option = (await within(dialog).findAllByRole("radio"))[0];
    if (option === undefined) throw new Error("no contact");
    fireEvent.click(option);
    const send = within(dialog).getByRole("button", { name: /^Send to / });
    expect(calls.some((c) => c.path.endsWith("/delegate"))).toBe(false);
    fireEvent.click(send);
    await waitFor(() => {
      expect(calls.some((c) => c.path.endsWith("/delegate"))).toBe(true);
    });
  });

  it("A-01-T16: Request from third party… is disabled without request_item.delegate (staff)", async () => {
    show("e");
    await ready();
    const button = within(viewerPane()).getByRole("button", { name: "Request from third party…" });
    expect((button as HTMLButtonElement).disabled).toBe(true);
  });

  it("P-03-T16: Reveal (logged) posts one logged reveal and shows the value in place of its mask", async () => {
    const calls = show("a");
    await ready();
    const reveal = (
      await within(viewerPane()).findAllByRole("button", { name: "Reveal (logged)" })
    )[0];
    if (reveal === undefined) throw new Error("no reveal");
    fireEvent.click(reveal);
    await within(viewerPane()).findByText("900-41-2281");
    expect(calls.filter((c) => c.path.endsWith("/pii-reveals"))).toHaveLength(1);
  });

  it("P-03-T16: a stale step-up asks to confirm it's you and shows nothing", async () => {
    show("a", { staleMfa: true });
    await ready();
    const reveal = (
      await within(viewerPane()).findAllByRole("button", { name: "Reveal (logged)" })
    )[0];
    if (reveal === undefined) throw new Error("no reveal");
    fireEvent.click(reveal);
    await screen.findByRole("dialog", { name: "Confirm it's you" });
    expect(document.body.textContent).not.toContain("900-41-2281");
  });

  it("A-01-T16: the legacy /engagements/$id/requests opens AUD-03 on the engagement's audit", async () => {
    install(scenarioFor("a"));
    renderRoutes(
      [
        {
          path: "/engagements/$engagementId/requests",
          component: boardRoute.options.component as () => JSX.Element,
        },
        {
          path: "/audits/$auditId/source-documents",
          component: () => <p>AUD-03 opened</p>,
        },
      ],
      { at: `/engagements/${ENGAGEMENT_ID}/requests` },
    );
    await screen.findByText("AUD-03 opened");
  });
});

describe("AUD-03 avoid", () => {
  it("AUD-03 avoid: banned names, agent-owned decisions and a screening percentage", async () => {
    show("c");
    await ready();
    const text = document.body.textContent;
    for (const word of ["Accrual", "ACME", "Finality", "Living Robotics", "lorem"]) {
      expect(text).not.toContain(word);
    }
    expect(text).not.toMatch(/\bArc\b/);
    expect(text).not.toMatch(/\btask\b/i);
    for (const verb of [/^Approve/, /^Sign off/, /^Release/, /^Post\b/]) {
      expect(screen.queryAllByRole("button", { name: verb })).toHaveLength(0);
    }
    const card = await waitFor(() => {
      const found = viewerPane().querySelector<HTMLElement>("[data-screening-card]");
      expect(found).not.toBeNull();
      return found as HTMLElement;
    });
    expect(card.textContent).not.toMatch(/\d+\s?%/);
  });

  it("AUD-03 avoid: red only for Overdue and Returned, never for an ordinary missing row", async () => {
    show("a");
    await ready();
    for (const r of rows().filter((x) => x.dataset.status === "requested")) {
      expect(r.innerHTML).not.toContain("red");
    }
  });
});
