// SHL-12 f · Bulk sign-off (P-04-T49): "Bulk shows Sign off 3 as Reviewer (L2) with 3 excluded rows
// and their reasons, and clicking any slot opens SHL-12." The sheet reads each workpaper's
// eligibility at L2, excludes the ineligible ones in words, signs only on the person's click, and
// shows each item's result.
import { client } from "@abacus/api-client/client";
import { toastStore } from "@abacus/ui";
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { type FixtureHandler, installFixtureMode } from "../../app-core/fixture-mode";
import { renderRoutes } from "../../testing/support";
import { BulkSignOffSheet } from ".";
import { BULK, scenarios } from "./scenarios";

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

interface Call {
  method: string;
  path: string;
  body: unknown;
}

function showBulk(): Call[] {
  const calls: Call[] = [];
  const scenario = scenarios.f;
  const handlers = Object.fromEntries(
    Object.entries(scenario.handlers).map(([key, handler]) => [
      key,
      ((request) => {
        calls.push({ method: request.method, path: request.path, body: request.body });
        return handler(request);
      }) satisfies FixtureHandler,
    ]),
  );
  restore = installFixtureMode({ ...scenario, handlers });
  renderRoutes([
    {
      path: "/",
      component: () => (
        <BulkSignOffSheet
          targets={BULK}
          level="L2_reviewer"
          meta="Northwind · PY2025"
          context="Planning 5 of 6 · SOC 1 waiting on inputs"
          open
          onOpenChange={() => undefined}
        />
      ),
    },
  ]);
  return calls;
}

describe("SHL-12 f: bulk", () => {
  it("excludes three in words and offers Sign off 3 as Reviewer (L2)", async () => {
    const calls = showBulk();
    const cta = await screen.findByRole<HTMLButtonElement>("button", {
      name: "Sign off 3 as Reviewer (L2)",
    });
    expect(cta.disabled).toBe(false);
    expect(screen.getByText("Sign off 6 workpapers")).toBeTruthy();
    const excluded = document.querySelectorAll("[data-excluded]");
    expect(excluded).toHaveLength(3);
    expect([...excluded].map((r) => r.textContent)).toEqual([
      expect.stringContaining("Waiting on inputs"),
      expect.stringContaining("1 open note"),
      expect.stringContaining("You prepared this"),
    ]);
    for (const row of excluded) {
      expect(within(row as HTMLElement).getByRole<HTMLInputElement>("checkbox").disabled).toBe(
        true,
      );
    }
    expect(screen.getByText("Ineligible workpapers are excluded automatically.")).toBeTruthy();
    expect(calls.some((c) => c.method === "POST")).toBe(false);
  });

  it("signs only on the click, with the three eligible hashes, and shows each item's result", async () => {
    const calls = showBulk();
    fireEvent.click(await screen.findByRole("button", { name: "Sign off 3 as Reviewer (L2)" }));
    await waitFor(() => {
      expect(calls.some((c) => c.method === "POST" && c.path === "/v1/sign-offs:bulk")).toBe(true);
    });
    const post = calls.find((c) => c.method === "POST");
    const body = post?.body as { level: string; targets: { target_id: string }[] };
    expect(body.level).toBe("L2_reviewer");
    expect(body.targets.map((t) => t.target_id)).toEqual([BULK[0]?.id, BULK[2]?.id, BULK[4]?.id]);
    await waitFor(() => {
      expect(document.querySelectorAll('[data-bulk-result="signed"]')).toHaveLength(3);
    });
    expect(document.querySelectorAll('[data-bulk-result="excluded"]')).toHaveLength(3);
  });

  it("unticking a row takes it out of the count", async () => {
    showBulk();
    await screen.findByRole("button", { name: "Sign off 3 as Reviewer (L2)" });
    fireEvent.click(screen.getByRole("checkbox", { name: "Materiality v2" }));
    expect(screen.getByRole("button", { name: "Sign off 2 as Reviewer (L2)" })).toBeTruthy();
  });
});
