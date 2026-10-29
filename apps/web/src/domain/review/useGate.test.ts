import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { conflictOf, useGate } from "./useGate";

// P-04-T40: useGate is never optimistic; a 409 lands in blocked, a 403 asks for step-up, a success
// raises Undo that calls only the compensating command.

vi.mock("@abacus/ui", () => ({ toast: { undoable: vi.fn(), show: vi.fn() } }));

const opts = { doneText: () => "Approved", failedText: "Couldn't approve" };

describe("useGate", () => {
  it("stays busy until the server answers, then done", async () => {
    let resolve: (v: string) => void = () => undefined;
    const command = () => new Promise<string>((r) => (resolve = r));
    const { result } = renderHook(() => useGate({ command, ...opts }));
    let pending: Promise<void> = Promise.resolve();
    act(() => {
      pending = result.current.run();
    });
    expect(result.current.phase).toBe("busy");
    await act(async () => {
      resolve("ok");
      await pending;
    });
    expect(result.current.phase).toBe("done");
  });

  it("lands a 409 in blocked with its code and facts", async () => {
    const command = () =>
      Promise.reject(
        Object.assign(new Error("409"), {
          detail: "gate_unmet",
          facts: { gate: "G3", note: { x: 1 } },
        }),
      );
    const { result } = renderHook(() => useGate({ command, ...opts }));
    await act(() => result.current.run());
    expect(result.current.phase).toBe("blocked");
    expect(result.current.blocked).toEqual({ code: "gate_unmet", facts: { gate: "G3" } });
  });

  it("asks for a fresh sign-in on 403", async () => {
    const command = () => Promise.reject(Object.assign(new Error("403"), { detail: "forbidden" }));
    const { result } = renderHook(() => useGate({ command, ...opts }));
    await act(() => result.current.run());
    expect(result.current.stepUp).toBe(true);
    expect(result.current.phase).toBe("idle");
  });

  it("reads no conflict from a non-coded error", () => {
    expect(conflictOf(new Error("x"))).toBeNull();
    expect(conflictOf({ detail: "not_found" })).toBeNull();
  });
});
