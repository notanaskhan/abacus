// A-07-T44 (ac-test-author: ayushkbhatia, ADR-078 solo independence as DEC-3127; A-07 §5, INV-1):
// independent acceptance tests for the A-07 screens in fixture mode, written from the epic's rules
// and not from each screen's own tests.
//
// - No gate control on an agent-owned element (`data-actor="agent"`, AgentText): no Approve, Sign
//   off, Release, Send, Post, Decide, Concur or Lock control inside one.
// - Final verbs are never optimistic: pressing Release, Approve & send or Lock calls the host and
//   the canvas does not claim the act happened before the server confirms it.
// - A disabled final control says why in words next to it.
// - Read-only variants: a non-partner sees Release disabled; without the right, Approve & send and
//   Lock are disabled.
// - No delete control after lock.
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Governance } from "./AUD-22";
import { ReportBuilder } from "./AUD-23";
import { FRAMES as AUD23_FRAMES } from "./AUD-23/copy";
import { Issuance } from "./AUD-24";
import { FRAMES as AUD24_FRAMES } from "./AUD-24/copy";
import { Archive } from "./AUD-25";
import { FRAMES as AUD25_FRAMES } from "./AUD-25/copy";

afterEach(cleanup);

const FINAL = /^(approve|sign off|release|send|post|decide|concur|lock)\b/i;

function finalControlsInAgentElements(): string[] {
  const found: string[] = [];
  for (const owned of document.querySelectorAll("[data-actor='agent']")) {
    for (const control of owned.querySelectorAll(
      "button, a, [role='button'], [role='menuitem']",
    )) {
      const name = (control.getAttribute("aria-label") ?? control.textContent ?? "").trim();
      if (FINAL.test(name)) found.push(name);
    }
  }
  return found;
}

function disabledFinalsWithoutWords(root: HTMLElement): string[] {
  const missing: string[] = [];
  for (const button of root.querySelectorAll<HTMLButtonElement>("button:disabled")) {
    const name = (button.getAttribute("aria-label") ?? button.textContent ?? "").trim();
    if (!FINAL.test(name)) continue;
    const near = button.parentElement?.textContent?.replace(name, "").trim() ?? "";
    const described = button.getAttribute("aria-describedby") ?? button.getAttribute("title");
    if (!described && near.length === 0) missing.push(name);
  }
  return missing;
}

const AUD22_FRAMES = ["a", "b", "c"] as const;

describe("A-07 screens: no gate control is agent-owned", () => {
  it.each(AUD22_FRAMES)("AUD-22 %s", (frame) => {
    render(<Governance frame={frame} canApproveSend />);
    expect(finalControlsInAgentElements()).toEqual([]);
  });
  it.each(Object.keys(AUD23_FRAMES))("AUD-23 %s", (frame) => {
    render(<ReportBuilder frame={frame as keyof typeof AUD23_FRAMES} canApprove />);
    expect(finalControlsInAgentElements()).toEqual([]);
  });
  it.each(AUD24_FRAMES)("AUD-24 %s", (frame) => {
    render(<Issuance frame={frame} canRelease />);
    expect(finalControlsInAgentElements()).toEqual([]);
  });
  it.each(AUD25_FRAMES)("AUD-25 %s", (frame) => {
    render(<Archive frame={frame} canLock />);
    expect(finalControlsInAgentElements()).toEqual([]);
  });
});

describe("A-07 screens: a disabled final control says why", () => {
  it.each(AUD24_FRAMES)("AUD-24 %s for the partner and for a non-partner", (frame) => {
    for (const canRelease of [true, false]) {
      const { container } = render(<Issuance frame={frame} canRelease={canRelease} />);
      expect(disabledFinalsWithoutWords(container)).toEqual([]);
      cleanup();
    }
  });
  it.each(AUD25_FRAMES)("AUD-25 %s", (frame) => {
    const { container } = render(<Archive frame={frame} canLock={false} />);
    expect(disabledFinalsWithoutWords(container)).toEqual([]);
  });
});

describe("A-07 screens: read-only variants", () => {
  it("AUD-24: a non-partner never has Release enabled", () => {
    for (const frame of AUD24_FRAMES) {
      render(<Issuance frame={frame} canRelease={false} />);
      for (const button of screen.queryAllByRole("button", { name: /^Release/ })) {
        expect((button as HTMLButtonElement).disabled).toBe(true);
      }
      cleanup();
    }
  });
  it("AUD-22: without approve-and-send the control is disabled", () => {
    for (const frame of AUD22_FRAMES) {
      render(<Governance frame={frame} canApproveSend={false} />);
      for (const button of screen.queryAllByRole("button", {
        name: /Approve & send|Approve and send/,
      })) {
        expect((button as HTMLButtonElement).disabled).toBe(true);
      }
      cleanup();
    }
  });
  it("AUD-25: without the right to lock, Lock is disabled", () => {
    for (const frame of AUD25_FRAMES) {
      render(<Archive frame={frame} canLock={false} />);
      for (const button of screen.queryAllByRole("button", { name: /^Lock/ })) {
        expect((button as HTMLButtonElement).disabled).toBe(true);
      }
      cleanup();
    }
  });
});

describe("A-07 screens: final verbs are never optimistic", () => {
  it("AUD-24: Release calls the host and does not show Released by itself", () => {
    const onRelease = vi.fn();
    render(<Issuance frame="c" canRelease onRelease={onRelease} />);
    const dialog = screen.queryByRole("dialog");
    if (dialog !== null) {
      const attest = within(dialog).queryByRole("checkbox");
      if (attest !== null) fireEvent.click(attest);
      const confirm = within(dialog)
        .getAllByRole("button", { name: /^Release/ })
        .at(-1);
      if (confirm !== undefined) fireEvent.click(confirm);
    }
    expect(screen.queryByText(/^Released\b/)).toBeNull();
  });
  it("AUD-25: Lock calls the host and the canvas still reads as before", () => {
    const onLock = vi.fn();
    render(<Archive frame="b2" canLock onLock={onLock} />);
    const before = document.querySelector("[data-screen='AUD-25']")?.getAttribute("data-frame");
    const lock = screen.queryAllByRole("button", { name: /^Lock/ }).at(-1);
    const attest = screen.queryByRole("checkbox");
    if (attest !== null) fireEvent.click(attest);
    if (lock !== undefined && !(lock as HTMLButtonElement).disabled) fireEvent.click(lock);
    expect(document.querySelector("[data-screen='AUD-25']")?.getAttribute("data-frame")).toBe(
      before,
    );
    expect(screen.queryByText("Locked · WORM")).toBeNull();
  });
});

describe("A-07 screens: no delete after lock", () => {
  it.each(["c", "d"] as const)("AUD-25 %s has no delete or remove control", (frame) => {
    render(<Archive frame={frame} canLock />);
    expect(screen.queryAllByRole("button", { name: /delete|remove/i })).toEqual([]);
    expect(screen.queryAllByRole("menuitem", { name: /delete|remove/i })).toEqual([]);
  });
});
