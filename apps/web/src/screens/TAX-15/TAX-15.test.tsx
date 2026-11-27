// T-08-T32 (TASK-9033; DEC-6038): TAX-15 a-f from their scenarios, whose rows are the exported
// Python scenario's. Row acceptance: "TAX-15 a-f render from data, a raise sends only on Daniel
// Reyes's click, and the Ferris row offers Open consent envelope and no outreach."
import { client } from "@abacus/api-client/client";
import { toastStore } from "@abacus/ui";
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { type FixtureHandler, installFixtureMode } from "../../app-core/fixture-mode";
import { renderRoutes } from "../../testing/support";
import { COPY as C } from "./copy";
import { TAX15 } from "./index";
import { COST_SEG_ID, FERRIS_ID, INITIAL, type Tax15State, scenarios } from "./scenarios";

const opened = vi.hoisted(() => [] as { key: string; args: readonly string[] }[]);
vi.mock("../../app-core/open", () => ({
  useOpenOverlay: () => (ref: { key: string; args: readonly string[] }) => {
    opened.push(ref);
  },
  useOpenHref: () => () => undefined,
}));

let restore: (() => void) | null = null;
interface Call {
  method: string;
  path: string;
}

beforeAll(() => {
  client.setConfig({ baseUrl: "http://localhost" });
});

afterEach(() => {
  cleanup();
  restore?.();
  restore = null;
  opened.length = 0;
  toastStore.clear();
});

function show(state: Tax15State): Call[] {
  const calls: Call[] = [];
  const base = scenarios[state];
  const handlers = Object.fromEntries(
    Object.entries(base.handlers).map(([k, h]) => [
      k,
      ((r) => {
        calls.push({ method: r.method, path: r.path });
        return h(r);
      }) satisfies FixtureHandler,
    ]),
  );
  restore = installFixtureMode({ ...base, handlers });
  const init = INITIAL[state];
  renderRoutes([
    {
      path: "/",
      component: () => (
        <TAX15
          {...(init.selected === undefined ? {} : { initialSelected: init.selected })}
          {...(init.client === undefined ? {} : { clientId: init.client })}
          {...(init.dismissDialog === undefined
            ? {}
            : { initialDismissDialog: init.dismissDialog })}
        />
      ),
    },
  ]);
  return calls;
}

const band = (key: string) => document.querySelector<HTMLElement>(`[data-band="${key}"]`);

describe("TAX-15 Planning opportunities", () => {
  it("TAX-15a default: the strip, nine rows in five bands, Feld selected with its rationale", async () => {
    show("a");
    await screen.findByText(C.queue, { selector: "header" });
    const strip = document.querySelector<HTMLElement>('[data-tax15="strip"]');
    await waitFor(() => {
      expect(strip?.textContent).toContain("58");
    });
    expect(strip?.textContent).toContain("$1,200,000");
    expect(strip?.textContent).toContain(C.talking.drafted);
    expect(document.querySelectorAll("[data-opportunity]")).toHaveLength(9);
    for (const [key, n] of [
      ["open", 4],
      ["raised", 1],
      ["accepted", 2],
      ["declined", 1],
      ["not_screened", 1],
    ] as const) {
      expect(band(key)?.querySelectorAll("[data-opportunity]")).toHaveLength(n);
    }
    expect(screen.getByText(C.showing(9, 71, 58))).toBeTruthy();
    const detail = document.querySelector<HTMLElement>('[data-tax15="detail"]');
    if (detail === null) throw new Error("no detail");
    expect(
      within(detail).getByText("Bunch 2026–2027 gifts through a donor-advised fund"),
    ).toBeTruthy();
    expect(within(detail).getByText(C.consentBasis["301_7216_2h"] ?? "")).toBeTruthy();
    expect(detail.querySelector('[data-tax15="why"]')?.textContent).toContain(
      "about 1,810 of federal tax at 32%",
    );
    expect(document.querySelector('[data-tax15="sources"]')?.textContent).toContain(
      "2025 Charitable Contributions Summary — Feld · 6 receipts",
    );
  });

  it("TAX-15 acceptance: a raise sends only on Daniel Reyes's click", async () => {
    const calls = show("a");
    fireEvent.click(await screen.findByRole("button", { name: C.raise }));
    const sheet = await screen.findByRole("dialog", { name: C.raiseTitle });
    expect(within(sheet).getByText(/Claire Feld/)).toBeTruthy();
    expect(calls.filter((c) => c.path.endsWith(":raise"))).toHaveLength(0); // the draft sends nothing
    fireEvent.click(within(sheet).getByRole("button", { name: C.send }));
    await waitFor(() => {
      expect(calls.filter((c) => c.path.endsWith(":raise"))).toHaveLength(1);
    });
    await waitFor(() => {
      expect(toastStore.list().map((t) => t.text)).toContain(C.raised);
    });
  });

  it("TAX-15b raised: the Feld row moves to Raised with its date", async () => {
    show("b");
    await waitFor(() => {
      expect(band("raised")?.querySelectorAll("[data-opportunity]")).toHaveLength(2);
    });
    expect(screen.getByText(/Raised Sep 14/)).toBeTruthy();
  });

  it("TAX-15c accepted: the cost segregation row, no outreach on an accepted item", async () => {
    show("c");
    await waitFor(() => {
      expect(
        document
          .querySelector(`[data-opportunity="${COST_SEG_ID}"]`)
          ?.getAttribute("aria-current"),
      ).toBe("true");
    });
    expect(screen.getByRole("button", { name: C.raise }).hasAttribute("disabled")).toBe(true);
  });

  it("TAX-15 acceptance: the Ferris row offers Open consent envelope and no outreach", async () => {
    show("d");
    expect(await screen.findByText(C.consentBlocked)).toBeTruthy();
    const detail = document.querySelector<HTMLElement>('[data-tax15="detail"]');
    if (detail === null) throw new Error("no detail");
    expect(within(detail).queryByRole("button", { name: C.raise })).toBeNull();
    expect(within(detail).queryByRole("button", { name: C.createProject })).toBeNull();
    expect(within(detail).queryByRole("button", { name: C.dismiss })).toBeNull();
    fireEvent.click(within(detail).getByRole("button", { name: C.openEnvelope }));
    expect(opened.some((o) => o.key === "envelope")).toBe(true);
    expect(document.querySelector(`[data-opportunity="${FERRIS_ID}"]`)).not.toBeNull();
  });

  it("TAX-15e dismiss: a reason first", async () => {
    show("e");
    const dialog = await screen.findByRole("dialog", { name: C.dismissTitle });
    const confirm = within(dialog).getByRole("button", { name: C.dismissConfirm });
    expect(confirm.hasAttribute("disabled")).toBe(true);
    fireEvent.click(within(dialog).getByLabelText(C.reasons.not_suitable));
    expect(confirm.hasAttribute("disabled")).toBe(false);
  });

  it("TAX-15f per-return view: the client chip and only Feld's rows", async () => {
    show("f");
    expect(await screen.findByText(C.clientChip("Jonah & Claire Feld"))).toBeTruthy();
    await waitFor(() => {
      expect(document.querySelectorAll("[data-opportunity]")).toHaveLength(1);
    });
  });

  it("no agent-owned control approves, signs off, releases or posts", async () => {
    show("a");
    await screen.findByText(C.queue, { selector: "header" });
    for (const word of ["Approve", "Sign off", "Release", "Post"]) {
      expect(screen.queryByRole("button", { name: new RegExp(`^${word}`) })).toBeNull();
    }
  });
});
