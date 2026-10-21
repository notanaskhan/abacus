// F-05-T15 (Component Sheet F, C-13): SearchField, Picker, FilterChip, ValueRow and Fieldset. There
// is no native select and no boxed input among them.
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { installDomShims } from "../test-dom";
import { Fieldset, FieldsetAdd } from "./fieldset";
import { FilterChip, Picker, type PickerOption, SearchField, ValueRow } from "./inputs";

beforeAll(installDomShims);
afterEach(cleanup);

function classes(element: HTMLElement): string[] {
  return element.className.split(/\s+/);
}

function openMenu(trigger: HTMLElement): void {
  trigger.focus();
  fireEvent.keyDown(trigger, { key: "ArrowDown" });
}

const STATUS: PickerOption[] = [
  { value: "all", label: "All" },
  { value: "req", label: "Requested" },
  { value: "rec", label: "Received", disabled: true },
];

describe("SearchField", () => {
  it("is a named search box on a 28px nested pill with a search icon", () => {
    const { container } = render(<SearchField label="Search clients" />);
    const input = screen.getByRole("searchbox", { name: "Search clients" });
    expect(input.getAttribute("placeholder")).toBe("Search");
    expect(classes(input)).toEqual(
      expect.arrayContaining([
        "h-[28px]",
        "rounded-pill",
        "bg-nested",
        "inset-shadow-hair",
        "text-body",
      ]),
    );
    expect(container.querySelector("svg")?.dataset["icon"]).toBe("search");
  });

  it("turns white with a firmer ring on focus", () => {
    render(<SearchField label="Search" />);
    expect(classes(screen.getByRole("searchbox"))).toEqual(
      expect.arrayContaining(["focus:bg-card", "focus:inset-shadow-sel"]),
    );
  });

  it("reports the text, not the event, and shows a clear button once there is text", () => {
    const onChange = vi.fn();
    render(<SearchField label="Search" onChange={onChange} />);
    expect(screen.queryByRole("button", { name: "Clear search" })).toBeNull();
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "Ridgeline" } });
    expect(onChange).toHaveBeenLastCalledWith("Ridgeline");
    expect(screen.getByRole("button", { name: "Clear search" })).toBeTruthy();
  });

  it("clears with the button and with Escape", () => {
    const onChange = vi.fn();
    render(<SearchField label="Search" defaultValue="Ridgeline" onChange={onChange} />);
    fireEvent.click(screen.getByRole("button", { name: "Clear search" }));
    expect(onChange).toHaveBeenLastCalledWith("");
    expect(screen.getByRole<HTMLInputElement>("searchbox").value).toBe("");
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "Summit" } });
    fireEvent.keyDown(screen.getByRole("searchbox"), { key: "Escape" });
    expect(onChange).toHaveBeenLastCalledWith("");
    expect(screen.getByRole<HTMLInputElement>("searchbox").value).toBe("");
  });

  it("is controlled when `value` is given", () => {
    const { rerender } = render(
      <SearchField label="Search" value="a" onChange={() => undefined} />,
    );
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "ab" } });
    expect(screen.getByRole<HTMLInputElement>("searchbox").value).toBe("a");
    rerender(<SearchField label="Search" value="ab" onChange={() => undefined} />);
    expect(screen.getByRole<HTMLInputElement>("searchbox").value).toBe("ab");
  });

  it("names the clear button as the caller says", () => {
    render(<SearchField label="Search" defaultValue="x" clearLabel="Clear" />);
    expect(screen.getByRole("button", { name: "Clear" })).toBeTruthy();
  });

  it("holds focus for a specimen", () => {
    render(<SearchField label="Search" forceState="focus" />);
    expect(screen.getByRole("searchbox").dataset["force"]).toBe("focus");
  });
});

