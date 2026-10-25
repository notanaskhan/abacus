// CLI-04 · Contacts & portal access (P-07-T33). One test per artboard a–g on its fixture scenario
// (inside the CLI-02 record on its "Contacts & access" tab), the spec's acceptance checklist the
// contract carries, the writes (invite, resend, change scope, unlock, revoke), the walled 404 and
// the task's acceptance: "Scenarios a to g pass with axe and the footer sums to 24 delegated
// requests" (axe: e2e/screens/CLI-04.spec.ts).
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
} from "../../app-core/fixture-mode";
import { renderRoutes } from "../../testing/support";
import { CLI02, type Cli02Tab } from "../CLI-02";
import type { Cli04Open } from ".";
import { type Cli04State, OPENS, OVERLAYS, STATES, freshScenario, scenarios } from "./scenarios";

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

function install(scenario: Scenario, over: Record<string, FixtureHandler> = {}): Seen {
  const seen: Seen = { calls: [] };
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
  clientId,
  opens,
}: {
  clientId: string;
  opens?: Cli04Open | undefined;
}): JSX.Element {
  const [tab, setTab] = useState<Cli02Tab>("contacts");
  return <CLI02 clientId={clientId} tab={tab} onTab={setTab} contactsOpen={opens} />;
}

function show(state: Cli04State, over: Record<string, FixtureHandler> = {}): Seen {
  const seen = install(freshScenario(state), over);
  renderRoutes([
    {
      path: "/",
      component: () => <Harness clientId={OPENS[state]} opens={OVERLAYS[state]} />,
    },
  ]);
  return seen;
}

function rows(): HTMLElement[] {
  return [...document.querySelectorAll<HTMLElement>("tr[data-row]")];
}

function rowOf(name: string): HTMLElement {
  const found = rows().find((r) => r.querySelector("td")?.textContent.startsWith(name));
  if (found === undefined) throw new Error(`no row ${name}`);
  return found;
}

function cell(row: HTMLElement, i: number): string {
  return row.querySelectorAll("td")[i]?.textContent ?? "";
}

const COL = { contact: 0, roles: 1, scope: 2, portal: 3, mfa: 4, seen: 5 } as const;

async function loaded(count: RegExp | string): Promise<void> {
  expect(await screen.findByText(count)).toBeTruthy();
  await waitFor(() => {
    expect(rows().length).toBeGreaterThan(0);
  });
}

function openMenu(row: HTMLElement): HTMLElement {
  const trigger = within(row).getByRole("button", { name: /actions$/ });
  trigger.focus();
  fireEvent.keyDown(trigger, { key: "ArrowDown" });
  return screen.getByRole("menu");
}

