// F-05-T15 (Component Sheet F, C-13): Toggle, Checkbox, Radio and RadioGroup. Each is a button with
// its ARIA role; the keyboard behaviour is here, so it is tested here.
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Checkbox, Radio, RadioGroup, Toggle } from "./toggles";

afterEach(cleanup);

function classes(element: HTMLElement): string[] {
  return element.className.split(/\s+/);
}

describe("Toggle", () => {
  it("is a switch named by its label, off until turned on", () => {
    render(<Toggle label="Enabled" />);
    const toggle = screen.getByRole("switch", { name: "Enabled" });
    expect(toggle.getAttribute("aria-checked")).toBe("false");
    fireEvent.click(toggle);
    expect(toggle.getAttribute("aria-checked")).toBe("true");
    fireEvent.click(toggle);
    expect(toggle.getAttribute("aria-checked")).toBe("false");
  });

  it("is controlled when `checked` is given: it asks, the caller answers", () => {
    const onChange = vi.fn();
    const { rerender } = render(<Toggle label="Enabled" checked={false} onChange={onChange} />);
    fireEvent.click(screen.getByRole("switch"));
    expect(onChange).toHaveBeenCalledWith(true);
    expect(screen.getByRole("switch").getAttribute("aria-checked")).toBe("false");
    rerender(<Toggle label="Enabled" checked onChange={onChange} />);
    expect(screen.getByRole("switch").getAttribute("aria-checked")).toBe("true");
  });

  it("is a focusable button, so Space and Enter turn it as they turn any button", () => {
    render(<Toggle label="Enabled" />);
    const toggle = screen.getByRole("switch");
    toggle.focus();
    expect(document.activeElement).toBe(toggle);
    expect(toggle.tagName).toBe("BUTTON");
    expect(toggle.getAttribute("type")).toBe("button");
  });

  it("is 38 by 22, olive when on and greige when off; small is 34 by 20", () => {
    const { rerender } = render(<Toggle label="A" />);
    expect(classes(screen.getByRole("switch"))).toEqual(
      expect.arrayContaining(["h-[22px]", "w-[38px]", "rounded-pill", "bg-surface-deep"]),
    );
    rerender(<Toggle label="A" defaultChecked size="small" checked />);
    expect(classes(screen.getByRole("switch"))).toEqual(
      expect.arrayContaining(["h-[20px]", "w-[34px]", "bg-green"]),
    );
  });

  it("does not turn when disabled", () => {
    const onChange = vi.fn();
    render(<Toggle label="A" disabled onChange={onChange} />);
    fireEvent.click(screen.getByRole("switch"));
    expect(onChange).not.toHaveBeenCalled();
  });

  it("is named by another element when it has one", () => {
    render(
      <>
        <span id="lbl">Auto mode</span>
        <Toggle label="Auto mode" aria-labelledby="lbl" />
      </>,
    );
    expect(screen.getByRole("switch", { name: "Auto mode" })).toBeTruthy();
  });

  it("holds a forced state", () => {
    render(<Toggle label="A" forceState="focus" />);
    expect(screen.getByRole("switch").dataset["force"]).toBe("focus");
  });
});

describe("Checkbox", () => {
  it("is a checkbox that toggles", () => {
    const onChange = vi.fn();
    render(<Checkbox label="Done" onChange={onChange} />);
    const box = screen.getByRole("checkbox", { name: "Done" });
    expect(box.getAttribute("aria-checked")).toBe("false");
    fireEvent.click(box);
    expect(box.getAttribute("aria-checked")).toBe("true");
    expect(onChange).toHaveBeenLastCalledWith(true);
    fireEvent.click(box);
    expect(onChange).toHaveBeenLastCalledWith(false);
  });

  it("is mixed for a parent of partly chosen children, and a click chooses it", () => {
    const onChange = vi.fn();
    const { container } = render(<Checkbox label="All" checked="mixed" onChange={onChange} />);
    const box = screen.getByRole("checkbox");
    expect(box.getAttribute("aria-checked")).toBe("mixed");
    expect(container.querySelector(".lucide-minus")).not.toBeNull();
    fireEvent.click(box);
    expect(onChange).toHaveBeenCalledWith(true);
  });

  it("is a 15px box of radius 4: espresso with a check when on, a ring when off", () => {
    const { container, rerender } = render(<Checkbox label="A" />);
    const box = screen.getByRole("checkbox");
    expect(classes(box)).toEqual(
      expect.arrayContaining(["size-[15px]", "rounded-value", "inset-ring-ink-3"]),
    );
    expect(container.querySelector(".lucide-check")).toBeNull();
    rerender(<Checkbox label="A" checked />);
    expect(classes(box)).toEqual(expect.arrayContaining(["bg-espresso", "text-on-dark"]));
    expect(container.querySelector(".lucide-check")).not.toBeNull();
  });

  it("shows its label and lets a click on it choose the box", () => {
    render(<Checkbox label="Remember me" showLabel />);
    fireEvent.click(screen.getByText("Remember me"));
    expect(
      screen.getByRole("checkbox", { name: "Remember me" }).getAttribute("aria-checked"),
    ).toBe("true");
  });

  it("does not change when disabled", () => {
    const onChange = vi.fn();
    render(<Checkbox label="A" disabled onChange={onChange} />);
    fireEvent.click(screen.getByRole("checkbox"));
    expect(onChange).not.toHaveBeenCalled();
  });
});

