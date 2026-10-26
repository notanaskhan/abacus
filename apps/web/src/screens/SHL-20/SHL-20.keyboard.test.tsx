// SHL-20 keyboard suite (P-06-T26; P-06 §5.6): the screening card is a non-modal O1 card; Escape
// closes it and gives focus back to the screening chip (so does ✕); an overlay opened from the
// card (the ReturnDialog, "Why?") closes on Escape without closing the card; Tab reaches the
// card's actions; "Screening 2 new files…" is polite with aria-busy on the card; the feedback menu
// is a radio group whose Send stays disabled until a reason is chosen. axe for SHL-20 runs in
// e2e/screens/SHL-20.spec.ts (Playwright).
import { client } from "@abacus/api-client/client";
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
// Registers the `?ov=viewer` drawer, as the firm routes do.
import "../../routes/firm/viewer";
import { nameOf, positions } from "../../testing/keyboard";
import { renderRoutes } from "../../testing/support";
import { SHL20 } from "./artboard";
import { type Shl20State, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

function show(state: Shl20State): void {
  restore = installFixtureMode(scenarios[state]);
  renderRoutes([{ path: "/", component: () => <SHL20 state={state} /> }]);
}

/** The card once its aggregate has loaded. */
async function card(): Promise<HTMLElement> {
  const found = await screen.findByRole("region", { name: "Evidence screening" });
  await waitFor(
    () => {
      expect(found.querySelector("[data-verdict]")).not.toBeNull();
    },
    { timeout: 4000 },
  );
  return found;
}

function chip(): HTMLElement {
  const el = document.querySelector<HTMLElement>("[data-screening-chip]");
  if (el === null) throw new Error("no screening chip");
  return el;
}

const STATEMENT = "Granite Rock Logistics — August statement.pdf";

describe("SHL-20 keyboard (P-06 §5.6)", () => {
  it("Escape closes the card and focus returns to the screening chip", async () => {
    show("a");
    const box = await card();
    expect(chip().getAttribute("aria-expanded")).toBe("true");
    const view = within(box).getAllByRole("button", { name: /^View/ })[0];
    if (view === undefined) throw new Error("no View");
    view.focus();
    fireEvent.keyDown(view, { key: "Escape" });
    await waitFor(() => {
      expect(screen.queryByRole("region", { name: "Evidence screening" })).toBeNull();
    });
    expect(document.activeElement).toBe(chip());
    expect(chip().getAttribute("aria-expanded")).toBe("false");
  });

  it("✕ closes the card and focus returns to the chip; the chip opens it again", async () => {
    show("d");
    const box = await card();
    fireEvent.click(within(box).getByRole("button", { name: "Close" }));
    await waitFor(() => {
      expect(screen.queryByRole("region", { name: "Evidence screening" })).toBeNull();
    });
    expect(document.activeElement).toBe(chip());
    fireEvent.click(chip());
    expect(await card()).toBeTruthy();
  });

  it("Tab reaches the card's actions: View and Return… on each flag, then Draft follow-up", async () => {
    show("a");
    const box = await card();
    const at = positions(box, [`View ${STATEMENT}`, `Return… ${STATEMENT}`, "Draft follow-up"]);
    expect(at).not.toContain(-1);
    expect([...at].sort((x, y) => x - y)).toEqual(at);
  });

  it("Return…: Escape closes the dialog, the card stays, focus returns to Return…", async () => {
    show("a");
    const box = await card();
    const opener = within(box).getByRole("button", { name: `Return… ${STATEMENT}` });
    opener.focus();
    fireEvent.click(opener);
    const dialog = await screen.findByRole("dialog", { name: "Return to client" });
    fireEvent.keyDown(dialog, { key: "Escape" });
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).toBeNull();
    });
    await waitFor(() => {
      expect(document.activeElement).toBe(opener);
    });
    expect(screen.getByRole("region", { name: "Evidence screening" })).toBe(box);
  });

  it("f: Why? is a radio group, Send waits for a reason, Escape closes it and keeps the card", async () => {
    show("f");
    const box = await card();
    const group = await screen.findByRole("radiogroup");
    expect(within(group).getAllByRole("radio").map(nameOf)).toEqual([
      "Wrong request match",
      "Wrong period",
      "Unclear file",
      "Other",
    ]);
    const send = screen.getByRole("button", { name: "Send feedback" });
    expect(send.hasAttribute("disabled")).toBe(true);
    fireEvent.keyDown(group, { key: "Escape" });
    await waitFor(() => {
      expect(screen.queryByRole("radiogroup")).toBeNull();
    });
    expect(screen.getByRole("region", { name: "Evidence screening" })).toBe(box);
  });

  it("c: the running card is busy and says so politely", async () => {
    show("c");
    const box = await screen.findByRole("region", { name: "Evidence screening" });
    await waitFor(() => {
      expect(box.getAttribute("aria-busy")).toBe("true");
    });
    const live = box.querySelector("[aria-live='polite']");
    expect(live?.textContent).toMatch(/Screening 2 new files/);
  });
});