describe("CLI-04 artboards", () => {
  it("defines a–g, all Grace Holloway at E0; a–f Northwind, g Copperleaf", () => {
    expect(STATES).toEqual(["a", "b", "c", "d", "e", "f", "g"]);
    for (const s of STATES) {
      expect(scenarios[s].persona).toBe("grace-holloway");
      expect(scenarios[s].clock).toBe("2026-09-14T09:24:00-05:00");
    }
    expect(OPENS.g).not.toBe(OPENS.a);
  });

  it("CLI-04a Northwind: six contacts, 3 active · 1 invited · 2 not invited, the 24-request footer", async () => {
    show("a");
    await loaded("3 active · 1 invited · 2 not invited");
    expect(
      screen.getByRole("tab", { name: /Contacts & access/ }).getAttribute("aria-selected"),
    ).toBe("true");
    expect(rows().map((r) => r.querySelector("button")?.textContent)).toEqual([
      "Dana Kowalski",
      "Northwind benefits committee",
      "Sam Ortiz",
      "Summit Plan Administrators",
      "Harborline Trust Company",
      "PayGrid Payroll",
    ]);
    const dana = rowOf("Dana Kowalski");
    expect(cell(dana, COL.contact)).toContain("dana.kowalski@northwindrobotics.com · HR Director");
    expect(cell(dana, COL.roles)).toContain("Plan administrator");
    expect(cell(dana, COL.portal)).toContain("Active");
    expect(cell(dana, COL.mfa)).toBe("On");
    expect(cell(dana, COL.seen)).toBe("8:02 AM");
    expect(cell(rowOf("Northwind benefits committee"), COL.seen)).toBe("Sep 3");
    const summit = rowOf("Summit Plan Administrators");
    expect(cell(summit, COL.portal)).toContain("Invited");
    expect(cell(summit, COL.portal)).toContain("Sent Sep 10 · expires Sep 24");
    expect(within(summit).getByRole("button", { name: "Resend" })).toBeTruthy();
    expect(cell(rowOf("Harborline Trust Company"), COL.portal)).toContain("Not invited");
    expect(
      within(rowOf("Harborline Trust Company")).getByRole("button", { name: "Invite…" }),
    ).toBeTruthy();
    expect(
      screen.getByText("Requests delegated: 10 + 9 + 2 + 2 + 1 = 24 · PBC received 11 of 24"),
    ).toBeTruthy();
  });

  it("CLI-04b the invite sheet for Harborline: its two delegated requests ticked, MFA on, 14 days, the scope note", async () => {
    show("b");
    const sheet = await screen.findByRole("dialog", { name: "Invite to portal" });
    expect(await within(sheet).findByText("certifications@harborlinetrust.com")).toBeTruthy();
    expect(within(sheet).getByText("Only delegated requests")).toBeTruthy();
    await waitFor(() => {
      expect(within(sheet).getAllByRole("checkbox")).toHaveLength(2);
    });
    for (const box of within(sheet).getAllByRole("checkbox")) {
      expect(box.getAttribute("aria-checked")).toBe("true");
    }
    expect(within(sheet).getByText("Email code")).toBeTruthy();
    const mfa = within(sheet).getByRole("switch", { name: "MFA required" });
    expect(mfa.getAttribute("aria-checked")).toBe("true");
    expect(within(sheet).getByText("14 days")).toBeTruthy();
    expect(within(sheet).getByText("Email preview")).toBeTruthy();
    expect(
      within(sheet).getByText(
        "Harborline Trust Company will see only these 2 requests. They will not see the plan's other documents, materiality, review notes or other clients.",
      ),
    ).toBeTruthy();
  });

  it("CLI-04b → c: Send invite grants exactly the ticked requests; Harborline reads Invited, sent Sep 14, with a toast", async () => {
    const seen = show("b");
    const sheet = await screen.findByRole("dialog", { name: "Invite to portal" });
    await waitFor(() => {
      expect(within(sheet).getAllByRole("checkbox")).toHaveLength(2);
    });
    fireEvent.click(within(sheet).getByRole("button", { name: "Send invite" }));
    await waitFor(() => {
      expect(toastStore.list()[0]?.text).toBe("Invite sent to Harborline Trust Company");
    });
    const sent = seen.calls.find((c) => c.method === "POST" && c.path.endsWith("/invitations"));
    const body = sent?.body as { grants: { role: string; request_item_ids: string[] }[] };
    expect(body.grants).toHaveLength(1);
    expect(body.grants[0]?.role).toBe("third_party");
    expect(body.grants[0]?.request_item_ids).toHaveLength(2);
    await waitFor(() => {
      expect(cell(rowOf("Harborline Trust Company"), COL.portal)).toContain("Sent Sep 14");
    });
    expect(screen.getByText("3 active · 2 invited · 1 not invited")).toBeTruthy();
  });

  it("CLI-04c Harborline Invited · Sent Sep 14", async () => {
    show("c");
    await loaded("3 active · 2 invited · 1 not invited");
    const harborline = rowOf("Harborline Trust Company");
    expect(cell(harborline, COL.portal)).toContain("Invited");
    expect(cell(harborline, COL.portal)).toContain("Sent Sep 14");
    expect(within(harborline).getByRole("button", { name: "Resend" })).toBeTruthy();
  });

  it("CLI-04d Sam Ortiz Locked after 3 incorrect codes (DF-24) and Unlock… clears it", async () => {
    const seen = show("d");
    await loaded(/1 locked/);
    const sam = rowOf("Sam Ortiz");
    expect(cell(sam, COL.portal)).toContain("Locked");
    expect(cell(sam, COL.portal)).toContain("3 incorrect codes");
    expect(cell(sam, COL.portal)).not.toContain("5 incorrect codes");
    fireEvent.click(within(sam).getByRole("button", { name: "Unlock…" }));
    const dialog = await screen.findByRole("alertdialog", {
      name: "Unlock portal sign-in for Sam Ortiz?",
    });
    fireEvent.click(within(dialog).getByRole("button", { name: "Unlock" }));
    await waitFor(() => {
      expect(seen.calls.some((c) => c.path.endsWith("/unlock"))).toBe(true);
    });
    await waitFor(() => {
      expect(cell(rowOf("Sam Ortiz"), COL.portal)).toContain("Active");
    });
  });

  it("CLI-04e Change access — Sam Ortiz: his 9 requests; unticking one sends the rest with the version seen", async () => {
    const seen = show("e");
    const sheet = await screen.findByRole("dialog", { name: "Change access — Sam Ortiz" });
    await waitFor(() => {
      expect(within(sheet).getAllByRole("checkbox")).toHaveLength(9);
    });
    fireEvent.click(within(sheet).getAllByRole("checkbox")[0] as HTMLElement);
    fireEvent.click(within(sheet).getByRole("button", { name: "Save access" }));
    await waitFor(() => {
      expect(seen.calls.some((c) => c.method === "PUT" && c.path.endsWith("/access"))).toBe(true);
    });
    const put = seen.calls.find((c) => c.method === "PUT")?.body as {
      seen_version: number;
      grants: { request_item_ids: string[] }[];
    };
    expect(put.seen_version).toBe(3);
    expect(put.grants[0]?.request_item_ids).toHaveLength(8);
  });

  it("CLI-04f Revoke portal access for Summit: requests stay with Northwind; confirm revokes", async () => {
    const seen = show("f");
    const dialog = await screen.findByRole("alertdialog", {
      name: "Revoke portal access for Summit Plan Administrators?",
    });
    expect(
      await within(dialog).findByText(
        "Their invite stops working immediately. Requests stay assigned to Northwind Robotics, Inc.",
      ),
    ).toBeTruthy();
    fireEvent.click(within(dialog).getByRole("button", { name: "Revoke" }));
    await waitFor(() => {
      expect(seen.calls.some((c) => c.path.endsWith("/revoke"))).toBe(true);
    });
    await waitFor(() => {
      expect(cell(rowOf("Summit Plan Administrators"), COL.portal)).toContain("Not invited");
    });
  });

  it("CLI-04g Copperleaf: Tess Moreno owner, Ben Ashby controller, the non-attest note", async () => {
    show("g");
    await loaded("2 active · 0 invited · 0 not invited");
    expect(cell(rowOf("Tess Moreno"), COL.roles)).toContain("Owner");
    expect(cell(rowOf("Tess Moreno"), COL.contact)).toContain("CEO");
    expect(cell(rowOf("Ben Ashby"), COL.roles)).toContain("Controller");
    expect(cell(rowOf("Ben Ashby"), COL.contact)).toContain("Approver of record");
    expect(screen.getByText("Non-attest client: no SKE designation required")).toBeTruthy();
  });
});

