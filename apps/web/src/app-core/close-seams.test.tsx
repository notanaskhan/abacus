// C-01-T57: each seam renders nothing new with its flag off (and the close sources are exact).
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("./flags", () => ({ useFlag: () => false }));

import {
  CloseSourceSeam,
  PortalCloseIntakeSeam,
  QuestionVariantSeam,
  closePeriod,
  isCloseSource,
  useCloseNavEntry,
} from "./close-seams";

describe("C-01-T57 close seams", () => {
  it("knows exactly the close sources of each overlay", () => {
    expect(isCloseSource("signoff", "reconciliation")).toBe(true);
    expect(isCloseSource("signoff", "workpaper")).toBe(false);
    expect(isCloseSource("approve", "close_aje")).toBe(true);
    expect(isCloseSource("viewer", "close_statement")).toBe(true);
    expect(isCloseSource("viewer", undefined)).toBe(false);
  });

  it("reads a close period only in its YYYY-MM shape", () => {
    expect(closePeriod("?period=2026-08")).toBe("2026-08");
    expect(closePeriod("?period=2026-13")).toBeUndefined();
    expect(closePeriod("?binder=1")).toBeUndefined();
  });

  it("renders the live overlay unchanged with closes.engine off", () => {
    const { container } = render(
      <CloseSourceSeam overlay="signoff" targetType="reconciliation" targetId="r1">
        <p>SHL-12 as today</p>
      </CloseSourceSeam>,
    );
    expect(screen.getByText("SHL-12 as today")).toBeTruthy();
    expect(container.innerHTML).toBe("<p>SHL-12 as today</p>");
  });

  it("renders the portal documents route unchanged with closes.portal_requests off", () => {
    const { container } = render(
      <PortalCloseIntakeSeam search="?period=2026-08">
        <p>Documents as today</p>
      </PortalCloseIntakeSeam>,
    );
    expect(container.innerHTML).toBe("<p>Documents as today</p>");
  });

  it("renders POR-04 unchanged with closes.portal_requests off", () => {
    const { container } = render(
      <QuestionVariantSeam questionId="q1">
        <p>POR-04 as today</p>
      </QuestionVariantSeam>,
    );
    expect(container.innerHTML).toBe("<p>POR-04 as today</p>");
  });

  it("offers no nav entry with the flag off", () => {
    function Probe() {
      return <p>{useCloseNavEntry() === undefined ? "none" : "entry"}</p>;
    }
    render(<Probe />);
    expect(screen.getByText("none")).toBeTruthy();
  });
});
