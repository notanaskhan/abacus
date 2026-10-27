// CLI-08 · Independence & conflicts (P-07-T48; docs/screens/CLI-08.md). One test per artboard a–g
// and the declined-note state on its fixture scenario, and the acceptance: "Scenarios a to g and
// the declined-note state pass with axe and Conclude is disabled for everyone but the engagement
// partner" (axe: e2e/screens/CLI-08.spec.ts, Playwright). Also: only Ana confirms for Ana (three
// statements), the reminder is a person's click, and the AVOID list.
import { client } from "@abacus/api-client/client";
import { toastStore } from "@abacus/ui";
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import {
  type FixtureHandler,
  type Scenario,
  installFixtureMode,
} from "../../app-core/fixture-mode";
import { renderRoutes } from "../../testing/support";
import { CLI08 } from ".";
import { COPY } from "./copy";
import {
  CHECK_ID,
  CLIENT_ID,
  type Cli08State,
  ENGAGEMENT_ID,
  OPENS,
  STATES,
  freshScenario,
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

interface Call {
  method: string;
  path: string;
  body: unknown;
}

function install(scenario: Scenario): Call[] {
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
  return calls;
}

function show(state: Cli08State): Call[] {
  const calls = install(freshScenario(state));
  renderRoutes([
    {
      path: "/",
      component: () => (
        <CLI08
          clientId={CLIENT_ID}
          engagementId={ENGAGEMENT_ID}
          tab={OPENS[state].tab}
          checkId={CHECK_ID}
          sheet={OPENS[state].sheet === true}
        />
      ),
    },
  ]);
  return calls;
}

function concludeButton(): HTMLButtonElement {
  return screen.getByRole("button", { name: COPY.conclude.button });
}

describe("CLI-08 artboards", () => {
  it("has every artboard and the declined-note state as a scenario", () => {
    expect(STATES).toEqual(["a", "b", "c", "d", "e", "f", "g", "declined"]);
  });

  it("a: 4 of 5 confirmed, Ana Cruz pending, Conclude reserved to Margaret Okonkwo", async () => {
    show("a");
    expect(await screen.findByText("4 of 5 confirmed")).toBeTruthy();
    expect(screen.getByText(/^Ana Cruz has not confirmed independence\./)).toBeTruthy();
    expect(screen.getByText("Requested · 2 reminders")).toBeTruthy();
    expect(screen.getAllByText("✓ Confirmed")).toHaveLength(4);
    const conclude = concludeButton();
    expect(conclude.disabled).toBe(true);
    expect(conclude.title).toBe("Reserved to Margaret Okonkwo · 1 confirmation pending");
    // Hannah confirmed already: her own button is disabled.
    expect(
      screen.getByRole<HTMLButtonElement>("button", { name: COPY.team.confirmMine }).disabled,
    ).toBe(true);
    expect(screen.getByText(COPY.team.footer)).toBeTruthy();
  });

  it("a: Send reminder is a person's click to Ana", async () => {
    const calls = show("a");
    fireEvent.click(await screen.findByRole("button", { name: COPY.reminder.send }));
    await waitFor(() => {
      expect(toastStore.list()[0]?.text).toBe("Reminder sent to Ana Cruz");
    });
    const sent = calls.find((c) => c.path.endsWith("/independence/reminders"));
    expect((sent?.body as { user_ids?: string[] } | undefined)?.user_ids).toHaveLength(1);
  });

  it("b: the NAS matrix under ET 1.295, the SKE designee named", async () => {
    show("b");
    expect(
      await screen.findByText("Assistance drafting the plan financial statements and notes"),
    ).toBeTruthy();
    expect(screen.getByText("Permitted — management takes responsibility")).toBeTruthy();
    expect(screen.getByText("Prepared by Summit Plan Administrators (TPA)")).toBeTruthy();
    expect(screen.getByText("Concluded")).toBeTruthy();
    expect(screen.getAllByText("Not applicable")).toHaveLength(3);
    expect(screen.getByText("Pending 1 team confirmation")).toBeTruthy();
  });

  it("c: the conflict check, Harborline not adverse, cleared by Hannah Leclerc", async () => {
    show("c");
    expect(await screen.findByText("Harborline Trust Company")).toBeTruthy();
    expect(screen.getByText("Not adverse")).toBeTruthy();
    expect(screen.getByText(/^Hannah Leclerc · /)).toBeTruthy();
    expect(screen.getByText("No conflicts · 1 related party noted")).toBeTruthy();
    expect(screen.getByText(/^Searched 7 names across every client/)).toBeTruthy();
  });

  it("d: rotation, EP 5 years, EQR 3, Manager 4; review after 7", async () => {
    show("d");
    expect(await screen.findByText("Margaret Okonkwo")).toBeTruthy();
    expect(screen.getByText(COPY.rotation.note(7))).toBeTruthy();
    for (const years of ["5", "3", "4"]) expect(screen.getByText(years)).toBeTruthy();
  });

  it("e: Ana confirms her own independence with all three statements", async () => {
    const calls = show("e");
    const confirm = await screen.findByRole<HTMLButtonElement>("button", {
      name: COPY.self.confirm,
    });
    expect(confirm.disabled).toBe(true); // nothing ticked yet
    for (const box of screen.getAllByRole("checkbox")) fireEvent.click(box);
    expect(confirm.disabled).toBe(false);
    fireEvent.click(confirm);
    await waitFor(() => {
      expect(toastStore.list()[0]?.text).toMatch(/^Independence confirmed · /);
    });
    const sent = calls.find((c) => c.path.endsWith("/independence/confirm"));
    expect(
      (sent?.body as { statement_codes?: string[] } | undefined)?.statement_codes,
    ).toHaveLength(3);
  });

  it("e: Ana's own view never offers Conclude", async () => {
    show("e");
    await screen.findAllByRole("checkbox");
    expect(concludeButton().disabled).toBe(true);
  });

  it("f: 5 of 5, Margaret concludes through the decision dock", async () => {
    const calls = show("f");
    expect(await screen.findByText("5 of 5 confirmed")).toBeTruthy();
    const conclude = concludeButton();
    await waitFor(() => {
      expect(conclude.disabled).toBe(false);
    });
    fireEvent.click(conclude);
    fireEvent.click(await screen.findByText("Independent"));
    fireEvent.click(screen.getByRole("button", { name: COPY.conclude.confirm }));
    await waitFor(() => {
      expect(calls.some((c) => c.path.endsWith("/independence/conclude"))).toBe(true);
    });
    expect(await screen.findByText(/^Concluded · Margaret Okonkwo · /)).toBeTruthy();
  });

  it("g: the breach banner", async () => {
    show("g");
    expect(await screen.findByText(COPY.banner.breach)).toBeTruthy();
    expect(concludeButton().disabled).toBe(true);
  });

  it("declined: Ana declined with a note; she stays blocked", async () => {
    show("declined");
    expect(await screen.findByText("Declined")).toBeTruthy();
    expect(screen.getByText(COPY.banner.declined("Ana Cruz"))).toBeTruthy();
    expect(screen.getByText(/^Note to the engagement partner: /)).toBeTruthy();
    expect(concludeButton().disabled).toBe(true);
  });
});

describe("CLI-08 acceptance: Conclude is the engagement partner's alone", () => {
  for (const state of ["a", "b", "c", "d", "e", "g", "declined"] as const) {
    it(`${state}: Conclude is disabled for anyone but the engagement partner`, async () => {
      show(state);
      await screen.findAllByText(COPY.title);
      await waitFor(() => {
        if (OPENS[state].tab === "team") expect(concludeButton().disabled).toBe(true);
      });
    });
  }
});

describe("CLI-08 avoid", () => {
  it("never paints pending red and never lets anyone confirm for another", async () => {
    show("a");
    await screen.findByText("4 of 5 confirmed");
    const html = document.body.innerHTML;
    expect(html).not.toMatch(/gradient|emoji/i);
    expect(screen.queryByRole("button", { name: /Confirm for/ })).toBeNull();
    const pending = screen.getByText("Pending");
    expect(pending.closest("[class*='red']")).toBeNull();
  });
});
