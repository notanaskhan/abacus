// HOME-02 · the queue (I-01-T16). Acceptance: "Scenarios a and f pass Vitest and axe, J/K moves the
// selection with focus announced, and the band counts equal the HOME-01 badge." Axe runs in the end
// review's gallery sweep; here a, f, the keyboard, `?gate=`, Show done and the read-only rule.
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { type FixtureHandler, installFixtureMode } from "../../app-core/fixture-mode";
import { newQueryClient } from "../../testing/support";
import { HOME02 } from ".";
import { COPY } from "./copy";
import { type Home02State, scenarios } from "./scenarios";

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
  queries: string[];
}

function show(
  state: Home02State,
  props: { gate?: string | null; onGate?: (g: string | null) => void } = {},
): Seen {
  const seen: Seen = { queries: [] };
  const scenario = scenarios[state];
  const handlers = Object.fromEntries(
    Object.entries(scenario.handlers).map(([key, handler]) => [
      key,
      ((request) => {
        if (request.path === "/v1/human-gates") seen.queries.push(request.query.toString());
        return handler(request);
      }) satisfies FixtureHandler,
    ]),
  );
  restore = installFixtureMode({ ...scenario, handlers });
  render(
    <QueryClientProvider client={newQueryClient()}>
      <HOME02 {...props} />
    </QueryClientProvider>,
  );
  return seen;
}

function rows(): HTMLButtonElement[] {
  return [...document.querySelectorAll<HTMLButtonElement>("[data-issue-row]")];
}

async function queue(): Promise<HTMLElement> {
  return screen.findByRole("navigation", { name: COPY.queue });
}

describe("HOME-02 queue", () => {
  it("a: Decisions 3 · Sign-offs 6 · Approvals & sends 2, the counts endpoint's numbers = the badge", async () => {
    show("a");
    const q = await queue();
    const bands = within(q)
      .getAllByRole("region")
      .map((r) => r.getAttribute("aria-label"));
    expect(bands).toEqual(["Decisions", "Sign-offs", "Approvals & sends"]);
    const text = q.textContent;
    expect(text).toContain("Decisions3");
    expect(text).toContain("Sign-offs6");
    expect(text).toContain("Approvals & sends2");
    expect(rows()).toHaveLength(11);
    // The badge is the Approvals segment's count, the same counts response.
    expect(screen.getByRole("tab", { name: /Approvals/u }).textContent).toContain("11");
  });

  it("a: the first decision is selected; blocked rows say Blocked in words with the triangle", async () => {
    show("a");
    await queue();
    expect(rows()[0]?.getAttribute("aria-current")).toBe("true");
    expect(rows()[0]?.textContent).toContain("§754 election");
    const blocked = rows().filter((r) => r.querySelector('[aria-label="Blocked"]') !== null);
    expect(blocked.length).toBeGreaterThan(0);
    for (const r of blocked) expect(r.textContent).toContain("Blocked");
  });

  it("a: the queue is links only: no decide, approve, sign-off or send control", async () => {
    show("a");
    await queue();
    for (const name of [/^Decide/u, /^Approve/u, /^Sign off/u, /^Send/u, /^Release/u]) {
      expect(screen.queryByRole("button", { name })).toBeNull();
    }
  });

  it("f: Nothing waiting on you, with Show done", async () => {
    show("f");
    expect(await screen.findByText(COPY.empty)).toBeTruthy();
    const showDone = screen.getAllByRole("button", { name: COPY.showDone });
    expect(showDone.length).toBeGreaterThan(0);
  });

  it("J and K move the selection, focus the row and announce it", async () => {
    const gates: (string | null)[] = [];
    show("a", { onGate: (g) => gates.push(g) });
    await queue();
    const first = rows()[0] as HTMLButtonElement;
    first.focus();
    fireEvent.keyDown(first, { key: "j" });
    await waitFor(() => {
      expect(rows()[1]?.getAttribute("aria-current")).toBe("true");
    });
    expect(document.activeElement).toBe(rows()[1]);
    expect(screen.getByText(/^Selected: CP2000 position/u)).toBeTruthy();
    fireEvent.keyDown(rows()[1] as HTMLButtonElement, { key: "k" });
    await waitFor(() => {
      expect(rows()[0]?.getAttribute("aria-current")).toBe("true");
    });
    expect(gates.length).toBe(2);
  });

  it("?gate= selects that row", async () => {
    show("a");
    await queue();
    const third = rows()[2]?.getAttribute("data-issue-row") ?? "";
    cleanup();
    restore?.();
    show("a", { gate: third });
    await queue();
    expect(rows()[2]?.getAttribute("aria-current")).toBe("true");
  });

  it("Show done asks for state=done", async () => {
    const seen = show("a");
    await queue();
    fireEvent.click(screen.getByRole("button", { name: COPY.showDone }));
    await waitFor(() => {
      expect(seen.queries.some((q) => q.includes("state=done"))).toBe(true);
    });
  });
});
