// ADM-06 · Security center & data residency (G-02-T16). One test per artboard (a–j) and T03's
// states on its fixture scenario (SPEC-349 AC-15 to AC-30, AC-49), plus: production shows the
// single Require SSO toggle (no R2 rows without the fixture's `enterprise`), a save sends the
// version it read, and no security "score" is drawn. axe runs in the Playwright journey
// (G-02-T21), not here.
import { client } from "@abacus/api-client/client";
import { toastStore } from "@abacus/ui";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import {
  type FixtureHandler,
  type Scenario,
  installFixtureMode,
} from "../../app-core/fixture-mode";
import { newQueryClient } from "../../testing/support";
import { SecurityPage } from ".";
import { type Adm06State, ENTERPRISE, OPENS, scenarios } from "./scenarios";

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

function show(state: Adm06State, options: { enterprise?: boolean } = {}): Call[] {
  const scenario: Scenario = scenarios[state];
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
  const enterprise = options.enterprise === false ? undefined : ENTERPRISE[state];
  render(
    <QueryClientProvider client={newQueryClient()}>
      <SecurityPage initial={OPENS[state]} {...(enterprise === undefined ? {} : { enterprise })} />
    </QueryClientProvider>,
  );
  return calls;
}

const fieldset = async (title: string): Promise<HTMLElement> => {
  const heading = await screen.findByRole("heading", { name: title });
  const section = heading.closest("section");
  if (section === null) throw new Error(`no fieldset ${title}`);
  return section;
};
const card = async (title: string): Promise<HTMLElement> =>
  screen.findByRole("region", { name: title });

