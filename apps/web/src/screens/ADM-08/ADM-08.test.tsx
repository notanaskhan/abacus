// ADM-08 · Integration settings (T-01-T40). One test per artboard (a–g) on its fixture scenario,
// plus the row's acceptance: no control lets an agent export or post, and Save stays disabled
// while a mapping conflict exists.
import { client } from "@abacus/api-client/client";
import { toastStore } from "@abacus/ui";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { TAX_TEAM } from "../../fixtures/seed/integration-settings";
import { newQueryClient } from "../../testing/support";
import { ADM08 } from ".";
import { COPY } from "./copy";
import { type Adm08State, OPENS, scenarios } from "./scenarios";

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

function show(state: Adm08State): void {
  restore = installFixtureMode(scenarios[state]);
  const opens = OPENS[state];
  render(
    <QueryClientProvider client={newQueryClient()}>
      <ADM08
        segment={opens.segment}
        mappingOpen={opens.mapping === true}
        testOnOpen={opens.test === true}
      />
    </QueryClientProvider>,
  );
}

function saveButton(): HTMLButtonElement {
  return screen.getByRole<HTMLButtonElement>("button", { name: COPY.save });
}

describe("ADM-08 integration settings", () => {
  it("a · Tax engine: the CCH file bridge, 21 of 21 mapped, three offices, the mirror", async () => {
    show("a");
    const engine = within(await screen.findByRole("region", { name: COPY.engine.title }));
    expect(engine.getByText("{Tax year}{Type}:{Client code}:V{n}")).toBeTruthy();
    expect(TAX_TEAM.length).toBe(21);
    expect(engine.getByText(COPY.engine.usersMapped(21, 21))).toBeTruthy();
    for (const office of ["CHI-01 · Chicago", "DEN-01 · Denver", "NYC-01 · New York"]) {
      expect(engine.getByText(office)).toBeTruthy();
    }
    const mirror = within(screen.getByRole("region", { name: COPY.mirror.title }));
    expect(mirror.getByText("Awaiting 8879")).toBeTruthy();
    expect(mirror.getByText(COPY.mirror.footer)).toBeTruthy();
    expect(saveButton().disabled).toBe(true);
  });

  it("a · dirty state: a change enables Save and Discard restores", async () => {
    show("a");
    const toggle = await screen.findByRole("switch", { name: COPY.engine.rules.read_diagnostics });
    fireEvent.click(toggle);
    expect(saveButton().disabled).toBe(false);
    fireEvent.click(screen.getByRole("button", { name: COPY.discard }));
    expect(saveButton().disabled).toBe(true);
  });

  it("b · Ledgers: human-approved batches only, attest clients locked", async () => {
    show("b");
    const ledgers = within(await screen.findByRole("region", { name: COPY.ledgers.title }));
    expect(
      ledgers.getByText("Posting disabled — clients book proposed entries themselves"),
    ).toBeTruthy();
    expect(
      ledgers.getByText("Granite Peak Outdoor Supply, Inc. (attest · posting off)"),
    ).toBeTruthy();
    const post = ledgers.getByRole<HTMLButtonElement>("switch", {
      name: COPY.ledgers.rows.post_only_approved,
    });
    expect(post.disabled || post.getAttribute("aria-disabled") === "true").toBe(true);
  });

  it("c · Mailboxes", async () => {
    show("c");
    expect(
      await screen.findByText("docs@brightwaterhale.com — Microsoft 365 · connected"),
    ).toBeTruthy();
    expect(screen.getByText("4 ›")).toBeTruthy();
  });

  it("d · Test connection passes with a toast", async () => {
    show("d");
    expect(await screen.findByText(COPY.testPassed(3))).toBeTruthy();
    await waitFor(() => {
      expect(toastStore.list().map((t) => t.text)).toContain(COPY.testPassedToast);
    });
  });

  it("e · Sage Intacct test fails: Needs reauth and Send reconnect request", async () => {
    show("e");
    expect(await screen.findByText(COPY.testFailed("HTTP 403 · permission denied"))).toBeTruthy();
    expect(screen.getAllByText(COPY.ledgers.needsReauth).length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: COPY.ledgers.reconnect })).toBeTruthy();
    expect(screen.getByText(COPY.ledgers.failedHelp)).toBeTruthy();
  });

  it("f · a mapping conflict keeps Save disabled even when dirty", async () => {
    show("f");
    expect(await screen.findByText(COPY.mirror.conflict)).toBeTruthy();
    fireEvent.click(screen.getByRole("switch", { name: COPY.engine.rules.read_diagnostics }));
    expect(saveButton().disabled).toBe(true);
  });

  it("g · Edit mapping: the 21 tax users with their CCH staff IDs", async () => {
    show("g");
    const drawer = within(await screen.findByRole("dialog", { name: COPY.drawer.title }));
    const users = drawer.getByRole("list", { name: COPY.engine.usersTitle });
    expect((await within(users).findAllByRole("listitem")).length).toBe(21);
  });

  it("no control lets an agent export or post", async () => {
    show("a");
    await screen.findByRole("region", { name: COPY.engine.title });
    const words = screen.getAllByRole("button").map((b) => b.textContent);
    for (const word of words) {
      expect(word).not.toMatch(/^(Export|Post|Approve|Release|Send|Decide)\b/);
    }
    expect(JSON.stringify(COPY)).not.toMatch(/(Accrued|Agent) (exports|posts|transmits|files)/);
  });
});
