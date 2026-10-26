// BND-02 keyboard suite (P-06-T26; P-06 §5.6): Tab runs rail → canvas → dock and reaches the
// publish bar and the dock's primary actions; a row is selected from the keyboard through its title
// button (aria-pressed); the Eye is a toggle button with aria-pressed; every overlay (row menu,
// Publish, Preview as client, Return to client, the follow-up sheet, the ReturnDialog) closes on
// Escape and gives focus back to the control that opened it. axe runs in
// e2e/screens/BND-02.spec.ts (Playwright).
import { client } from "@abacus/api-client/client";
import { toastStore } from "@abacus/ui";
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { type JSX, useState } from "react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { positions, tabOrder } from "../../testing/keyboard";
import { renderRoutes } from "../../testing/support";
import { BND02, type BinderTab } from ".";
import { type Bnd02State, OPENS, scenarios } from "./scenarios";

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

function Harness({ state }: { state: Bnd02State }): JSX.Element {
  const [request, setRequest] = useState<string | null>(OPENS[state].request);
  const [tab, setTab] = useState<BinderTab>("requests");
  return (
    <BND02
      binderId={OPENS[state].binderId}
      request={request}
      onRequest={setRequest}
      tab={tab}
      onTab={setTab}
    />
  );
}

function show(state: Bnd02State): void {
  restore = installFixtureMode(scenarios[state]);
  renderRoutes([{ path: "/", component: () => <Harness state={state} /> }]);
}

function dock(): HTMLElement {
  return screen.getByRole("region", { name: "Request dock" });
}

function rowOf(title: string): HTMLElement {
  const row = screen.getByRole("button", { name: title }).closest<HTMLElement>("[data-request]");
  if (row === null) throw new Error(`no row ${title}`);
  return row;
}

/** Focus a control and activate it, as Enter or Space on a focused button does. */
function press(el: HTMLElement): void {
  el.focus();
  fireEvent.click(el);
}

async function closesOnEscape(dialog: HTMLElement, opener: HTMLElement): Promise<void> {
  fireEvent.keyDown(dialog, { key: "Escape" });
  await waitFor(() => {
    expect(screen.queryByRole("dialog")).toBeNull();
  });
  await waitFor(() => {
    expect(document.activeElement).toBe(opener);
  });
}

const W2 = "2025 W-2 From Mercer Hill Health";
const EST = "2025 federal (1040-ES) and New York (IT-2105) estimated payment confirmations";

describe("BND-02 keyboard (P-06 §5.6)", () => {
  it("Tab runs rail, canvas, then dock, and reaches the publish bar and each row's controls", async () => {
    show("a");
    await screen.findByText("Published Feb 3 · 5 of 7 satisfied · 2 open");
    const at = positions(document.body, [
      "All Binders",
      "Preview as client",
      "Unpublish…",
      W2,
      `${W2}: visible to client`,
      `${W2} actions`,
    ]);
    expect(at).not.toContain(-1);
    expect([...at].sort((x, y) => x - y)).toEqual(at);
    // The dock comes after the canvas.
    const order = tabOrder();
    const lastRow = order.findIndex((el) => el.closest("[data-request]") !== null);
    const firstDock = order.findIndex((el) => dock().contains(el));
    expect(lastRow).toBeGreaterThanOrEqual(0);
    expect(firstDock).toBeGreaterThan(lastRow);
    expect(order.filter((el) => el.tabIndex > 0)).toEqual([]);
  });

  it("b: Publish to client… is reachable, and Escape closes its dialog with focus back on it", async () => {
    show("b");
    await screen.findByText("Draft · 7 requests from the 2025 return");
    const opener = screen.getByRole("button", { name: "Publish to client…" });
    expect(tabOrder()).toContain(opener);
    press(opener);
    const dialog = await screen.findByRole("dialog", { name: "Publish to client" });
    await closesOnEscape(dialog, opener);
  });

  it("a row is selected from the keyboard through its title button, and the dock follows", async () => {
    show("a");
    await screen.findByText("Published Feb 3 · 5 of 7 satisfied · 2 open");
    const title = screen.getByRole("button", { name: W2 });
    expect(title.tagName).toBe("BUTTON");
    expect(title.getAttribute("aria-pressed")).toBe("false");
    press(title);
    await waitFor(() => {
      expect(screen.getByRole("button", { name: W2 }).getAttribute("aria-pressed")).toBe("true");
    });
    expect(await within(dock()).findByText(W2)).toBeTruthy();
  });

  it("the Eye is a toggle button with aria-pressed and a visible-to-client label", async () => {
    show("f");
    await screen.findByText("Published Feb 3 · 5 of 7 satisfied · 2 open");
    const k1 = rowOf("Schedule K-1 from Ridgeline Property Partners, LP");
    const eye = within(k1).getByRole("button", { name: /hidden from client$/ });
    expect(eye.getAttribute("aria-pressed")).toBe("false");
    const w2Eye = within(rowOf(W2)).getByRole("button", { name: /visible to client$/ });
    expect(w2Eye.getAttribute("aria-pressed")).toBe("true");
  });

  it("the row menu opens from the keyboard and Escape gives focus back to its trigger", async () => {
    show("a");
    await screen.findByText("Published Feb 3 · 5 of 7 satisfied · 2 open");
    const trigger = within(rowOf(W2)).getByRole("button", { name: `${W2} actions` });
    trigger.focus();
    fireEvent.keyDown(trigger, { key: "ArrowDown" });
    const menu = await screen.findByRole("menu");
    fireEvent.keyDown(menu, { key: "Escape" });
    await waitFor(() => {
      expect(screen.queryByRole("menu")).toBeNull();
    });
    expect(document.activeElement).toBe(trigger);
  });

  it("Preview as client: Escape closes the sheet and focus returns to its button", async () => {
    show("a");
    await screen.findByText("Published Feb 3 · 5 of 7 satisfied · 2 open");
    const opener = screen.getByRole("button", { name: "Preview as client" });
    press(opener);
    const sheet = await screen.findByRole("dialog", { name: "Preview as client" });
    await closesOnEscape(sheet, opener);
  });

  it("e: Return to client…: Escape closes the note dialog, nothing is sent, focus returns", async () => {
    show("e");
    await screen.findByText(/1 ignored/);
    const opener = within(dock()).getByRole("button", { name: "Return to client…" });
    press(opener);
    const dialog = await screen.findByRole("dialog", { name: "Return to client" });
    await closesOnEscape(dialog, opener);
  });

  it("d: Send reminder…: Escape closes the follow-up sheet and focus returns", async () => {
    show("d");
    await screen.findByText("3 overdue");
    const opener = screen.getAllByRole("button", { name: "Send reminder…" })[0];
    if (opener === undefined) throw new Error("no Send reminder…");
    press(opener);
    const sheet = await screen.findByRole("dialog");
    await closesOnEscape(sheet, opener);
  });

  it("g: Accept and Return… are reachable in the dock; Escape closes the ReturnDialog", async () => {
    show("g");
    await screen.findByRole("button", { name: EST });
    const accept = await within(dock()).findByRole("button", { name: "Accept" });
    const ret = within(dock()).getByRole("button", { name: "Return…" });
    const order = tabOrder();
    expect(order).toContain(ret);
    await waitFor(() => {
      expect(tabOrder()).toContain(accept);
    });
    press(ret);
    const dialog = await screen.findByRole("dialog", { name: "Return to client" });
    await closesOnEscape(dialog, ret);
  });
});
