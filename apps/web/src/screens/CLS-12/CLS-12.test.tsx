// C-02-T48 (TASK-9026; DEC-6031): CLS-12 a, b, c, c2 and d from their scenarios (the Python
// scenario's hand-off facts). Row acceptance: "CLS-12a, b, c, c2 and d render at Tier C and focus
// stays in the sheet until Escape returns it to the menu."
import { client } from "@abacus/api-client/client";
import { toastStore } from "@abacus/ui";
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import {
  type FixtureHandler,
  type Scenario,
  installFixtureMode,
} from "../../app-core/fixture-mode";
import { copperleafAugust } from "../../fixtures/seed/closes";
import { renderRoutes } from "../../testing/support";
import { statusItems } from "../CLS-02/Overview";
import { COPY as C } from "./copy";
import { CLS12 } from "./index";
import { CLS12_DECEMBER_ID, type Cls12State, scenarios } from "./scenarios";

let restore: (() => void) | null = null;

beforeAll(() => {
  client.setConfig({ baseUrl: "http://localhost" });
});

afterEach(() => {
  cleanup();
  toastStore.clear();
  restore?.();
  restore = null;
});

function show(
  state: Cls12State,
  onOpenChange = vi.fn(),
): { posts: string[]; onOpenChange: typeof onOpenChange } {
  const posts: string[] = [];
  const base: Scenario = scenarios[state];
  const handlers = Object.fromEntries(
    Object.entries(base.handlers).map(([key, handler]) => [
      key,
      ((request) => {
        if (request.method === "POST") posts.push(request.path);
        return handler(request);
      }) satisfies FixtureHandler,
    ]),
  );
  restore = installFixtureMode({ ...base, handlers });
  renderRoutes([
    {
      path: "/",
      component: () => (
        <>
          <button type="button">Close status</button>
          <CLS12
            closeId={CLS12_DECEMBER_ID}
            client="Copperleaf Coffee Roasters, Inc."
            open
            onOpenChange={onOpenChange}
          />
        </>
      ),
    },
  ]);
  return { posts, onOpenChange };
}

async function sheet(): Promise<HTMLElement> {
  return screen.findByRole("dialog", { name: C.title });
}

describe("CLS-12 Tax hand-off", () => {
  it("CLS-12a ready: source, target, five schedules on, three items on, one primary", async () => {
    show("a");
    const s = await sheet();
    await waitFor(() => {
      expect(s.querySelectorAll("[data-schedule]")).toHaveLength(5);
    });
    expect(s.textContent).toContain("December 2026 · Locked Jan 11, 2027");
    expect(s.textContent).toContain("TB v1 · year ended Dec 31, 2026");
    expect(s.textContent).toContain("2026 Form 1120-S · Copperleaf Coffee Roasters, Inc.");
    expect(s.textContent).toContain("CCH Axcess Tax");
    expect(s.textContent).toContain("Olivia Brandt (preparer) · Samuel Ito (reviewer)");
    expect(s.textContent).toContain(
      "cost 278,400.00 · accumulated depreciation 74,900.00 · 2026 book depreciation 25,680.00 → Fixed Assets",
    );
    expect(s.textContent).toContain("144,000.00 → Schedule M-2 (AAA)");
    expect(s.querySelectorAll("[data-item]")).toHaveLength(3);
    const switches = within(s).getAllByRole("switch");
    expect(switches).toHaveLength(8);
    expect(switches.every((t) => t.getAttribute("aria-checked") === "true")).toBe(true);
    const primaries = s.querySelectorAll('[data-variant="primary"]');
    expect(primaries).toHaveLength(1);
    expect(within(s).getByRole("button", { name: C.handOff }).hasAttribute("disabled")).toBe(
      false,
    );
  });

  it("CLS-12b not available: the CLS-02 menu item is disabled with the read's reason", () => {
    const items = statusItems(copperleafAugust(), () => undefined, {
      reason: "Available after the December 2026 close locks",
      onOpen: () => undefined,
    });
    const handoff = items.find((i) => i.label === "Handoff to tax…");
    expect(handoff?.disabled).toBe(true);
    expect(handoff?.hint).toBe("Available after the December 2026 close locks");
    const ready = statusItems(copperleafAugust(), () => undefined, {
      reason: null,
      onOpen: () => undefined,
    });
    expect(ready.find((i) => i.label === "Handoff to tax…")?.disabled).toBeFalsy();
  });

  it("CLS-12c hand off: a person's click posts once and the toast names the return and issues", async () => {
    const { posts } = show("a");
    const s = await sheet();
    await waitFor(() => {
      expect(s.querySelectorAll("[data-item]")).toHaveLength(3);
    });
    fireEvent.click(within(s).getByRole("switch", { name: /Square and Shopify/ }));
    expect(posts).toHaveLength(0);
    fireEvent.click(within(s).getByRole("button", { name: C.handOff }));
    await waitFor(() => {
      expect(posts).toHaveLength(1);
    });
    await waitFor(() => {
      expect(toastStore.list().map((t) => t.text)).toContain(
        "Handed off to 2026 Form 1120-S · 2 tax issues created",
      );
    });
  });

  it("CLS-12c2 handed off: TXP-02's provenance banner and Hand off closed", async () => {
    show("c2");
    const s = await sheet();
    const banner = await waitFor(() => {
      const found = s.querySelector<HTMLElement>('[data-cls12="provenance"]');
      if (found === null) throw new Error("no banner");
      return found;
    });
    expect(banner.textContent).toContain(
      "TB from the December 2026 close, locked Jan 11, 2027 · handed off by Priya Raman · Jan 12, 2027, 2:15 PM",
    );
    expect(within(banner).getByRole("button", { name: C.viewClose })).toBeTruthy();
    expect(within(s).getByRole("button", { name: C.handOff }).hasAttribute("disabled")).toBe(true);
  });

  it("CLS-12d superseded: the reopen banner names the tax team", async () => {
    show("d");
    const s = await sheet();
    const banner = await waitFor(() => {
      const found = s.querySelector<HTMLElement>('[data-cls12="superseded"]');
      if (found === null) throw new Error("no banner");
      return found;
    });
    expect(banner.textContent).toBe(
      "The December close was reopened on Jan 20. Handing off again replaces TB v1 and notifies Olivia Brandt and Samuel Ito.",
    );
  });

  it("CLS-12 acceptance: focus stays in the sheet until Escape returns it", async () => {
    const { onOpenChange } = show("a");
    const s = await sheet();
    await waitFor(() => {
      expect(s.contains(document.activeElement)).toBe(true);
    });
    fireEvent.keyDown(document.activeElement ?? s, { key: "Tab" });
    expect(s.contains(document.activeElement)).toBe(true);
    fireEvent.keyDown(document.activeElement ?? s, { key: "Escape" });
    await waitFor(() => {
      expect(onOpenChange).toHaveBeenCalledWith(false);
    });
  });
});