describe("Picker", () => {
  it("shows the chosen option's label on a 28px pill, named for what it chooses", () => {
    render(<Picker label="Status" options={STATUS} value="all" />);
    const button = screen.getByRole("button", { name: "Status: All" });
    expect(button.textContent).toBe("All");
    expect(button.getAttribute("aria-haspopup")).toBe("menu");
    expect(classes(button)).toEqual(
      expect.arrayContaining([
        "h-[28px]",
        "rounded-pill",
        "bg-card",
        "shadow-e1",
        "pl-[11px]",
        "pr-[9px]",
      ]),
    );
  });

  it("shows the placeholder while nothing is chosen", () => {
    render(<Picker label="Status" options={STATUS} placeholder="Any status" />);
    expect(screen.getByRole("button", { name: "Status: Any status" })).toBeTruthy();
  });

  it("opens a radio menu with the current one checked, and chooses with a click", () => {
    const onChange = vi.fn();
    render(<Picker label="Status" options={STATUS} defaultValue="all" onChange={onChange} />);
    openMenu(screen.getByRole("button", { name: "Status: All" }));
    const menu = screen.getByRole("menu", { name: "Status" });
    const items = within(menu).getAllByRole("menuitemradio");
    expect(items.map((i) => i.getAttribute("aria-checked"))).toEqual(["true", "false", "false"]);
    expect(items[2]?.getAttribute("aria-disabled")).toBe("true");
    fireEvent.click(items[1] as HTMLElement);
    expect(onChange).toHaveBeenCalledWith("req");
    expect(screen.getByRole("button", { name: "Status: Requested" })).toBeTruthy();
    expect(screen.queryByRole("menu")).toBeNull();
  });

  it("closes on Escape and returns focus to the picker", async () => {
    render(<Picker label="Status" options={STATUS} value="all" />);
    const button = screen.getByRole("button", { name: "Status: All" });
    openMenu(button);
    fireEvent.keyDown(document.activeElement as HTMLElement, { key: "Escape" });
    expect(screen.queryByRole("menu")).toBeNull();
    await waitFor(() => {
      expect(document.activeElement).toBe(button);
    });
  });

  it("draws the nav-fill picker with up-down chevrons", () => {
    const { container } = render(
      <Picker label="Stage" variant="fill" options={STATUS} value="req" />,
    );
    const button = screen.getByRole("button", { name: "Stage: Requested" });
    expect(classes(button)).toEqual(expect.arrayContaining(["bg-nav-fill", "pl-[12px]"]));
    expect(container.querySelector("svg")?.dataset["icon"]).toBe("chevrons-up-down");
  });

  it("draws the filter button as an icon and a chevron with no text", () => {
    const { container } = render(
      <Picker label="Filter" variant="filter" options={STATUS} value="all" />,
    );
    const button = screen.getByRole("button", { name: "Filter: All" });
    expect(button.textContent).toBe("");
    expect([...container.querySelectorAll("svg")].map((s) => s.dataset["icon"])).toEqual([
      "list-filter",
      "chevron-down",
    ]);
  });

  it("has no native select in it", () => {
    const { container } = render(<Picker label="Status" options={STATUS} value="all" />);
    expect(container.querySelector("select")).toBeNull();
  });

  it("does not open when disabled", () => {
    render(<Picker label="Status" options={STATUS} value="all" disabled />);
    openMenu(screen.getByRole("button", { name: "Status: All" }));
    expect(screen.queryByRole("menu")).toBeNull();
  });

  it("holds the menu open for a specimen", () => {
    render(<Picker label="Status" options={STATUS} value="all" forceState="open" />);
    expect(screen.getByRole("menu", { name: "Status" })).toBeTruthy();
  });
});

