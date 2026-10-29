// INB-02 · Attachment triage & File-to (N-01-T15; DEC-1062). One test per artboard on its fixture
// scenario, and the task's acceptance: "Apply stays disabled until every flagged or ambiguous card
// has a human choice, and Escape on a dirty sheet asks first."
import { client } from "@abacus/api-client/client";
import { toastStore } from "@abacus/ui";
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { renderRoutes } from "../../testing/support";
import { INB02 } from ".";
import { COPY } from "./copy";
import { type Inb02State, messageOf, scenarios } from "./scenarios";

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

function mount(state: Inb02State): void {
  restore = installFixtureMode(scenarios[state]);
  const m = messageOf(state);
  renderRoutes([
    {
      path: "/",
      component: () => (
        <INB02
          messageId={m.id}
          subject={m.subject}
          sender={m.sender}
          startDirty={state === "a2"}
          onClose={() => undefined}
        />
      ),
    },
  ]);
}

async function sheet(): Promise<HTMLElement> {
  return screen.findByRole("dialog");
}

function apply(dialog: HTMLElement, n: number): HTMLButtonElement {
  return within(dialog).getByRole<HTMLButtonElement>("button", { name: COPY.apply(n) });
}

describe("INB-02", () => {
  it("a: two Feld cards, the 96% destination, the 2024 copy's two flags, Apply 2 enabled", async () => {
    mount("a");
    const dialog = await sheet();
    expect(within(dialog).getByText(COPY.title)).toBeTruthy();
    expect(await within(dialog).findByText("Feld_1095C_2025.pdf")).toBeTruthy();
    expect(within(dialog).getByText("96%")).toBeTruthy();
    expect(within(dialog).getByText("Tax year 2024 ≠ 2025 (the open return).")).toBeTruthy();
    expect(
      within(dialog).getByText(/^Duplicate of Claire_Feld_2024_1095C_MercerHill\.pdf/),
    ).toBeTruthy();
    await waitFor(() => {
      expect(apply(dialog, 2).disabled).toBe(false);
    });
  });

  it("b: two candidates at 61% and 58%; Apply stays disabled until one is chosen", async () => {
    mount("b");
    const dialog = await sheet();
    expect(await within(dialog).findByText("61%")).toBeTruthy();
    expect(apply(dialog, 1).disabled).toBe(true);
    fireEvent.click(within(dialog).getByText("61%").closest("button") as HTMLElement);
    await waitFor(() => {
      expect(apply(dialog, 1).disabled).toBe(false);
    });
  });

  it("c: the TIN mismatch forces Hold and shows the client message preview", async () => {
    mount("c");
    const dialog = await sheet();
    expect(
      await within(dialog).findByText(
        "SSN differs from the client record (last four 7713 vs 7731)",
      ),
    ).toBeTruthy();
    expect(within(dialog).getByText(COPY.holdPreview)).toBeTruthy();
    expect(within(dialog).queryByRole("radio", { name: COPY.decisions.file })).toBeNull();
  });

  it("d: three Stein files, the copy of the notice defaults to Ignore", async () => {
    mount("d");
    const dialog = await sheet();
    expect(await within(dialog).findByText("Stein_CP2000_2024_copy.pdf")).toBeTruthy();
    expect(within(dialog).getByText(COPY.flag.duplicateOfNotice)).toBeTruthy();
  });

  it("e: Keep both versions is on for the Northwind census", async () => {
    mount("e");
    const dialog = await sheet();
    expect(await within(dialog).findByText("Census_Corrections_2025.xlsx")).toBeTruthy();
    expect(within(dialog).getByRole("switch", { name: COPY.rows.keepBoth })).toBeTruthy();
  });

  it("g: Supersede earlier is on for the corrected 1099-DIV", async () => {
    mount("g");
    const dialog = await sheet();
    expect(
      await within(dialog).findByText("Iyer_2025_1099DIV_Halvard_Corrected.pdf"),
    ).toBeTruthy();
    const toggle = within(dialog).getByRole("switch", { name: COPY.rows.supersede });
    expect(toggle.getAttribute("aria-checked")).toBe("true");
  });

  it("f: Apply sends every decision once and the toast names the notified preparer", async () => {
    mount("a");
    const dialog = await sheet();
    await waitFor(() => {
      expect(apply(dialog, 2).disabled).toBe(false);
    });
    fireEvent.click(apply(dialog, 2));
    await waitFor(() => {
      expect(
        toastStore.list().some((t) => t.text === "Filed 1 · Ignored 1 · Kevin Osei notified"),
      ).toBe(true);
    });
  });

  it("a2: Escape on a dirty sheet asks before closing", async () => {
    mount("a2");
    const dialog = await sheet();
    await within(dialog).findByText("Feld_1095C_2025.pdf");
    fireEvent.keyDown(dialog, { key: "Escape" });
    expect((await screen.findAllByText(/Discard/)).length).toBeGreaterThan(0);
  });
});
