// N-04-T20 (TASK-3322): NOT-03 in fixture mode. Row: "Scenario tests for a-g and d2 pass, every amount
// equals NOT-02, and no control lets anyone but a person approve, send for signature or mark sent."
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { NOT02_NOTICE, not02Notice } from "../../fixtures/seed/not02";
import { newQueryClient } from "../../testing/support";
import { ResponseEditor } from "./Response";
import { type Not03State, scenarios, STATES } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

function show(state: Not03State): { onApprove: ReturnType<typeof vi.fn> } {
  const onApprove = vi.fn();
  restore = installFixtureMode(scenarios[state]);
  render(
    <QueryClientProvider client={newQueryClient()}>
      <ResponseEditor noticeId={NOT02_NOTICE} notice={not02Notice("c")} onApprove={onApprove} />
    </QueryClientProvider>,
  );
  return { onApprove };
}

const drawn = (selector: string): Promise<HTMLElement> =>
  waitFor(
    () => {
      const found = document.querySelector<HTMLElement>(selector);
      expect(found).not.toBeNull();
      return found as HTMLElement;
    },
    { timeout: 6000 },
  );

describe("NOT-03", () => {
  it("has a scenario for a to g and d2", () => {
    expect(STATES).toEqual(["a", "b", "c", "d", "d2", "e", "f", "g"]);
  });

  it("a: the total equals NOT-02, the watermark shows and Approve only opens the sign-off", async () => {
    const { onApprove } = show("a");
    expect((await drawn("[data-not03='total']")).textContent).toContain("753.01");
    expect(document.querySelector("[data-document='watermark']")).not.toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Approve…" }));
    expect(onApprove).toHaveBeenCalledTimes(1);
  });

  it("b: approved has no watermark and offers the signature", async () => {
    show("b");
    await drawn("[data-readiness='approved']");
    expect(document.querySelector("[data-document='watermark']")).toBeNull();
    expect(screen.getByRole("button", { name: "Send for client signature…" })).toBeTruthy();
  });

  it("c: out for signature is waiting, with no approve or send control", async () => {
    show("c");
    expect((await drawn("[data-not03='waiting']")).textContent).toContain("Waiting on Marcus and Dana");
    expect(screen.queryByRole("button", { name: "Mark as sent…" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Approve…" })).toBeNull();
  });

  it("d, d2: ready to send opens the sheet", async () => {
    show("d2");
    await drawn("[data-readiness='ready_to_send']");
    fireEvent.click(screen.getByRole("button", { name: "Mark as sent…" }));
    expect(await drawn("[data-not03='mark-sent']")).toBeTruthy();
  });

  it("e: sent is locked and logs the reply", async () => {
    show("e");
    await drawn("[data-readiness='sent']");
    expect(screen.getByRole("button", { name: "Log IRS reply…" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Regenerate" })).toBeNull();
  });

  it("g: approval is blocked with its reason in text", async () => {
    show("g");
    expect((await drawn("[data-not03='blocked']")).textContent).toContain("partner's decision");
    expect((screen.getByRole("button", { name: "Approve…" }) as HTMLButtonElement).disabled).toBe(true);
  });
});
