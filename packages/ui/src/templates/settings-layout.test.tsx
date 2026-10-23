import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { T12Specimen, Tpl12Specimen } from "../specimens/settings";
import { installDomShims } from "../test-dom";
import { SettingsLayout, canSave } from "./settings-layout";

// F-05-T45 acceptance: "TPL-12b enables Save only when dirty, TPL-12c blocks Save with Required,
// TPL-12d shows the read-only banner, and TPL-12e toasts Firm settings saved." Plus T12a to T12d,
// the step-up slot and the section list.

beforeAll(installDomShims);
afterEach(cleanup);

const TOOLBAR = { nav: [{ label: "Home" }], firm: "Brightwater Hale" } as const;
const GROUPS = [
  {
    label: "Firm",
    sections: [
      { id: "general", label: "General", icon: "building-2" as const },
      { id: "people", label: "People", icon: "users-round" as const },
    ],
  },
];

function board(container: HTMLElement, id: string): HTMLElement {
  const el = container.querySelector<HTMLElement>(`[data-artboard="${id}"]`);
  if (el === null) throw new Error(`no artboard ${id}`);
  return el;
}

const button = (el: HTMLElement, name: string): HTMLButtonElement =>
  within(el).getByRole<HTMLButtonElement>("button", { name });

describe("canSave", () => {
  it("only dirty, valid and editable forms save", () => {
    expect(canSave(false, false, false)).toBe(false);
    expect(canSave(true, false, false)).toBe(true);
    expect(canSave(true, true, false)).toBe(false);
    expect(canSave(true, false, true)).toBe(false);
  });
});

describe("SettingsLayout", () => {
  it("names the form pane after the active section and selects from the list", () => {
    const onSelect = vi.fn();
    render(
      <SettingsLayout
        toolbar={TOOLBAR}
        title="Firm settings"
        navTitle="Settings"
        groups={GROUPS}
        active="general"
        onSelect={onSelect}
        dirty={false}
      >
        <p>Form</p>
      </SettingsLayout>,
    );
    expect(screen.getByRole("heading", { name: "General", level: 2 })).toBeTruthy();
    const nav = screen.getByRole("navigation", { name: "Sections" });
    expect(within(nav).getByRole("button", { name: "General" }).getAttribute("aria-current")).toBe(
      "page",
    );
    fireEvent.click(within(nav).getByRole("button", { name: "People" }));
    expect(onSelect).toHaveBeenCalledWith("people");
  });

  it("draws the step-up slot over the shell when the screen passes one", () => {
    render(
      <SettingsLayout
        toolbar={TOOLBAR}
        title="Firm settings"
        navTitle="Settings"
        groups={GROUPS}
        active="general"
        dirty
        stepUp={<div role="dialog" aria-label="Confirm it’s you" />}
      >
        <p>Form</p>
      </SettingsLayout>,
    );
    expect(screen.getByRole("dialog", { name: "Confirm it’s you" })).toBeTruthy();
  });
});

