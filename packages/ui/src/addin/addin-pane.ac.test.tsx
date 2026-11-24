// ac-test-author: notanaskhan
// F-08-T20 (TASK-8937; F-08 §3 E1, E2; ADR-078; DEC-5939): the add-in pane's promises, black-box
// over its public props and rendered output: no sign-off fires without a named human click, offline
// disables Sign-off, Changes lists exactly the changed cells, and the signed-out copy takes the
// firm name from branding data (DF-30). Expectations are the epic's words, not the component's.
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { installDomShims } from "../test-dom";
import { AddinPane, type AddinPaneProps } from "./index";

beforeAll(() => {
  installDomShims();
});

afterEach(cleanup);

const CHANGES = [
  { cell: "F12", by: "Cole Hart", from: "3,962,400", to: "3,972,400" },
  { cell: "F13", by: "Cole Hart", from: "217,600", to: "207,600" },
  { cell: "F14", by: "Cole Hart", from: "4,180,000", to: "4,180,000" },
] as const;

function props(over: Partial<AddinPaneProps> = {}): AddinPaneProps {
  return {
    host: "excel",
    signedIn: true,
    firmName: "Brightwater Hale",
    context: "Granite Peak · FY2026 · AP leadsheet",
    initials: "CH",
    tab: "Sign-off",
    syncedAt: "2:14 PM",
    signOff: { state: "open", signer: "Cole Hart", initials: "CH" },
    changes: [],
    ...over,
  };
}

function buttons(): HTMLButtonElement[] {
  return screen.queryAllByRole<HTMLButtonElement>("button");
}

describe("F-08 E1 add-in pane (independent)", () => {
  it("test_ac_e1_no_sign_off_fires_without_a_named_human_click", () => {
    const onOpenSignOff = vi.fn();
    render(<AddinPane {...props({ onOpenSignOff })} />);
    // Rendering, switching nothing and hovering never open the sign-off.
    expect(onOpenSignOff).not.toHaveBeenCalled();
    const signers = buttons().filter((b) => /^Sign off/u.test(b.textContent));
    expect(signers.length).toBeGreaterThan(0);
    for (const b of signers) {
      // A sign-off control opens the named person's dialog ("…"); it never signs on its own
      // (INV-1, INV-5). The name is in the label where the epic says so ("Sign off again as …").
      expect(b.textContent).toMatch(/…$/u);
    }
    fireEvent.click(signers[0] as HTMLButtonElement);
    expect(onOpenSignOff).toHaveBeenCalledTimes(1);
  });

  it("test_ac_e1_sign_off_again_only_opens_the_dialog", () => {
    const onOpenSignOff = vi.fn();
    const onTickmark = vi.fn();
    const onUpdateDocument = vi.fn();
    render(
      <AddinPane
        {...props({
          signOff: { state: "stale", signer: "Cole Hart", initials: "CH" },
          changes: CHANGES,
          onOpenSignOff,
          onTickmark,
          onUpdateDocument,
        })}
      />,
    );
    const again = buttons().find((b) => b.textContent.startsWith("Sign off again as Cole Hart"));
    expect(again).toBeDefined();
    fireEvent.click(again as HTMLButtonElement);
    expect(onOpenSignOff).toHaveBeenCalledTimes(1);
    expect(onTickmark).not.toHaveBeenCalled();
    expect(onUpdateDocument).not.toHaveBeenCalled();
  });

  it("test_ac_e1_offline_disables_sign_off", () => {
    const onOpenSignOff = vi.fn();
    render(<AddinPane {...props({ offline: true, queued: 2, onOpenSignOff })} />);
    expect(screen.getByText("Offline · changes sync when you reconnect")).toBeTruthy();
    expect(document.body.textContent).toContain("2 changes waiting to sync");
    expect(document.body.textContent).toMatch(/Last synced/u);
    const signers = buttons().filter((b) => /^Sign off/u.test(b.textContent));
    for (const b of signers) {
      expect(b.disabled).toBe(true);
      fireEvent.click(b);
    }
    expect(onOpenSignOff).not.toHaveBeenCalled();
  });

  it("test_ac_e1_changes_equals_the_changed_cells", () => {
    render(<AddinPane {...props({ tab: "Changes", changes: CHANGES })} />);
    const text = document.body.textContent;
    for (const c of CHANGES) expect(text).toContain(c.cell);
    // Exactly the changed cells: no other cell reference is listed.
    const cells = new Set(text.match(/\b[A-Z]{1,2}\d{1,4}\b/gu) ?? []);
    for (const ref of cells) {
      if (/^F1[2-4]$/u.test(ref)) continue;
      // Words such as "FY2026" are not cells; any other A1 reference would be a stray change.
      expect(["FY2026"]).toContain(ref);
    }
  });

  it("test_ac_e1_signed_out_copy_comes_from_branding_data", () => {
    const onSignIn = vi.fn();
    const { rerender } = render(
      <AddinPane {...props({ signedIn: false, firmName: "Brightwater Hale", onSignIn })} />,
    );
    expect(screen.getByText("Sign in to Accrued")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Sign in with Brightwater Hale SSO" })).toBeTruthy();
    rerender(
      <AddinPane {...props({ signedIn: false, firmName: "Harlow Pike CPAs", onSignIn })} />,
    );
    expect(screen.getByRole("button", { name: "Sign in with Harlow Pike CPAs SSO" })).toBeTruthy();
    expect(document.body.textContent).not.toContain("Brightwater Hale");
  });

  it("test_ac_e1_one_primary_per_card", () => {
    render(<AddinPane {...props({ tab: "Sign-off", changes: CHANGES })} />);
    for (const card of document.querySelectorAll("section")) {
      const primaries = within(card)
        .queryAllByRole("button")
        .filter((b) => b.getAttribute("data-variant") === "primary");
      expect(primaries.length).toBeLessThanOrEqual(1);
    }
  });
});

describe("F-08 E2 specimen hosts never ship", () => {
  it("test_ac_e2_host_chrome_is_not_exported_from_the_main_entry", async () => {
    const main: Record<string, unknown> = await import("../index");
    for (const name of ["HostWindow", "ExcelGrid", "WordPage"]) {
      expect(main[name]).toBeUndefined();
    }
  });
});
