// P-04-T55 (TASK-2805): SHL-09 a–f in fixture mode. Row acceptance: "SHL-09a-f match their
// artboards at Tier C, and SHL-09e keeps Sign off field disabled with Add a reference before
// signing off." Words and figures are the handoff's (SHL-09 spec, frames 1–6).
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import {
  Outlet,
  RouterProvider,
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
} from "@tanstack/react-router";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { newQueryClient } from "../../testing/support";
import { ProvenanceTray } from ".";
import { DOCUMENTS, OPENS, type Shl09State, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

function show(state: Shl09State): void {
  restore = installFixtureMode(scenarios[state]);
  const open = OPENS[state];
  const root = createRootRoute({ component: Outlet });
  const router = createRouter({
    routeTree: root.addChildren([
      createRoute({
        getParentRoute: () => root,
        path: "/",
        component: () => (
          <ProvenanceTray
            field={{ type: open.type, id: open.id, fieldKey: open.fieldKey }}
            documents={DOCUMENTS}
            initialCollapsed={open.collapsed === true}
          />
        ),
      }),
    ]),
    history: createMemoryHistory({ initialEntries: ["/"] }),
  });
  render(
    <QueryClientProvider client={newQueryClient()}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

const tray = (): Promise<HTMLElement> =>
  waitFor(
    () => {
      const t = document.querySelector<HTMLElement>("[data-shl09='tray']");
      if (t === null) throw new Error("no tray yet");
      return t;
    },
    { timeout: 6000 },
  );

const section = (t: HTMLElement, name: "Updated" | "Previous"): HTMLElement =>
  within(t).getByRole("region", { name });

describe("SHL-09 frames", () => {
  it("a: Updated 2,310 over the struck 2,190, the citation, references and the stale KO tick", async () => {
    show("a");
    const t = await tray();
    const up = section(t, "Updated");
    expect(up.textContent).toContain("Accrued Agent");
    expect(up.querySelector("[data-value]")?.textContent).toBe("2,310");
    expect(up.querySelector("[data-prior]")?.textContent).toBe("2,190");
    expect(up.textContent).toContain(
      "Box 1 of the corrected Halvard Securities 2025 Form 1099-INT (issued Mar 6, 2026), consolidated statement p. 4.",
    );
    expect(up.textContent).toContain(
      "Halvard Securities 2025 Consolidated 1099 (Corrected) · p. 4",
    );
    expect(up.textContent).toContain("Interest income, Box 1: 2,310.00");
    const stale = up.querySelector("[data-tick='stale']");
    expect(stale?.textContent).toContain("✓ KO");
    expect(stale?.textContent).toContain("Changed after sign-off");
    expect(stale?.querySelector(".line-through")).not.toBeNull();
    expect(up.querySelector("[data-flag]")?.textContent).toContain(
      "Confirm corrected 1099 replaces the original",
    );
    const prev = section(t, "Previous");
    expect(prev.textContent).toContain("Imported Return");
    expect(prev.querySelector("[data-value]")?.textContent).toBe("2,190");
    expect(t.textContent).toContain("2 versions");
  });

  it("b: the ≈ estimate badge and the open issue link", async () => {
    show("b");
    const t = await tray();
    expect(within(t).getByLabelText("Estimate").textContent).toBe("≈");
    expect(t.textContent).toContain("48,000");
    await waitFor(() => {
      expect(t.querySelector("[data-issue-link]")?.textContent).toContain(
        "Open issue: Obtain 2025 federal and NY estimated tax payment confirmations",
      );
    });
  });

  it("c: a person's edit reads Edited with a person glyph, not the monogram", async () => {
    show("c");
    const up = section(await tray(), "Updated");
    expect(up.textContent).toContain("Kevin Osei");
    expect(up.textContent).toContain("Edited");
    expect(up.textContent).toContain("Per client email Sep 9 — Jonah confirmed…");
    expect(within(up).getByLabelText("Kevin Osei")).toBeTruthy();
  });

  it("d: both ticks are current", async () => {
    show("d");
    const up = section(await tray(), "Updated");
    expect(up.querySelectorAll("[data-tick='current']")).toHaveLength(2);
    expect(up.querySelector("[data-tick='stale']")).toBeNull();
    expect(up.querySelector("[data-flag]")).toBeNull();
  });

  it("e: Unsupported keeps Sign off field disabled with Add a reference before signing off", async () => {
    show("e");
    const t = await tray();
    const up = section(t, "Updated");
    expect(up.querySelector("[data-unsupported]")?.textContent).toContain("No source cited");
    expect(up.textContent).toContain("Unsupported");
    const sign = await within(t).findByRole<HTMLButtonElement>("button", {
      name: "Sign off field",
    });
    expect(sign.disabled).toBe(true);
    expect(sign.getAttribute("data-human-verb")).toBe("Sign off");
    fireEvent.focus(t.querySelector("[data-shl09='sign-disabled']") as HTMLElement);
    expect(await screen.findAllByText("Add a reference before signing off")).not.toHaveLength(0);
  });

  it("e: adding the Halvard page clears Unsupported and enables Sign off field", async () => {
    show("e");
    const t = await tray();
    fireEvent.click(within(t).getByRole("button", { name: "Add reference" }));
    fireEvent.click(
      await within(t).findByRole("button", {
        name: /Halvard Securities 2025 Consolidated 1099 \(Corrected\)/u,
      }),
    );
    await waitFor(() => {
      expect(t.querySelector("[data-unsupported]")).toBeNull();
    });
    const sign = await within(t).findByRole<HTMLButtonElement>("button", {
      name: "Sign off field",
    });
    await waitFor(() => {
      expect(sign.disabled).toBe(false);
    });
  });

  it("f: Previous starts collapsed and opens on its chevron", async () => {
    show("f");
    const prev = section(await tray(), "Previous");
    expect(prev.querySelector("[data-value]")).toBeNull();
    fireEvent.click(within(prev).getByRole("button", { name: "Expand" }));
    expect(prev.querySelector("[data-value]")?.textContent).toBe("2,190");
  });

  it("a: Sign off field ticks the current hash as the person", async () => {
    show("a");
    const t = await tray();
    fireEvent.click(await within(t).findByRole("button", { name: "Sign off field" }));
    await waitFor(() => {
      expect(section(t, "Updated").querySelectorAll("[data-tick='current']")).toHaveLength(1);
    });
  });

  it("a: an edit needs its citation note before Save", async () => {
    show("a");
    const t = await tray();
    fireEvent.click(within(t).getByRole("button", { name: "Edit value" }));
    const form = t.querySelector<HTMLElement>("[data-shl09='edit']") as HTMLElement;
    const save = within(form).getByRole<HTMLButtonElement>("button", { name: "Save" });
    expect(save.disabled).toBe(true);
    fireEvent.change(within(form).getByLabelText("Citation note (required)"), {
      target: { value: "Per the corrected 1099-INT" },
    });
    expect(save.disabled).toBe(false);
  });
});