describe("Radio", () => {
  it("is a 17px ring, an olive disc with a check once chosen", () => {
    const { container, rerender } = render(<Radio checked={false} label="One" />);
    const radio = screen.getByRole("radio", { name: "One" });
    expect(classes(radio)).toEqual(expect.arrayContaining(["size-[17px]", "rounded-pill"]));
    expect(radio.getAttribute("aria-checked")).toBe("false");
    rerender(<Radio checked label="One" />);
    expect(classes(radio)).toEqual(expect.arrayContaining(["bg-green", "text-on-dark"]));
    expect(container.querySelector(".lucide-check")).not.toBeNull();
  });

  it("is a 13px ring as the issue size", () => {
    render(<Radio checked={false} label="Issue" size="issue" />);
    expect(classes(screen.getByRole("radio"))).toContain("size-[13px]");
  });

  it("chooses on click, and a chosen radio does not unchoose", () => {
    const onSelect = vi.fn();
    const { rerender } = render(<Radio checked={false} label="One" onSelect={onSelect} />);
    fireEvent.click(screen.getByRole("radio"));
    expect(onSelect).toHaveBeenCalledTimes(1);
    rerender(<Radio checked label="One" onSelect={onSelect} />);
    fireEvent.click(screen.getByRole("radio"));
    expect(onSelect).toHaveBeenCalledTimes(1);
  });
});

describe("RadioGroup", () => {
  const OPTIONS = [
    { value: "a", label: "Daily" },
    { value: "b", label: "Weekly" },
    { value: "c", label: "Monthly" },
  ];

  it("is a radiogroup with one tab stop: the chosen radio", () => {
    render(<RadioGroup label="Repeats" options={OPTIONS} value="b" />);
    expect(screen.getByRole("radiogroup", { name: "Repeats" })).toBeTruthy();
    const stops = screen.getAllByRole("radio").map((r) => r.getAttribute("tabindex"));
    expect(stops).toEqual(["-1", "0", "-1"]);
  });

  it("wraps with the arrows, choosing as it moves, and moves focus", () => {
    const onChange = vi.fn();
    render(<RadioGroup label="Repeats" options={OPTIONS} defaultValue="c" onChange={onChange} />);
    fireEvent.keyDown(screen.getByRole("radio", { name: "Monthly" }), { key: "ArrowRight" });
    expect(screen.getByRole("radio", { name: "Daily" }).getAttribute("aria-checked")).toBe("true");
    expect(document.activeElement).toBe(screen.getByRole("radio", { name: "Daily" }));
    expect(onChange).toHaveBeenLastCalledWith("a");
    fireEvent.keyDown(screen.getByRole("radio", { name: "Daily" }), { key: "ArrowUp" });
    expect(screen.getByRole("radio", { name: "Monthly" }).getAttribute("aria-checked")).toBe(
      "true",
    );
  });

  it("skips a disabled option and jumps with Home and End", () => {
    render(
      <RadioGroup
        label="Repeats"
        defaultValue="a"
        options={[OPTIONS[0], { value: "b", label: "Weekly", disabled: true }, OPTIONS[2]].flatMap(
          (o) => (o === undefined ? [] : [o]),
        )}
      />,
    );
    fireEvent.keyDown(screen.getByRole("radio", { name: "Daily" }), { key: "ArrowRight" });
    expect(screen.getByRole("radio", { name: "Monthly" }).getAttribute("aria-checked")).toBe(
      "true",
    );
    fireEvent.keyDown(screen.getByRole("radio", { name: "Monthly" }), { key: "Home" });
    expect(screen.getByRole("radio", { name: "Daily" }).getAttribute("aria-checked")).toBe("true");
    fireEvent.keyDown(screen.getByRole("radio", { name: "Daily" }), { key: "End" });
    expect(screen.getByRole("radio", { name: "Monthly" }).getAttribute("aria-checked")).toBe(
      "true",
    );
  });

  it("chooses on a click on the radio or on its text", () => {
    const onChange = vi.fn();
    render(<RadioGroup label="Repeats" options={OPTIONS} onChange={onChange} />);
    fireEvent.click(screen.getByText("Weekly"));
    expect(onChange).toHaveBeenCalledWith("b");
  });

  it("puts the first enabled radio in the tab order when none is chosen", () => {
    render(<RadioGroup label="Repeats" options={OPTIONS} />);
    expect(screen.getAllByRole("radio").map((r) => r.getAttribute("tabindex"))).toEqual([
      "0",
      "-1",
      "-1",
    ]);
  });
});
