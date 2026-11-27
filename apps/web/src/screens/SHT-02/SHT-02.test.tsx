// K-03-T23 (TASK-9029; DEC-6034): SHT-02 a-f from their scenarios, whose column and usage are the
// exported Python scenario's. Row acceptance: "SHT-02a-f render with exactly the 11 types in
// order, Restricted as the default for client-data columns, Save disabled until a change, and
// Suggest to Hannah Leclerc prefilling an SHL-18 mention."
import { client } from "@abacus/api-client/client";
import { toastStore } from "@abacus/ui";
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { installFixtureMode, json } from "../../app-core/fixture-mode";
import { SHEET_ID } from "../../fixtures/seed/sheets-sh1";
import { renderRoutes } from "../../testing/support";
import { COPY as C } from "./copy";
import { ColumnDrawer } from "./index";
import { INITIAL, type Sht02State, scenarios } from "./scenarios";

const opened = vi.hoisted(() => [] as { key: string; args: readonly string[] }[]);
vi.mock("../../app-core/open", () => ({
  useOpenOverlay: () => (ref: { key: string; args: readonly string[] }) => {
    opened.push(ref);
  },
}));

let restore: (() => void) | null = null;
const closed = vi.fn();

beforeAll(() => {
  client.setConfig({ baseUrl: "http://localhost" });
});

afterEach(() => {
  cleanup();
  restore?.();
  restore = null;
  opened.length = 0;
  toastStore.clear();
  closed.mockReset();
});

function show(state: Sht02State, over: Parameters<typeof installFixtureMode>[0]["handlers"] = {}) {
  const base = scenarios[state];
  restore = installFixtureMode({ ...base, handlers: { ...base.handlers, ...over } });
  const init = INITIAL[state];
  renderRoutes([
    {
      path: "/",
      component: () => (
        <ColumnDrawer
          sheetId={SHEET_ID}
          columnId={init.columnId}
          afterKey={init.afterKey}
          onClose={closed}
          {...(init.initialType === undefined ? {} : { initialType: init.initialType })}
          {...(init.initialDelete === undefined ? {} : { initialDelete: init.initialDelete })}
        />
      ),
    },
  ]);
}

async function drawer(name: string): Promise<HTMLElement> {
  const d = await screen.findByRole("dialog", { name });
  await within(d).findByText(C.keys.classification);
  return d;
}

function openMenu(button: HTMLElement): void {
  fireEvent.pointerDown(button, { button: 0 }); // the menu opens on pointer down (Radix)
}

