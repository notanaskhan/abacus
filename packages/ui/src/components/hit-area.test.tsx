// F-05-T15 acceptance: every control under 24px has a 24px hit area (WCAG 2.2 SC 2.5.8; plan 04
// section 3.8). jsdom has no layout, so the box is read from the size classes a control declares
// and the hit area from the `before:` pseudo-element classes that grow it; a control with no
// declared size under 24 is not measurable here and is not asserted. The sweep renders every
// control of the kit, so a new one that is small and has no hit area fails here.
import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { Button, IconButton } from "./button";
import { HIT, MIN_TARGET } from "./hit-area";
import { Picker, SearchField, FilterChip, ValueRow } from "./inputs";
import { Segmented, SheetTabs, UnderlineTabs, ViewToggle } from "./tabs";
import { Checkbox, Radio, RadioGroup, Toggle } from "./toggles";

afterEach(cleanup);

interface Box {
  w: number | undefined;
  h: number | undefined;
}

function pxOf(token: string): number {
  return token === "px" ? 1 : Number(token.replace("px", ""));
}

function boxOf(element: Element): Box {
  const box: Box = { w: undefined, h: undefined };
  for (const cls of element.className.split(/\s+/)) {
    const size = /^size-\[(\d+)px\]$/.exec(cls);
    if (size?.[1] !== undefined) {
      box.w = Number(size[1]);
      box.h = Number(size[1]);
    }
    const h = /^h-\[(\d+)px\]$/.exec(cls);
    if (h?.[1] !== undefined) box.h = Number(h[1]);
    const w = /^w-\[(\d+)px\]$/.exec(cls);
    if (w?.[1] !== undefined) box.w = Number(w[1]);
  }
  return box;
}

/** How far the `::before` hit area reaches past the box on each axis. */
function growOf(element: Element): { x: number; y: number; absolute: boolean } {
  const grow = { x: 0, y: 0, absolute: false };
  for (const cls of element.className.split(/\s+/)) {
    if (cls === "before:absolute") grow.absolute = true;
    const all = /^before:-inset-(\[\d+px\]|px)$/.exec(cls);
    if (all?.[1] !== undefined) {
      const n = pxOf(all[1].replace(/[[\]]/g, ""));
      grow.x = n;
      grow.y = n;
    }
    const axis = /^before:-inset-([xy])-(\[\d+px\]|px)$/.exec(cls);
    if (axis?.[1] !== undefined && axis[2] !== undefined) {
      const n = pxOf(axis[2].replace(/[[\]]/g, ""));
      if (axis[1] === "x") grow.x = n;
      else grow.y = n;
    }
  }
  return grow;
}

function hitOf(element: Element): { w: number | undefined; h: number | undefined } {
  const { w, h } = boxOf(element);
  const grow = growOf(element);
  return {
    w: w === undefined ? undefined : w + 2 * grow.x,
    h: h === undefined ? undefined : h + 2 * grow.y,
  };
}

/** Asserts the hit area of a control under 24px; returns whether it was under. */
function expectHitArea(element: Element): boolean {
  const { w, h } = boxOf(element);
  const under = (w !== undefined && w < MIN_TARGET) || (h !== undefined && h < MIN_TARGET);
  if (!under) return false;
  const hit = hitOf(element);
  expect(growOf(element).absolute, `${element.outerHTML.slice(0, 80)} needs before:absolute`).toBe(
    true,
  );
  if (hit.w !== undefined) expect(hit.w).toBeGreaterThanOrEqual(MIN_TARGET);
  if (hit.h !== undefined) expect(hit.h).toBeGreaterThanOrEqual(MIN_TARGET);
  return true;
}

