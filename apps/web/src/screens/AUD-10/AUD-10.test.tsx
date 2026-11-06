// A-04-T37 (TASK-3319): AUD-10 in fixture mode. Row: "The gap reads 92 days, the timeline has a text
// alternative, and no control concludes reliance while the gap is open." (the handoff's acceptance.)
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, waitFor } from "@testing-library/react";
import type { JSX } from "react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { newQueryClient } from "../../testing/support";
import { type Aud10State, scenarios } from "./scenarios";
import { useServiceOrgsCanvas } from "./ServiceOrgs";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

function Canvas(props: { running?: boolean; cuec?: number | null }): JSX.Element {
  const canvas = useServiceOrgsCanvas(
    "00000000-0000-4000-8000-000000000001",
    props,
  );
  return <div>{canvas.children}</div>;
}

function show(state: Aud10State, props: { running?: boolean; cuec?: number | null } = {}): void {
  restore = installFixtureMode(scenarios[state]);
  render(
    <QueryClientProvider client={newQueryClient()}>
      <Canvas {...props} />
    </QueryClientProvider>,
  );
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

describe("AUD-10", () => {
  it("a: the 92-day gap has a text alternative and 2 of 6 CUECs are evidenced", async () => {
    show("a");
    expect((await drawn("[data-aud10='gap-label']")).textContent).toBe("Gap · 92 days");
    expect((await drawn("[data-aud10='coverage-alt']")).textContent).toContain("92 days");
    expect((await drawn("[data-aud10='cuecs']")).textContent).toContain("2 of 6 evidenced");
    expect((await drawn("[data-aud10='reliance']")).textContent).toContain("pending");
  });

  it("a: the inventory reads the four organizations with their evidence", async () => {
    show("a");
    const table = await drawn("[data-aud10='inventory']");
    expect(table.textContent).toContain("Gap found");
    expect(table.textContent).toContain("Certification accepted");
    expect(table.textContent).toContain("Tested directly");
    expect(table.textContent).toContain("Not relevant");
  });

  it("b: the gap keeps its hatch and reads the bridge letter", async () => {
    show("b");
    expect((await drawn("[data-aud10='gap-label']")).textContent).toContain("no changes reported");
    expect((await drawn("[data-aud10='gap']")).dataset.bridged).toBe("true");
  });

  it("c: the selected CUEC is pressed", async () => {
    show("c", { cuec: 2 });
    expect((await drawn("[data-cuec='2']")).getAttribute("aria-pressed")).toBe("true");
  });

  it("d: the run drafting shows skeletons, never figures", async () => {
    show("d", { running: true });
    await drawn("[data-aud10='drafting']");
    expect(document.querySelector("[data-aud10='inventory']")).toBeNull();
  });

  it("e: a High exception is marked", async () => {
    show("e");
    const table = await drawn("[data-aud10='exceptions']");
    await waitFor(() => {
      expect(table.querySelector("[data-impact='high']")).not.toBeNull();
    });
  });

  it("no control concludes reliance", async () => {
    show("a");
    await drawn("[data-aud10='reliance']");
    expect(document.body.textContent).not.toMatch(/Conclude reliance|Rely on/);
  });
});
