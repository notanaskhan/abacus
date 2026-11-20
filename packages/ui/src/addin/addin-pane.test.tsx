// F-08-T17 (TASK-8849; F-08 §E1; T22 a–g): "T22a to T22g render at 350 px with one primary per card,
// Sign-off disabled offline, and 'Sign off again as <name>...' only opening the dialog."
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, describe, expect, it, vi } from "vitest";
import { installDomShims } from "../test-dom";
import { ADDIN_W, AddinPane, type AddinPaneProps } from "./AddinPane";

installDomShims();
afterEach(cleanup);
const HERE = dirname(fileURLToPath(import.meta.url));

function props(over: Partial<AddinPaneProps> = {}): AddinPaneProps {
  return {
    host: "excel",
    signedIn: true,
    firmName: "Brightwater Hale",
    context: "Client · FY · workbook",
    initials: "MD",
    tab: "Link",
    syncedAt: "9:24 AM",
    signOff: { state: "open" },
    changes: [],
    ...over,
  };
}

function primaries(): number[] {
  return [...document.querySelectorAll("[data-addin-card]")].map(
    (card) =>
      [...card.querySelectorAll("button")].filter((b) => b.className.includes("bg-ink")).length,
  );
}

describe("AddinPane C-39 (F-08-T17)", () => {
  it("a: 350 px, Link asks for a cell, one primary per card", () => {
    render(<AddinPane {...props()} />);
    expect(ADDIN_W).toBe(350);
    expect(document.querySelector("[data-addin]")?.getAttribute("style")).toContain("350px");
    expect(screen.getByText("Select a cell to link it to evidence.")).toBeTruthy();
    expect(primaries().every((n) => n <= 1)).toBe(true);
  });

  it("b: a linked cell names its evidence", () => {
    render(
      <AddinPane
        {...props({
          selection: { cell: "D14", linked: { file: "Bank_statement_Sep.pdf", page: 2 } },
        })}
      />,
    );
    expect(screen.getByText("Bank_statement_Sep.pdf · p.2")).toBeTruthy();
  });

  it("c: signed out reads the SSO card with the firm's name from branding", () => {
    render(<AddinPane {...props({ signedIn: false, firmName: "Brightwater Hale" })} />);
    expect(screen.getByText("Sign in to Accrued")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Sign in with Brightwater Hale SSO" })).toBeTruthy();
  });

  it("d: offline shows the bar, Last synced, queued intents and disables Sign-off", () => {
    render(<AddinPane {...props({ offline: true, queued: 2, tab: "Sign-off" })} />);
    expect(screen.getByText("Offline · changes sync when you reconnect")).toBeTruthy();
    expect(screen.getByText("Last synced 9:24 AM")).toBeTruthy();
    expect(screen.getByText("2 changes waiting to sync")).toBeTruthy();
    expect(screen.getByRole<HTMLButtonElement>("button", { name: "Sign off…" }).disabled).toBe(
      true,
    );
  });

  it("e: changed after sign-off: stale slot and 'Sign off again as' only opens the dialog", () => {
    const onOpenSignOff = vi.fn();
    render(
      <AddinPane
        {...props({
          tab: "Sign-off",
          signOff: { state: "stale", signer: "Marcus Delaney", initials: "MD" },
          changes: [
            { cell: "F12", by: "Cole Hart", from: "1,200", to: "1,250" },
            { cell: "F13", by: "Cole Hart", from: "800", to: "820" },
          ],
          onOpenSignOff,
        })}
      />,
    );
    expect(document.querySelector('[data-slot="stale"]')?.textContent).toContain("!");
    fireEvent.click(screen.getByRole("button", { name: "Sign off again as Marcus Delaney…" }));
    expect(onOpenSignOff).toHaveBeenCalledTimes(1);
  });

  it("f: signed off and locked disables actions", () => {
    render(
      <AddinPane {...props({ tab: "Sign-off", signOff: { state: "locked", initials: "MD" } })} />,
    );
    expect(screen.getByText("Signed off · locked")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Sign off/u })).toBeNull();
  });

  it("g: Word host lists incoming changes with Update document", () => {
    const onUpdateDocument = vi.fn();
    render(
      <AddinPane
        {...props({
          host: "word",
          incoming: [
            { cell: "Note 5", by: "Accrued", from: "1,630,000", to: "1,640,000" },
            { cell: "Balance sheet", by: "Accrued", from: "7,466,200", to: "7,476,200" },
            { cell: "Note 7", by: "Accrued", from: "68,400", to: "70,100" },
          ],
          onUpdateDocument,
        })}
      />,
    );
    expect(screen.getByText("Incoming changes (3)")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Update document" }));
    expect(onUpdateDocument).toHaveBeenCalled();
  });

  it("imports no Office.js", () => {
    expect(readFileSync(join(HERE, "AddinPane.tsx"), "utf8")).not.toMatch(
      /from ["'](office|@microsoft\/office-js)|require\(["']office/u,
    );
  });
});