describe("ADM-06 Security center", () => {
  it("a: SSO and MFA enforced, the FTC clock, the export schedule and the posture", async () => {
    show("a");
    const signIn = await fieldset("Firm sign-in");
    expect(signIn.textContent).toContain("Microsoft Entra ID (SSO)");
    expect(signIn.textContent).toContain("Enforced since Jan 12, 2026 by Felix Andersen.");
    expect(signIn.textContent).toContain("Enforced · 46 of 46 enrolled");
    expect(signIn.textContent).toContain("1 · hardware key · last tested Aug 3, 2026");
    expect(
      within(signIn).getByRole("switch", { name: "Require SSO for all firm users" }),
    ).toBeTruthy();
    const incidents = await fieldset("Incident register");
    await within(incidents).findByText("Day 4 of 30 · notify by Oct 10 if ≥ 500");
    expect(incidents.textContent).toContain("INC-2026-004");
    expect(within(incidents).getAllByText("Not a notification event")).toHaveLength(2);
    const exportCard = await card("Data export");
    await within(exportCard).findByText("Scheduled");
    expect(exportCard.textContent).toContain("Monthly · 1st at 2:00 AM CT");
    expect(exportCard.textContent).toContain("Sep 1, 2026 · 386 GB");
    expect(exportCard.textContent).toContain("Two people: Felix Andersen + Margaret Okonkwo");
    const posture = await card("Posture");
    await within(posture).findByText("1 open incident");
    expect(posture.textContent).toContain("MFA 46/46");
    expect(posture.textContent).toContain("2 Pub 4557 items open");
    expect(document.body.textContent).not.toMatch(/score/i);
  });

  it("a, production: without the fixture's R2 data only the single Require SSO toggle renders", async () => {
    show("a", { enterprise: false });
    const signIn = await fieldset("Firm sign-in");
    expect(signIn.textContent).not.toContain("SCIM provisioning");
    expect(signIn.textContent).not.toContain("IdP-initiated SSO");
  });

  it("a, fieldset B: the DF-17 floor and DEC-35's lockout are locked", async () => {
    show("a");
    const portal = await fieldset("Client portal sign-in");
    expect(portal.textContent).toContain(
      "Require MFA for owners, signers, approvers and anyone who can see tax return information",
    );
    expect(portal.textContent).toContain("3 codes · 15 minutes");
    for (const toggle of within(portal).getAllByRole("switch")) {
      expect(
        toggle.getAttribute("aria-disabled") === "true" || toggle.hasAttribute("disabled"),
      ).toBe(true);
    }
  });

  it("a: a shorter idle timeout saves with the version it read", async () => {
    const calls = show("a");
    const signIn = await fieldset("Firm sign-in");
    const trigger = within(signIn).getByRole("button", { name: /Idle timeout/ });
    trigger.focus();
    fireEvent.keyDown(trigger, { key: "ArrowDown" });
    fireEvent.click(await screen.findByRole("menuitemradio", { name: "20 minutes" }));
    fireEvent.click(await screen.findByRole("button", { name: "Save" }));
    await waitFor(() => {
      const put = calls.find((c) => c.method === "PUT" && c.path === "/v1/firm/security/sign-in");
      expect(put?.body).toMatchObject({ session_idle_minutes: 20, version: 1 });
    });
  });

  it("b → g: Export now… asks for Margaret's approval, then the card waits for her", async () => {
    const calls = show("b");
    const exportCard = await card("Data export");
    fireEvent.click(await within(exportCard).findByRole("button", { name: "Export now…" }));
    const dialog = await screen.findByRole("dialog", { name: "Export all firm data?" });
    expect(dialog.textContent).toContain("Margaret Okonkwo must approve");
    expect(dialog.textContent).toContain("The link expires after 7 days.");
    fireEvent.click(within(dialog).getByRole("button", { name: "Request export" }));
    await waitFor(() => {
      expect(calls.some((c) => c.method === "POST" && c.path === "/v1/firm/data-exports")).toBe(
        true,
      );
    });
    await within(await card("Data export")).findByText("Waiting for approval · Margaret Okonkwo");
  });

  it("c: the history tray lists Sep 1 386 GB, Aug 1 371 GB and Jul 1 359 GB", async () => {
    show("c");
    await screen.findByText("Sep 1, 2026 · 386 GB", {
      selector: "[role=menuitem] *, [role=menuitem]",
    });
    expect(screen.getByText("Aug 1, 2026 · 371 GB")).toBeTruthy();
    expect(screen.getByText("Jul 1, 2026 · 359 GB")).toBeTruthy();
  });

  it("d: the incident drawer has the clock bar, the timeline and the two decisions", async () => {
    show("d");
    const drawer = await screen.findByRole("dialog");
    await within(drawer).findByText("1,812 failed sign-ins from 203.0.113.0/24 blocked");
    expect(within(drawer).getByRole("progressbar", { name: "Day 4 of 30" })).toBeTruthy();
    expect(within(drawer).getByRole("button", { name: "Close as not reportable…" })).toBeTruthy();
    expect(within(drawer).getByRole("button", { name: "Start notification…" })).toBeTruthy();
  });

  it("d, waiting: Felix's decision waits for Margaret", async () => {
    show("d_waiting");
    const drawer = await screen.findByRole("dialog");
    await within(drawer).findByText("Waiting for Margaret Okonkwo");
  });

  it("e: the Jan 11 snapshot reads 41 of 46 in red ink with the amber banner", async () => {
    show("e");
    await screen.findByText(
      "5 users without MFA. Enforcing SSO will require MFA at next sign-in.",
    );
    const signIn = await fieldset("Firm sign-in");
    const gap = within(signIn).getByText("41 of 46 enrolled");
    expect(gap.className).toContain("text-red-ink");
  });

  it("f: Margaret reads, Export now is hidden and Approve export shows", async () => {
    show("f");
    await screen.findByText("Only IT/Security can change security settings.");
    const exportCard = await card("Data export");
    await within(exportCard).findByRole("button", { name: "Approve export" });
    expect(within(exportCard).queryByRole("button", { name: "Export now…" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Save" })).toBeNull();
  });

  it("g: the requested export waits for Margaret", async () => {
    show("g");
    await within(await card("Data export")).findByText("Waiting for approval · Margaret Okonkwo");
  });

  it("h: WISP, residency and retention read as the handoff writes them", async () => {
    show("h");
    const wisp = await fieldset("WISP & safeguards");
    await within(wisp).findByText(
      /BH WISP v4 \(IRS Pub 5708 format\) · approved by Margaret Okonkwo Jan 15, 2026/,
    );
    expect(wisp.textContent).toContain("18 of 20 evidenced");
    expect(wisp.textContent).toContain("Annual penetration test — scheduled Oct 6, 2026");
    const residency = await fieldset("Data residency");
    expect(residency.textContent).toContain("United States");
    expect(residency.textContent).toContain("US · primary Ohio, backup Oregon");
    const retention = await fieldset("Retention defaults");
    expect(retention.textContent).toContain(
      "Clocks and holds are managed in Files › Retention (FIL-02).",
    );
    expect(retention.textContent).toContain("7 years · WORM after assembly");
  });

  it("i: Require SSO · Per user lists the seat holders, the break-glass account exempt", async () => {
    show("i");
    const table = await screen.findByRole("table", { name: "Require SSO per user" });
    const rows = within(table).getAllByRole("row");
    expect(rows).toHaveLength(48); // the header, 46 seat holders and the break-glass account
    expect(table.textContent).toContain("Break-glass account");
    expect(within(table).getByLabelText("Exempt")).toBeTruthy();
  });

  it("j: the SCIM error points to ADM-02's seats", async () => {
    show("j");
    await screen.findByText("1 user not provisioned · seat limit 46 of 46");
    expect(screen.getByRole("button", { name: "Open seats (ADM-02) →" })).toBeTruthy();
    expect((await card("Posture")).textContent).toContain("SCIM provisioning on");
  });

  it("sessions: the drawer lists the members' sessions and signs one out of this firm", async () => {
    const calls = show("sessions");
    const drawer = await screen.findByRole("dialog", { name: "Active sessions" });
    await within(drawer).findByText("Raj Malhotra");
    expect(drawer.textContent).toContain("Chrome · macOS");
    const [signOut] = within(drawer).getAllByRole("button", {
      name: /^Sign out of .*: Raj Malhotra$/,
    });
    if (signOut === undefined) throw new Error("no sign-out");
    fireEvent.click(signOut);
    await waitFor(() => {
      expect(calls.some((c) => c.method === "POST" && c.path.endsWith("/sign-out"))).toBe(true);
    });
  });

  it("unlock: a lock the provider keeps reads when it ends", async () => {
    show("unlock");
    const drawer = await screen.findByRole("dialog", { name: "Active sessions" });
    await within(drawer).findByText("Neil Ashcroft");
    fireEvent.click(within(drawer).getByRole("button", { name: "Unlock: Neil Ashcroft" }));
    await within(drawer).findByText("Unlocks automatically at 9:39 AM");
  });

  it.each([
    ["support_requested", "Awaiting firm approval"],
    ["support_granted", "Granted until 11:40 AM"],
    ["support_revoked", "Revoked"],
  ] as const)("%s: the support card reads %s", async (state, words) => {
    show(state);
    const support = await card("Support access");
    await within(support).findByText(words);
    expect(
      within(support).getByRole("switch", { name: "Allow support session requests" }),
    ).toBeTruthy();
  });
});