describe("CLI-04 acceptance", () => {
  it("CLI-04 acceptance: delegated request counts sum to 24 (10 + 9 + 2 + 2 + 1) and the footer ties to PBC 11 of 24", async () => {
    show("a");
    await loaded("3 active · 1 invited · 2 not invited");
    const footer = document.querySelector("[data-footer='delegated']")?.textContent ?? "";
    const m = /Requests delegated: ([\d + ]+) = (\d+) · PBC received (\d+) of (\d+)/u.exec(footer);
    const parts = (m?.[1] ?? "").split("+").map((p) => Number(p.trim()));
    expect(parts).toEqual([10, 9, 2, 2, 1]);
    expect(parts.reduce((a, b) => a + b, 0)).toBe(24);
    expect(Number(m?.[2])).toBe(24);
    expect([Number(m?.[3]), Number(m?.[4])]).toEqual([11, 24]);
  });

  it("CLI-04 acceptance: third parties are scoped to delegated requests with a lock icon", async () => {
    show("a");
    await loaded("3 active · 1 invited · 2 not invited");
    for (const name of [
      "Sam Ortiz",
      "Summit Plan Administrators",
      "Harborline Trust Company",
      "PayGrid Payroll",
    ]) {
      const row = rowOf(name);
      expect(cell(row, COL.roles)).toContain("Third party");
      expect(cell(row, COL.scope)).toMatch(/delegated requests only$/u);
      expect(row.querySelectorAll("td")[COL.scope]?.querySelector("svg")).not.toBeNull();
    }
    expect(cell(rowOf("Sam Ortiz"), COL.scope)).toBe("9 delegated requests only");
    expect(cell(rowOf("Dana Kowalski"), COL.roles)).not.toContain("Third party");
  });

  it("CLI-04 acceptance: status pills read Active, Invited, Not invited and Locked from the registry", async () => {
    show("d");
    await loaded(/1 locked/);
    const pill = (name: string): string => {
      const portal = rowOf(name).querySelectorAll("td")[COL.portal];
      return portal?.querySelector("span[class*='bg-']")?.className ?? "";
    };
    expect(pill("Dana Kowalski")).toContain("bg-green-tint");
    expect(pill("Summit Plan Administrators")).toContain("bg-amber-tint");
    expect(pill("Harborline Trust Company")).toContain("bg-chip");
    expect(pill("Sam Ortiz")).toContain("bg-red-tint");
  });

  it("CLI-04 acceptance: no avatars; nothing is an agent-owned send, approve or sign-off", async () => {
    show("a");
    await loaded("3 active · 1 invited · 2 not invited");
    expect(document.querySelector("[data-avatar], img")).toBeNull();
    for (const word of [/^Approve/, /^Sign off/, /^Release/, /^Post/, /^Decide/]) {
      expect(screen.queryByRole("button", { name: word })).toBeNull();
    }
  });
});

