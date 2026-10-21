// F-05-T12 (C-06): the Status kit's components. A pill is radius 999 (DEC-124) on its variant's
// tokens, a disc carries role=img and a name, words always come with the colour, and every word is
// read from the registry.
import {
  DISC_LABEL,
  DISC_STATES,
  RegistryStatus,
  Status,
  StatusDisc,
  StatusPill,
  SubLine,
  SyncChip,
  TallyPill,
  Tick,
  type DiscSize,
  type PillVariant,
} from "@abacus/ui";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(cleanup);

function classes(element: HTMLElement): string[] {
  return element.className.split(/\s+/);
}

describe("StatusPill", () => {
  const VARIANTS: [PillVariant, string[]][] = [
    ["amber", ["bg-amber-tint", "text-amber-ink"]],
    ["green", ["bg-green", "text-on-dark", "shadow-lift"]],
    ["green-tint", ["bg-green-tint", "text-green-ink"]],
    ["red", ["bg-red", "text-on-dark", "shadow-lift"]],
    ["red-tint", ["bg-red-tint", "text-red-ink"]],
    ["neutral", ["bg-chip", "text-ink-2"]],
    ["muted", ["bg-nested", "text-ink-3", "font-normal", "inset-shadow-hair"]],
    ["soon", ["bg-nested", "text-ink-3"]],
    ["outline", ["bg-card", "text-ink-2", "shadow-e1"]],
    ["tag", ["bg-nested", "text-ink-2", "inset-shadow-hair"]],
  ];

  it.each(VARIANTS)("draws %s from tokens, as a pill", (variant, expected) => {
    render(<StatusPill variant={variant}>Word</StatusPill>);
    const pill = screen.getByText("Word");
    expect(classes(pill)).toEqual(expect.arrayContaining([...expected, "rounded-pill"]));
    expect(classes(pill)).toEqual(
      expect.arrayContaining(["inline-flex", "items-center", "whitespace-nowrap"]),
    );
    expect(pill.className).not.toMatch(/#[0-9a-f]{3,8}|rgba?\(/i);
  });

  it("takes its height, padding and type role from the size", () => {
    render(
      <>
        <StatusPill size="state">State</StatusPill>
        <StatusPill size="card-state">Card</StatusPill>
        <StatusPill size="sm">Small</StatusPill>
        <StatusPill size="micro">Micro</StatusPill>
        <StatusPill size="tally">Tally</StatusPill>
        <StatusPill size="tag" variant="tag">
          Tag
        </StatusPill>
      </>,
    );
    expect(classes(screen.getByText("State"))).toEqual(
      expect.arrayContaining(["h-[21px]", "px-[8px]", "text-pill"]),
    );
    expect(classes(screen.getByText("Card"))).toEqual(
      expect.arrayContaining(["h-[21px]", "px-[9px]", "text-pill-card"]),
    );
    expect(classes(screen.getByText("Small"))).toEqual(
      expect.arrayContaining(["h-[19px]", "text-pill-sm"]),
    );
    expect(classes(screen.getByText("Micro"))).toEqual(
      expect.arrayContaining(["h-[18px]", "gap-[3px]", "text-micro"]),
    );
    expect(classes(screen.getByText("Tally"))).toEqual(
      expect.arrayContaining(["h-[17px]", "text-micro"]),
    );
    expect(classes(screen.getByText("Tag"))).toEqual(
      expect.arrayContaining(["h-[23px]", "text-pill-card"]),
    );
  });

  it("puts a check, a spinner or a chevron around the word, and nothing else", () => {
    const { container } = render(
      <>
        <StatusPill variant="green" check>
          Done
        </StatusPill>
        <StatusPill variant="amber" spin>
          Connecting…
        </StatusPill>
        <StatusPill variant="neutral" size="status">
          Not started
        </StatusPill>
        <StatusPill variant="neutral">Plain</StatusPill>
      </>,
    );
    const svgs = (word: string): number => screen.getByText(word).querySelectorAll("svg").length;
    expect(svgs("Done")).toBe(1);
    expect(svgs("Connecting…")).toBe(1);
    expect(svgs("Not started")).toBe(1);
    expect(svgs("Plain")).toBe(0);
    expect(container.querySelectorAll("svg[aria-hidden='true']")).toHaveLength(3);
    const check = screen.getByText("Done").querySelector("svg");
    expect(check?.getAttribute("width")).toBe("11");
    expect(screen.getByText("Not started").querySelector("svg")?.getAttribute("width")).toBe("12");
  });

  it("keeps working for callers that name a tone", () => {
    render(
      <>
        <StatusPill tone="success">Received</StatusPill>
        <StatusPill tone="danger">Returned</StatusPill>
        <StatusPill tone="warning">Uploaded</StatusPill>
        <StatusPill tone="neutral">Draft</StatusPill>
      </>,
    );
    expect(classes(screen.getByText("Received"))).toContain("bg-green-tint");
    expect(classes(screen.getByText("Returned"))).toContain("bg-red-tint");
    expect(classes(screen.getByText("Uploaded"))).toContain("bg-amber-tint");
    expect(classes(screen.getByText("Draft"))).toContain("bg-chip");
    expect(classes(screen.getByText("Draft"))).toContain("rounded-pill");
  });

  it("renders a legacy state through Status", () => {
    render(<Status domain="request" value="uploaded" />);
    expect(classes(screen.getByText("Uploaded"))).toContain("bg-amber-tint");
  });
});

describe("StatusDisc", () => {
  it.each(DISC_STATES)("names the %s disc", (state) => {
    render(<StatusDisc state={state} />);
    const disc = screen.getByRole("img", { name: DISC_LABEL[state] });
    expect(classes(disc)).toContain("size-[15px]");
  });

  it("is named Done, Prepared, To do, In progress, Running, Warning, Failed, Skipped, Waiting", () => {
    expect(DISC_STATES.map((s) => DISC_LABEL[s])).toEqual([
      "Done",
      "Prepared",
      "To do",
      "In progress",
      "Running",
      "Warning",
      "Failed",
      "Skipped",
      "Waiting",
    ]);
  });

  it("draws the glyph at 8 under 13, 9 at 15 and 10 at 17, stroke 1.9", () => {
    const sizes: [DiscSize, string][] = [
      [13, "8"],
      [15, "9"],
      [17, "10"],
    ];
    for (const [size, glyph] of sizes) {
      cleanup();
      render(<StatusDisc state="done" size={size} />);
      const svg = screen.getByRole("img", { name: "Done" }).querySelector("svg");
      expect(svg?.getAttribute("width")).toBe(glyph);
      expect(svg?.getAttribute("stroke-width")).toBe("1.9");
    }
  });

  it("fills done green, fail red, off ink-4 and wait amber; warn is a bare amber triangle", () => {
    render(
      <>
        <StatusDisc state="done" />
        <StatusDisc state="fail" />
        <StatusDisc state="off" />
        <StatusDisc state="wait" />
        <StatusDisc state="warn" />
      </>,
    );
    expect(classes(screen.getByRole("img", { name: "Done" }))).toContain("bg-green");
    expect(classes(screen.getByRole("img", { name: "Failed" }))).toContain("bg-red");
    expect(classes(screen.getByRole("img", { name: "Skipped" }))).toContain("bg-ink-4");
    expect(classes(screen.getByRole("img", { name: "Waiting" }))).toContain("bg-amber");
    const warn = screen.getByRole("img", { name: "Warning" });
    expect(classes(warn)).toContain("text-amber");
    expect(classes(warn)).not.toContain("rounded-full");
    expect(warn.querySelector("svg")?.getAttribute("width")).toBe("15");
  });

  it("turns the running ring on the 820ms utility and rings the empty ones", () => {
    render(
      <>
        <StatusDisc state="run" />
        <StatusDisc state="todo" />
        <StatusDisc state="prepared" />
        <StatusDisc state="half" />
      </>,
    );
    expect(
      screen.getByRole("img", { name: "Running" }).querySelector(".motion-spin"),
    ).not.toBeNull();
    expect(classes(screen.getByRole("img", { name: "To do" }))).toContain("inset-ring-ink-4");
    expect(classes(screen.getByRole("img", { name: "Prepared" }))).toContain("inset-ring-ink-4");
    expect(
      screen.getByRole("img", { name: "In progress" }).querySelector("path.fill-ink"),
    ).not.toBeNull();
  });
});

describe("SubLine", () => {
  it("sets an 11.5px line in ink-3, or amber ink, beside its disc", () => {
    render(
      <>
        <SubLine disc="todo">Queued</SubLine>
        <SubLine tone="text-amber" disc="half">
          Blocked on a Partner decision
        </SubLine>
      </>,
    );
    expect(classes(screen.getByText("Queued").parentElement as HTMLElement)).toEqual(
      expect.arrayContaining(["text-meta", "text-ink-3"]),
    );
    expect(
      classes(screen.getByText("Blocked on a Partner decision").parentElement as HTMLElement),
    ).toContain("text-amber-ink");
    expect(screen.getByRole("img", { name: "To do" })).toBeTruthy();
    expect(screen.getByRole("img", { name: "In progress" })).toBeTruthy();
  });
});

describe("SyncChip", () => {
  it("reads every sync state from the registry, with its glyph", () => {
    render(
      <>
        <SyncChip code="not_yet_exported" />
        <SyncChip code="ready_for_export" />
        <SyncChip code="exporting" />
        <SyncChip code="synced" vars={{ date: "Sep 10" }} />
        <SyncChip code="out_of_sync" />
        <SyncChip code="import_pending_approval" />
        <SyncChip code="failed" />
      </>,
    );
    for (const word of [
      "Not yet exported",
      "Ready for export",
      "Exporting…",
      "Synced Sep 10",
      "Out of sync",
      "Import pending approval",
      "Export failed",
    ]) {
      const chip = screen.getByText(word);
      expect(classes(chip)).toEqual(
        expect.arrayContaining([
          "bg-card",
          "shadow-e1",
          "h-[29px]",
          "rounded-pill",
          "font-normal",
        ]),
      );
    }
    expect(screen.getByRole("img", { name: "Done" })).toBeTruthy();
    expect(screen.getByRole("img", { name: "Failed" })).toBeTruthy();
    expect(screen.getByText("Exporting…").querySelector(".motion-spin")).not.toBeNull();
  });

  it("is a button only when it has an action, and carries the chevron", () => {
    const onClick = vi.fn();
    render(
      <>
        <SyncChip code="synced" vars={{ date: "Sep 10" }} />
        <SyncChip code="out_of_sync" onClick={onClick} aria-haspopup="menu" />
      </>,
    );
    expect(screen.getAllByRole("button")).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: "Out of sync" }));
    expect(onClick).toHaveBeenCalledOnce();
    expect(screen.getByRole("button").querySelectorAll("svg").length).toBeGreaterThan(1);
  });
});