describe("FilterChip", () => {
  const CLIENTS: PickerOption[] = [
    { value: "rpp", label: "Ridgeline Property Partners" },
    { value: "sum", label: "Summit Trail" },
  ];

  it("is white and quiet while empty: the label, then Select with up-down chevrons", () => {
    const { container } = render(
      <FilterChip label="Client" icon="building-2" options={CLIENTS} />,
    );
    const chip = screen.getByRole("button", { name: "Client: Select" });
    expect(chip.dataset["active"]).toBe("false");
    expect(classes(chip)).toEqual(
      expect.arrayContaining(["bg-card", "shadow-e1", "h-[28px]", "rounded-pill"]),
    );
    expect(chip.textContent).toBe("ClientSelect");
    expect([...container.querySelectorAll("svg")].map((s) => s.dataset["icon"])).toEqual([
      "building-2",
      "chevrons-up-down",
    ]);
  });

  it("turns amber once a value is chosen, and the value is 500", () => {
    render(<FilterChip label="Client" options={CLIENTS} value="rpp" />);
    const chip = screen.getByRole("button", { name: "Client: Ridgeline Property Partners" });
    expect(chip.dataset["active"]).toBe("true");
    expect(classes(chip)).toEqual(
      expect.arrayContaining(["bg-amber-tint", "text-amber-ink", "ring-amber-line"]),
    );
    expect(classes(chip.lastElementChild as HTMLElement)).toContain("font-medium");
  });

  it("chooses from a radio menu and reports the value", () => {
    const onChange = vi.fn();
    render(<FilterChip label="Client" options={CLIENTS} onChange={onChange} />);
    openMenu(screen.getByRole("button", { name: "Client: Select" }));
    fireEvent.click(screen.getByRole("menuitemradio", { name: "Summit Trail" }));
    expect(onChange).toHaveBeenCalledWith("sum");
    expect(screen.getByRole("button", { name: "Client: Summit Trail" })).toBeTruthy();
  });

  it("empties with the clear item the caller names", () => {
    const onChange = vi.fn();
    render(
      <FilterChip
        label="Client"
        options={CLIENTS}
        value="rpp"
        clearLabel="Any client"
        onChange={onChange}
      />,
    );
    openMenu(screen.getByRole("button", { name: /Client:/ }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Any client" }));
    expect(onChange).toHaveBeenCalledWith(null);
  });
});

describe("ValueRow", () => {
  const REPEATS = [
    { value: "d", label: "Daily" },
    { value: "w", label: "Weekly" },
  ];

  it("puts the label at the left and the value at the right of a 34px row", () => {
    const { container } = render(
      <ValueRow kind="info" label="Next run">
        Wed, Sep 16
      </ValueRow>,
    );
    const row = container.querySelector("label")?.parentElement as HTMLElement;
    expect(classes(row)).toEqual(
      expect.arrayContaining(["min-h-[34px]", "px-[12px]", "gap-[10px]", "text-body"]),
    );
    expect(classes(screen.getByText("Next run"))).toEqual(
      expect.arrayContaining(["text-ink-2", "flex-none"]),
    );
    expect(classes(screen.getByText("Wed, Sep 16"))).toEqual(
      expect.arrayContaining(["text-right", "text-ink-3"]),
    );
  });

  it("indents under a schedule: 24px of left padding", () => {
    const { container } = render(
      <ValueRow kind="info" label="Next run" indented>
        x
      </ValueRow>,
    );
    expect(classes(container.querySelector("label")?.parentElement as HTMLElement)).toContain(
      "pl-[24px]",
    );
  });

  it("select: shows the value with up-down chevrons and chooses from a menu", () => {
    const onChange = vi.fn();
    const { container } = render(
      <ValueRow kind="select" label="Repeats" value="d" options={REPEATS} onChange={onChange} />,
    );
    const button = screen.getByRole("button", { name: "Repeats: Daily" });
    expect(button.textContent).toBe("Daily");
    expect(classes(button)).toEqual(
      expect.arrayContaining(["font-medium", "min-h-[26px]", "rounded-sheet"]),
    );
    expect(container.querySelector("svg")?.dataset["icon"]).toBe("chevrons-up-down");
    openMenu(button);
    fireEvent.click(screen.getByRole("menuitemradio", { name: "Weekly" }));
    expect(onChange).toHaveBeenCalledWith("w");
  });

  it("time: draws a clock in place of the chevrons", () => {
    const { container } = render(
      <ValueRow
        kind="time"
        label="Time"
        value="9"
        options={[{ value: "9", label: "09:00 AM" }]}
      />,
    );
    expect(container.querySelector("svg")?.dataset["icon"]).toBe("clock");
  });

  it("text: a borderless right-aligned input, 500, with the requirement as its placeholder", () => {
    const onChange = vi.fn();
    render(<ValueRow kind="text" label="Name" placeholder="Required" onChange={onChange} />);
    const input = screen.getByRole("textbox", { name: "Name" });
    expect(input.getAttribute("placeholder")).toBe("Required");
    expect(classes(input)).toEqual(
      expect.arrayContaining(["bg-transparent", "text-right", "font-medium"]),
    );
    expect(input.className).not.toMatch(/\bborder\b|ring|shadow|rounded/);
    fireEvent.change(input, { target: { value: "Missing Document Chaser" } });
    expect(onChange).toHaveBeenCalledWith("Missing Document Chaser");
  });

  it("toggle: a switch named by the row's label", () => {
    const onChange = vi.fn();
    render(<ValueRow kind="toggle" label="Enabled" onChange={onChange} />);
    fireEvent.click(screen.getByRole("switch", { name: "Enabled" }));
    expect(onChange).toHaveBeenCalledWith(true);
  });

  it("paragraph: a stacked row with a borderless three-row field", () => {
    render(<ValueRow kind="paragraph" label="Description" placeholder="What this agent does" />);
    const field = screen.getByRole("textbox", { name: "Description" });
    expect(field.tagName).toBe("TEXTAREA");
    expect(field.getAttribute("rows")).toBe("3");
    expect(classes(field)).toEqual(expect.arrayContaining(["bg-transparent", "resize-none"]));
  });

  it("an invalid row turns the value brick and says why, as an alert", () => {
    render(
      <ValueRow kind="text" label="Name" placeholder="Required" error="Give the agent a name." />,
    );
    const input = screen.getByRole("textbox", { name: "Name" });
    expect(input.getAttribute("aria-invalid")).toBe("true");
    expect(classes(input)).toContain("text-red-ink");
    const alert = screen.getByRole("alert");
    expect(alert.textContent).toBe("Give the agent a name.");
    expect(input.getAttribute("aria-describedby")).toBe(alert.id);
    expect(classes(alert)).toEqual(
      expect.arrayContaining(["text-right", "text-meta", "text-red-ink"]),
    );
  });

  it("has no native select and no bordered input", () => {
    const { container } = render(
      <>
        <ValueRow kind="select" label="A" value="d" options={REPEATS} />
        <ValueRow kind="text" label="B" />
        <ValueRow kind="paragraph" label="C" />
      </>,
    );
    expect(container.querySelector("select")).toBeNull();
    for (const field of container.querySelectorAll("input, textarea")) {
      expect((field as HTMLElement).className).not.toMatch(/border|ring-|shadow|rounded/);
    }
  });
});

describe("Fieldset", () => {
  it("is a white radius-10 card on e1 with a band header", () => {
    render(<Fieldset title="Details">body</Fieldset>);
    const heading = screen.getByRole("heading", { name: "Details" });
    expect(heading.tagName).toBe("H3");
    expect(classes(heading)).toContain("text-section");
    const card = heading.closest("section") as HTMLElement;
    expect(classes(card)).toEqual(
      expect.arrayContaining(["bg-card", "rounded-nested", "shadow-e1", "overflow-hidden"]),
    );
    expect(classes(heading.parentElement as HTMLElement)).toEqual(
      expect.arrayContaining(["bg-band-hd", "min-h-[33px]", "border-b-[0.5px]", "border-hair"]),
    );
  });

  it("has no header without a title, and keeps a padded body for free content", () => {
    const { container } = render(<Fieldset className="opacity-70">free</Fieldset>);
    expect(container.querySelector("h3")).toBeNull();
    expect(classes(container.firstElementChild as HTMLElement)).toContain("opacity-70");
    expect(classes(screen.getByText("free"))).toContain("p-[12px]");
  });

  it("with `flush`, puts a hairline between its rows", () => {
    render(
      <Fieldset title="Schedule" flush>
        <ValueRow kind="info" label="A">
          1
        </ValueRow>
        <ValueRow kind="info" label="B">
          2
        </ValueRow>
      </Fieldset>,
    );
    const body = screen.getByText("A").closest("section")?.lastElementChild as HTMLElement;
    expect(classes(body)).toEqual(expect.arrayContaining(["divide-y-[0.5px]", "divide-hair"]));
    expect(classes(body)).not.toContain("p-[12px]");
  });

  it("carries a mini add button at the right of the header", () => {
    const onClick = vi.fn();
    render(
      <Fieldset title="Schedule" action={<FieldsetAdd onClick={onClick}>Schedule</FieldsetAdd>}>
        x
      </Fieldset>,
    );
    const add = screen.getByRole("button", { name: "Schedule" });
    expect(classes(add)).toEqual(
      expect.arrayContaining(["h-[25px]", "rounded-pill", "bg-card", "shadow-e1"]),
    );
    fireEvent.click(add);
    expect(onClick).toHaveBeenCalledTimes(1);
  });
});