describe("CLI-04 behaviour", () => {
  it("Resend names the row's invitation and toasts", async () => {
    const seen = show("a");
    await loaded("3 active · 1 invited · 2 not invited");
    fireEvent.click(
      within(rowOf("Summit Plan Administrators")).getByRole("button", { name: "Resend" }),
    );
    await waitFor(() => {
      expect(
        seen.calls.some((c) => c.path.includes("/invitations/") && c.path.endsWith("/resend")),
      ).toBe(true);
    });
    await waitFor(() => {
      expect(toastStore.list()[0]?.text).toBe("Invite sent to Summit Plan Administrators");
    });
  });

  it("the row menu offers Change scope… and Revoke… on a live contact; Unlock… only when locked", async () => {
    show("a");
    await loaded("3 active · 1 invited · 2 not invited");
    const menu = openMenu(rowOf("Dana Kowalski"));
    expect(
      within(menu).getByRole("menuitem", { name: "Change scope…" }).getAttribute("aria-disabled"),
    ).not.toBe("true");
    expect(
      within(menu).getByRole("menuitem", { name: "Unlock…" }).getAttribute("aria-disabled"),
    ).toBe("true");
    expect(
      within(menu).getByRole("menuitem", { name: "Revoke…" }).getAttribute("aria-disabled"),
    ).not.toBe("true");
  });

  it("the search narrows the rows by name or address", async () => {
    show("a");
    await loaded("3 active · 1 invited · 2 not invited");
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "keystone" } });
    await waitFor(() => {
      expect(rows()).toHaveLength(1);
    });
    expect(rowOf("Sam Ortiz")).toBeTruthy();
  });

  it("a name opens the contact drawer: roles per entity and delegated requests", async () => {
    show("a");
    await loaded("3 active · 1 invited · 2 not invited");
    fireEvent.click(within(rowOf("Dana Kowalski")).getByRole("button", { name: "Dana Kowalski" }));
    const drawer = await screen.findByRole("dialog", { name: "Dana Kowalski" });
    expect(within(drawer).getByText("Plan administrator")).toBeTruthy();
    expect(within(drawer).getByText("Delegated requests")).toBeTruthy();
    expect(within(drawer).getByText("Sign-in history")).toBeTruthy();
  });

  it("a viewer without the row actions sees them disabled (allowed_actions)", async () => {
    install(scenarios.a);
    restore?.();
    restore = installFixtureMode({ ...freshScenario("a"), persona: "margaret-okonkwo" });
    renderRoutes([{ path: "/", component: () => <Harness clientId={OPENS.a} /> }]);
    await loaded("3 active · 1 invited · 2 not invited");
    const invite = within(rowOf("Harborline Trust Company")).getByRole<HTMLButtonElement>(
      "button",
      {
        name: "Invite…",
      },
    );
    expect(invite.disabled).toBe(true);
  });

  it("a walled or unknown client answers 404 and the list says nothing about why (INV-3)", async () => {
    show("a", {
      "GET /v1/clients/{client_id}/contacts": () => json({ detail: "not_found" }, 404),
    });
    await waitFor(() => {
      expect(screen.queryByText(/active ·/)).toBeNull();
    });
    expect(rows()).toHaveLength(0);
  });

  it("the error state retries", async () => {
    show("a", { "GET /v1/clients/{client_id}/contacts": () => json({}, 500) });
    expect(await screen.findByRole("button", { name: "Retry" })).toBeTruthy();
  });

  it("without contacts.v2 the tab stays planned and the record shows its Overview", async () => {
    const base = freshScenario("a");
    install(base, {
      "GET /v1/me/capabilities": async (request) => {
        const answer = await (base.handlers["GET /v1/me/capabilities"] as FixtureHandler)(request);
        const body = (await answer.json()) as { flags: Record<string, unknown> };
        return json({ ...body, flags: { ...body.flags, "contacts.v2": false } });
      },
    });
    renderRoutes([{ path: "/", component: () => <Harness clientId={OPENS.a} /> }]);
    await screen.findByRole("heading", { name: /Northwind Robotics, Inc\./ });
    await waitFor(() => {
      expect(document.querySelector("[data-screen='CLI-04']")).toBeNull();
    });
  });
});