describe("SHT-02 Column and field configurator", () => {
  it("SHT-02a new: Date range shown as a month, Required on, Restricted, nothing used yet", async () => {
    show("a");
    const d = await drawer(C.addTitle);
    expect(within(d).getByText(C.after("Invoice date"))).toBeTruthy();
    expect(within(d).getByRole("button", { name: `${C.keys.type}: Date` })).toBeTruthy();
    expect(within(d).getByText(C.display.month)).toBeTruthy();
    expect(
      within(d).getByRole("switch", { name: C.keys.range }).getAttribute("aria-checked"),
    ).toBe("true");
    expect(
      within(d).getByRole("switch", { name: C.keys.required }).getAttribute("aria-checked"),
    ).toBe("true");
    expect(within(d).getByRole("switch", { name: C.keys.visible }).hasAttribute("disabled")).toBe(
      true,
    );
    expect(within(d).getByText(C.visibleHelp)).toBeTruthy();
    expect(within(d).getByText("0 saved views · 0 rules · 0 agent columns")).toBeTruthy();
    expect(within(d).getByText(C.note)).toBeTruthy();
  });

  it("SHT-02 acceptance: Restricted is the default for a client-data column, and a lower level needs a reason", async () => {
    show("a");
    const d = await drawer(C.addTitle);
    const level = within(d).getByRole("button", { name: `${C.keys.classification}: Restricted` });
    expect(level).toBeTruthy();
    fireEvent.change(within(d).getByRole("textbox", { name: C.keys.name }), {
      target: { value: "Service period" },
    });
    const add = within(d).getByRole("button", { name: C.add });
    expect(add.hasAttribute("disabled")).toBe(false);
    openMenu(level);
    const items = await screen.findAllByRole("menuitemradio");
    expect(items.map((i) => i.textContent)).toEqual(
      C.levels.map((l) => `${l.label}${l.hint ?? ""}`),
    );
    fireEvent.click(screen.getByRole("menuitemradio", { name: /^Internal/ }));
    await within(d).findByRole("textbox", { name: C.reasonLabel });
    expect(add.hasAttribute("disabled")).toBe(true); // a reason first
    fireEvent.change(within(d).getByRole("textbox", { name: C.reasonLabel }), {
      target: { value: "Dates only, no amounts." },
    });
    expect(add.hasAttribute("disabled")).toBe(false);
  });

  it("SHT-02b acceptance: the type picker lists exactly the 11 types in order", async () => {
    show("b");
    const d = await drawer(C.addTitle);
    openMenu(within(d).getByRole("button", { name: `${C.keys.type}: Date` }));
    const items = await screen.findAllByRole("menuitemradio");
    expect(items).toHaveLength(11);
    expect(items.map((i) => i.textContent)).toEqual(
      C.types.map((t) => `${t.label}${t.hint ?? ""}`),
    );
    // "Agent column" hands off to SHT-04.
    fireEvent.click(screen.getByRole("menuitemradio", { name: /^Agent column/ }));
    await waitFor(() => {
      expect(closed).toHaveBeenCalled();
    });
    expect(opened).toContainEqual({ key: "agent-column", args: ["new"] });
  });

  it("SHT-02c acceptance: edit shows what uses the column, and Save is disabled until a change", async () => {
    show("c");
    const d = await drawer(C.editTitle("Service period"));
    expect(
      await within(d).findByText(
        "2 saved views (Default · Exceptions) · 1 agent column (Conclusion reads @Service period)",
      ),
    ).toBeTruthy();
    expect(within(d).getByText("40 rows have values")).toBeTruthy();
    expect(within(d).getByRole("button", { name: C.deleteColumn })).toBeTruthy();
    const save = within(d).getByRole("button", { name: C.save });
    expect(save.hasAttribute("disabled")).toBe(true);
    fireEvent.change(within(d).getByRole("textbox", { name: C.keys.description }), {
      target: { value: "When the goods or services were received (per invoice)" },
    });
    expect(save.hasAttribute("disabled")).toBe(false);
    fireEvent.click(save);
    await waitFor(() => {
      expect(toastStore.list().map((t) => t.text)).toContain(C.saved("Service period"));
    });
  });

  it("SHT-02d type change: Date to Text warns before converting the 40 values", async () => {
    show("d");
    const d = await drawer(C.editTitle("Service period"));
    const warning = await waitFor(() => {
      const found = d.querySelector<HTMLElement>('[data-sht02="type-warning"]');
      if (found === null) throw new Error("no warning");
      return found;
    });
    await waitFor(() => {
      expect(warning.textContent).toContain(
        "Changing Date to Text keeps the 40 values as text. Date filters in 2 saved views stop working, and Conclusion will read @Service period as text.",
      );
    });
    expect(within(warning).getByRole("button", { name: C.keepType("Date") })).toBeTruthy();
    fireEvent.click(within(warning).getByRole("button", { name: C.changeType }));
    await waitFor(() => {
      expect(within(d).getByRole("button", { name: `${C.keys.type}: Text` })).toBeTruthy();
    });
  });

  it("SHT-02e blocked delete: the dialog names the views and the agent column", async () => {
    show("e");
    const dialog = await screen.findByRole("dialog", { name: C.blockedTitle("Service period") });
    await waitFor(() => {
      expect(dialog.textContent).toContain(
        "It is used in 2 saved views (Default, Exceptions), and the agent column Conclusion refers to @Service period. Remove those references first. Deleting a column never removes evidence or sign-offs.",
      );
    });
    expect(within(dialog).getByRole("button", { name: C.openAgent("Conclusion") })).toBeTruthy();
    expect(
      within(dialog)
        .getAllByRole("button", { name: C.close })
        .some((b) => b.textContent === C.close),
    ).toBe(true);
  });

  it("SHT-02f acceptance: a non-manager reads it, and Suggest to Hannah Leclerc prefills an SHL-18 mention", async () => {
    show("f");
    const d = await drawer(C.addTitle);
    expect(within(d).getByText(C.readOnly)).toBeTruthy();
    expect(within(d).queryByRole("button", { name: C.add })).toBeNull();
    expect(
      within(d).getByRole<HTMLTextAreaElement>("textbox", { name: C.keys.name }).readOnly,
    ).toBe(true);
    fireEvent.click(within(d).getByRole("button", { name: C.suggest("Hannah Leclerc") }));
    await waitFor(() => {
      const composer = Array.from(d.querySelectorAll<HTMLTextAreaElement>("textarea")).find((t) =>
        t.value.startsWith("@Hannah Leclerc"),
      );
      expect(composer?.value).toBe("@Hannah Leclerc ");
    });
  });

  it("error: a failed save says so", async () => {
    show("c", {
      "PATCH /v1/sheets/{sheet_id}/columns/{column_id}": () => json({ detail: "boom" }, 501),
    });
    const d = await drawer(C.editTitle("Service period"));
    fireEvent.change(within(d).getByRole("textbox", { name: C.keys.description }), {
      target: { value: "Changed" },
    });
    fireEvent.click(within(d).getByRole("button", { name: C.save }));
    await waitFor(() => {
      expect(toastStore.list().map((t) => t.text)).toContain(C.failed);
    });
  });

  it("not loaded: a failed sheet read says so", async () => {
    show("a", { "GET /v1/sheets/{sheet_id}": () => json({ detail: "boom" }, 500) });
    expect(await screen.findByText(C.loadFailed)).toBeTruthy();
  });
});