describe("TPL-12", () => {
  it("TPL-12a: clean, so Save and Discard are disabled and nothing says unsaved", () => {
    const a = board(render(<Tpl12Specimen />).container, "tpl-12a");
    expect(button(a, "Save").disabled).toBe(true);
    expect(button(a, "Discard").disabled).toBe(true);
    expect(a.querySelector('[data-settings="unsaved"]')).toBeNull();
  });

  it("TPL-12b: dirty enables Save; Discard returns to clean", () => {
    const b = board(render(<Tpl12Specimen />).container, "tpl-12b");
    expect(b.querySelector('[data-settings="unsaved"]')?.textContent).toBe("Unsaved changes");
    expect(button(b, "Save").disabled).toBe(false);
    expect(
      within(b).getByRole("button", { name: /Default time zone: Eastern Time \(ET\)/ }),
    ).toBeTruthy();
    fireEvent.click(button(b, "Discard"));
    expect(button(b, "Save").disabled).toBe(true);
  });

  it("TPL-12c: the emptied Display name reads Required and blocks Save", () => {
    const c = board(render(<Tpl12Specimen />).container, "tpl-12c");
    const field = within(c).getByRole<HTMLInputElement>("textbox", { name: "Display name" });
    expect(field.value).toBe("");
    expect(field.placeholder).toBe("Required");
    expect(field.getAttribute("aria-invalid")).toBe("true");
    expect(within(c).getByRole("alert").textContent).toBe(
      "Enter the name clients see in the portal.",
    );
    expect(button(c, "Save").disabled).toBe(true);
    fireEvent.change(field, { target: { value: "Brightwater" } });
    expect(button(c, "Save").disabled).toBe(false);
  });

  it("TPL-12d: the read-only banner, locked fieldsets, no Save or Discard", () => {
    const d = board(render(<Tpl12Specimen />).container, "tpl-12d");
    expect(d.querySelector('[data-settings="read-only"]')?.textContent).toBe(
      "Only firm admins can edit these settings.",
    );
    expect(within(d).queryByRole("button", { name: "Save" })).toBeNull();
    expect(within(d).queryByRole("button", { name: "Discard" })).toBeNull();
    expect(within(d).getAllByRole("img", { name: "Locked" }).length).toBeGreaterThanOrEqual(4);
    expect(within(d).queryByRole("textbox")).toBeNull();
  });

  it("TPL-12e: the toast says Firm settings saved, and a save from TPL-12b raises it too", () => {
    const { container } = render(<Tpl12Specimen />);
    expect(board(container, "tpl-12e").textContent).toContain("Firm settings saved");
    const b = board(container, "tpl-12b");
    expect(b.textContent).not.toContain("Firm settings saved");
    fireEvent.click(button(b, "Save"));
    expect(b.textContent).toContain("Firm settings saved");
    expect(button(b, "Save").disabled).toBe(true);
  });

  it("offices foot: 98 + 64 + 62 = 224 returns, 22 + 14 + 10 = 46 seats", () => {
    const a = board(render(<Tpl12Specimen />).container, "tpl-12a");
    const text = a.textContent;
    expect(text).toContain("22 seats · 98 TY2025 returns");
    expect(text).toContain("14 seats · 64 returns");
    expect(text).toContain("10 seats · 62 returns");
    expect(a.querySelector('[data-settings="total"]')?.textContent).toBe(
      "All offices46 seats · 224 returns",
    );
  });

  it("the section list is exactly the twelve sections of blueprint §4.3", () => {
    const a = board(render(<Tpl12Specimen />).container, "tpl-12a");
    const nav = within(a).getByRole("navigation", { name: "Sections" });
    expect(within(nav).getAllByRole("button")).toHaveLength(12);
  });
});

describe("T12", () => {
  it("T12a clean and T12b dirty with two changes", () => {
    const { container } = render(<T12Specimen />);
    expect(button(board(container, "t12a"), "Save").disabled).toBe(true);
    const b = board(container, "t12b");
    expect(button(b, "Save").disabled).toBe(false);
    expect(
      within(b)
        .getByRole("switch", { name: "Agents can send client email" })
        .getAttribute("aria-checked"),
    ).toBe("true");
  });

  it("T12c: Kevin Osei reads the banner in the form, every row locked, Save disabled", () => {
    const c = board(render(<T12Specimen />).container, "t12c");
    const form = c.querySelector<HTMLElement>('[data-settings="form"]');
    expect(form?.querySelector('[data-settings="read-only"]')?.textContent).toBe(
      "Only firm admins can edit these settings.",
    );
    expect(button(c, "Save").disabled).toBe(true);
    for (const toggle of within(c).getAllByRole<HTMLButtonElement>("switch"))
      expect(toggle.disabled).toBe(true);
    expect(within(c).getAllByRole("img", { name: "Locked" }).length).toBe(13);
  });

  it("T12d: coverage over 100% shows in red ink with its helper and blocks Save", () => {
    const d = board(render(<T12Specimen />).container, "t12d");
    expect(within(d).getByRole("alert").textContent).toBe("Enter a value from 50% to 100%.");
    expect(button(d, "Save").disabled).toBe(true);
  });
});