describe("the hit-area measure", () => {
  it("reads sizes and insets from classes", () => {
    const el = document.createElement("button");
    el.className = "size-[15px] before:absolute before:-inset-[5px]";
    expect(boxOf(el)).toEqual({ w: 15, h: 15 });
    expect(growOf(el)).toEqual({ x: 5, y: 5, absolute: true });
    expect(hitOf(el)).toEqual({ w: 25, h: 25 });
    el.className = "h-[22px] w-[38px] before:absolute before:inset-x-0 before:-inset-y-px";
    expect(hitOf(el)).toEqual({ w: 38, h: 24 });
  });

  it("every entry of HIT reaches 24px from the size it is for", () => {
    const FOR = {
      issue: 13,
      checkbox: 15,
      radio: 17,
      clear: 16,
      switch22: 22,
      switch20: 20,
    } as const;
    for (const [name, base] of Object.entries(FOR) as [keyof typeof FOR, number][]) {
      const el = document.createElement("span");
      el.className = `size-[${String(base)}px] ${HIT[name]}`;
      expect(hitOf(el).h, name).toBeGreaterThanOrEqual(MIN_TARGET);
    }
  });
});

describe("controls under 24px", () => {
  it("Toggle: the 22px and 20px switches reach 24px tall", () => {
    const { getAllByRole } = render(
      <>
        <Toggle label="Enabled" />
        <Toggle label="Dense" size="small" />
      </>,
    );
    const [a, b] = getAllByRole("switch");
    expect(a && hitOf(a)).toEqual({ w: 38, h: 24 });
    expect(b && hitOf(b)).toEqual({ w: 34, h: 24 });
  });

  it("Checkbox: a 15px box reaches 25px", () => {
    const { getByRole } = render(<Checkbox label="Done" />);
    expect(hitOf(getByRole("checkbox"))).toEqual({ w: 25, h: 25 });
  });

  it("Radio: the 17px radio reaches 25px and the 13px issue ring reaches 25px", () => {
    const { getAllByRole } = render(
      <>
        <Radio checked={false} label="One" />
        <Radio checked={false} label="Issue" size="issue" />
      </>,
    );
    const [a, b] = getAllByRole("radio");
    expect(a && hitOf(a)).toEqual({ w: 25, h: 25 });
    expect(b && hitOf(b)).toEqual({ w: 25, h: 25 });
  });

  it("SearchField: the 16px clear button reaches 24px", () => {
    const { getByRole } = render(<SearchField label="Search" defaultValue="Ridgeline" />);
    expect(hitOf(getByRole("button", { name: "Clear search" }))).toEqual({ w: 24, h: 24 });
  });

  it("Button: the 23px size and a link keep their 24px (T14)", () => {
    const { getByRole } = render(<Button size="xs">Small</Button>);
    expect(hitOf(getByRole("button"))).toMatchObject({ h: 25 });
  });
});

describe("the sweep", () => {
  it("every control of the kit that declares a size under 24 has a 24px hit area", () => {
    const { container } = render(
      <div>
        <Button size="xs">Small</Button>
        <IconButton icon="plus" label="New" />
        <Toggle label="A" />
        <Toggle label="B" size="small" />
        <Checkbox label="C" />
        <Checkbox label="D" checked="mixed" />
        <Radio checked label="E" />
        <Radio checked={false} label="F" size="issue" />
        <RadioGroup
          label="G"
          options={[
            { value: "a", label: "A" },
            { value: "b", label: "B" },
          ]}
        />
        <SearchField label="Search" defaultValue="x" />
        <Picker label="P" options={[{ value: "a", label: "A" }]} value="a" />
        <FilterChip label="Client" options={[{ value: "a", label: "A" }]} />
        <ValueRow kind="toggle" label="Enabled" />
        <ValueRow
          kind="select"
          label="Repeats"
          value="d"
          options={[{ value: "d", label: "Daily" }]}
        />
        <Segmented label="S" options={["One", "Two"]} />
        <UnderlineTabs label="U" options={["One", "Two"]} />
        <SheetTabs label="T" options={["One", "Two"]} />
        <ViewToggle view="grid" />
      </div>,
    );
    const controls = container.querySelectorAll("button, input, [role=switch], [role=checkbox]");
    expect(controls.length).toBeGreaterThan(20);
    let small = 0;
    for (const control of controls) if (expectHitArea(control)) small++;
    // Not vacuous: the xs button, two switches, two checkboxes, three radios, the clear button.
    expect(small).toBeGreaterThanOrEqual(9);
  });
});
