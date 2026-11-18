// C-01-T43 (live swap 2): CLS-04, CLS-05, CLS-06 and CLS-10 show the C-20 frame for a refused or
// failed read and nothing of the record; a read that is loading or ready leaves the screen to draw.
import { render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { closeReadFrame } from "./ReadFrame";

const read = (error: unknown, pending = false) => ({
  isPending: pending,
  isError: error !== null,
  error,
  refetch: vi.fn(),
});

describe("closeReadFrame", () => {
  it.each(["CLS-04", "CLS-05", "CLS-06", "CLS-10"])(
    "%s: a 403, a 404 and a 500 each draw the frame, never the record",
    (screen) => {
      for (const [error, kind] of [
        [{ status: 403 }, "restricted"],
        [{ detail: "not_found" }, "restricted"],
        [{ status: 500 }, "error"],
      ] as const) {
        const frame = closeReadFrame(screen, read(error));
        expect(frame).not.toBeNull();
        const { container, unmount } = render(frame ?? <></>);
        const body = container.querySelector(`[data-screen-body="${screen}"]`);
        expect(body?.getAttribute("data-state")).toBe(kind);
        unmount();
      }
    },
  );

  it("loading and ready reads leave the screen to render itself", () => {
    expect(closeReadFrame("CLS-04", read(null, true))).toBeNull();
    expect(closeReadFrame("CLS-04", read(null))).toBeNull();
  });
});