describe("Tick", () => {
  it("is micro green for MS and Received, micro neutral for F, CF and PY", () => {
    render(
      <>
        <Tick code="MS" />
        <Tick code="Received" />
        <Tick code="F" />
        <Tick code="CF" />
        <Tick code="PY" />
      </>,
    );
    for (const word of ["MS", "Received"]) {
      const tick = screen.getByText(word);
      expect(classes(tick)).toEqual(expect.arrayContaining(["bg-green", "h-[18px]"]));
      expect(tick.querySelector("svg")?.getAttribute("width")).toBe("9");
      expect(tick.querySelector("svg")?.getAttribute("stroke-width")).toBe("2.8");
    }
    for (const word of ["F", "CF", "PY"]) {
      const tick = screen.getByText(word);
      expect(classes(tick)).toEqual(expect.arrayContaining(["bg-chip", "h-[18px]"]));
      expect(tick.querySelector("svg")).toBeNull();
    }
  });

  it("is a bare ink-3 check at 11 for an agreed figure", () => {
    render(<Tick code="check" />);
    const tick = screen.getByRole("img", { name: "Agreed" });
    expect(classes(tick)).toContain("text-ink-3");
    expect(tick.querySelector("svg")?.getAttribute("width")).toBe("11");
    expect(tick.querySelector("svg")?.getAttribute("stroke-width")).toBe("2");
  });
});

