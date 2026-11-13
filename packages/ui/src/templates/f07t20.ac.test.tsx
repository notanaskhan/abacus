// F-07-T20 (TASK-7921; ADR-078): independent acceptance tests for the T14 inspector and the T17 form
// renderer, from SPEC-652 and the rows' acceptance. "Tests fail on an unmasked TIN, a reveal
// without the capability, any input on the form face, Download in the viewer bar, a trace not from
// a manifest match_id."
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { MatchScope } from "../tracing/match";
import { FormRendererLayout } from "./form-renderer";
import { GraphCanvasLayout, MaskedTin } from "./graph-layout";

afterEach(cleanup);

const FILE = {
  name: "Ridgeline 2025 Form 1065",
  pages: [{ n: 1, width_pt: 612, height_pt: 792, rotation: 0 as const, src: "/f/1.png" }],
  regions: [],
};

describe("T14 inspector (independent)", () => {
  it.each(["123-45-4417", "123456789", "4417", "XX-XXX0287", "•••-••-44"])(
    "an unmasked or malformed TIN %s never draws",
    (tin) => {
      render(<MaskedTin value={tin} canReveal={false} />);
      expect(screen.queryByText(tin)).toBeNull();
      expect(screen.getByText("—")).toBeTruthy();
      cleanup();
    },
  );

  it("no Reveal without the capability, even with a handler", () => {
    render(
      <GraphCanvasLayout
        view="graph"
        canvas={null}
        inspector={{ title: "Jonah Feld", sub: "Person", tin: "•••-••-4417", kv: [] }}
        canReveal={false}
        onReveal={async () => "123-45-4417"}
      />,
    );
    expect(screen.queryByText("Reveal (logged)")).toBeNull();
  });
});

describe("T17 form renderer (independent)", () => {
  function draw(menu: { label: string; onSelect: () => void }[] = []) {
    return render(
      <MatchScope>
        <FormRendererLayout
          mode="form"
          thumbs={[{ n: 1, src: "/f/1.png" }]}
          page={1}
          file={FILE}
          menu={menu}
          k1s={[]}
          total={{ state: "tie" }}
          diagnostics={[{ id: "d", severity: "warning", text: "Check", page: 1, match: null }]}
        />
      </MatchScope>,
    );
  }

  it("the form face holds no input", () => {
    const { container } = draw();
    const face = container.querySelector("[data-form-face]");
    expect(face?.querySelectorAll("input, textarea, select, [contenteditable]").length).toBe(0);
  });

  it("Download is never a bar button; only the caller's menu may hold it", () => {
    draw([{ label: "Download", onSelect: () => undefined }]);
    const bars = document.querySelectorAll('[role="toolbar"]');
    for (const bar of bars) {
      expect([...bar.querySelectorAll("button")].some((b) => b.textContent === "Download")).toBe(false);
    }
  });

  it("a diagnostic without a manifest match lights nothing (pages only)", () => {
    draw();
    expect(document.querySelector("[data-lit]")).toBeNull();
  });
});
