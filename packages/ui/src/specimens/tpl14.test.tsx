// F-07-T17 (TASK-7919; handoff TPL-14 a–f): "Fixture tests prove 2 + 38 + 30 + 5 + 25 = 100 and the
// K-1 band ties to 307,900 / 4,600 / 1,550 / 150,000 and 1,912,500, and all six artboards render
// with olivia-brandt as viewer."
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { TPL14_BOARDS, Tpl14Specimen } from "./tpl14";
import { FELD_K1, TPL14_OWNERSHIP, TPL14_VIEWER, feldInspector, releasedEdges } from "./tpl14-data";

afterEach(cleanup);

describe("TPL-14 Graph canvas specimen", () => {
  it("ownership ties: 2 + 38 + 30 + 5 + 25 = 100", () => {
    expect(Object.values(TPL14_OWNERSHIP).reduce((a, b) => a + b, 0)).toBe(100);
  });

  it("Jonah Feld's K-1 band ties to the handoff's figures", () => {
    expect(FELD_K1.map((r) => r.amount)).toEqual(["307900", "4600", "1550", "150000", "1912500"]);
    expect(feldInspector().k1?.status.text).toBe("Draft K-1 · pre-release");
    expect(feldInspector(true).k1?.status.text).toBe("Released Sep 15");
  });

  it("f: every K-1 flow edge is released", () => {
    expect(releasedEdges().some((e) => e.kind === "k1_draft")).toBe(false);
  });

  it("all six artboards render for Olivia Brandt", () => {
    expect(TPL14_VIEWER).toBe("olivia-brandt");
    render(<Tpl14Specimen />);
    for (const b of TPL14_BOARDS) {
      expect(document.querySelector(`[data-tpl14="${b.id}"]`)).toBeTruthy();
    }
    expect(screen.getAllByText("No relationships yet.").length).toBe(1);
  });
});