describe("TallyPill", () => {
  it("is green for a tie, amber for off and check, muted for pending", () => {
    render(
      <>
        <TallyPill code="tie" />
        <TallyPill code="off" vars={{ amount: "8,500" }} />
        <TallyPill code="check" />
        <TallyPill code="pending" />
        <TallyPill code="reconciled" />
      </>,
    );
    expect(classes(screen.getByText("tie"))).toEqual(
      expect.arrayContaining(["bg-green", "h-[17px]"]),
    );
    expect(classes(screen.getByText("off 8,500"))).toContain("bg-amber-tint");
    expect(classes(screen.getByText("Check"))).toContain("bg-amber-tint");
    expect(classes(screen.getByText("Pending"))).toEqual(
      expect.arrayContaining(["bg-nested", "font-normal"]),
    );
    expect(classes(screen.getByText("Reconciled"))).toContain("bg-green");
  });

  it("sets the ties-once-posted state as an amber line with its disc", () => {
    render(<TallyPill code="ties_once_posted" />);
    expect(classes(screen.getByText("Ties once posted").parentElement as HTMLElement)).toContain(
      "text-amber-ink",
    );
  });
});

describe("RegistryStatus", () => {
  it("reads a context's word, and a pill for a state with a variant", () => {
    render(
      <>
        <RegistryStatus object="return" code="preparing" context="subbar_1040_1041" />
        <RegistryStatus object="engagement" code="delivered" />
      </>,
    );
    expect(classes(screen.getByText("Draft"))).toContain("bg-amber-tint");
    const delivered = screen.getByText("Delivered");
    expect(classes(delivered)).toContain("bg-green");
    expect(delivered.querySelector("svg")).not.toBeNull();
  });

  it("draws a disc and a line where the registry gives no pill", () => {
    render(
      <>
        <RegistryStatus object="agent_run" code="running" />
        <RegistryStatus object="close_task" code="needs_attention" />
        <RegistryStatus
          object="audit_section"
          code="blocked_on_decision"
          vars={{ role: "Partner" }}
        />
      </>,
    );
    expect(screen.getByRole("img", { name: "Running" })).toBeTruthy();
    const [first, second] = screen.getAllByRole("img", { name: "Warning" });
    expect(first?.parentElement).toBe(screen.getByText("Needs attention").parentElement);
    expect(second?.parentElement).toBe(
      screen.getByText("Blocked on a Partner decision").parentElement,
    );
  });

  it("uses the client's words in the portal", () => {
    render(<RegistryStatus object="request" code="not_applicable" client />);
    expect(screen.getByText("Ignored")).toBeTruthy();
  });

  it("can leave the disc out", () => {
    render(<RegistryStatus object="agent_run" code="running" withDisc={false} />);
    expect(screen.queryByRole("img")).toBeNull();
    expect(screen.getByText("Running")).toBeTruthy();
  });

  it("draws a sync state as the chip", () => {
    render(<RegistryStatus object="return_sync_chip" code="failed" />);
    expect(screen.getByText("Export failed")).toBeTruthy();
    expect(screen.getByRole("img", { name: "Failed" })).toBeTruthy();
  });

  it("puts the weight on a material weakness", () => {
    render(<RegistryStatus object="deficiency_severity" code="material_weakness" />);
    expect(classes(screen.getByText("Material weakness"))).toContain("font-medium");
    expect(classes(screen.getByText("Material weakness"))).toContain("bg-red");
  });
});
